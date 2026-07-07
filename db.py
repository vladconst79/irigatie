#!/usr/bin/python3
# -*- coding: utf-8 -*-
import datetime
import syslog
import threading

import pymysql


class IrrigationDatabase:
    def __init__(self, config, debug=False):
        self.config = config
        self.debug = debug
        self.conn = None
        self.db_lock = threading.Lock()
        self.runtime_state_lock = threading.Lock()

    def connect(self):
        self.conn = pymysql.connect(
            host=self.config.db_server,
            port=int(self.config.db_port),
            user=self.config.db_user,
            password=self.config.db_pass,
            db=self.config.db_name,
            autocommit=True,
        )
        self.conn.ping(True)
        return self

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def ping(self):
        self.conn.ping(True)

    def execute(self, operation, sql, params=()):
        try:
            with self.db_lock:
                self.ping()
                with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(sql, params)
        except Exception as exc:
            log_database_error(operation, exc)
            raise

    def fetchone(self, operation, sql, params=()):
        try:
            with self.db_lock:
                self.ping()
                with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(sql, params)
                    return cursor.fetchone()
        except Exception as exc:
            log_database_error(operation, exc)
            raise

    def add_rain_credit_mm(self, amount_mm):
        self.execute(
            'add_rain_credit_mm',
            'UPDATE programari SET ploaie = ploaie + %s, zile_fp = 1;',
            (amount_mm,)
        )

    def record_hardware_rain_pulse(self, amount_mm):
        self.add_rain_credit_mm(amount_mm)

    def log_rain_event(self, source, amount_mm, raw_value=None,
                       event_time=None):
        try:
            self.execute(
                'log_rain_event',
                'INSERT INTO rain_events '
                '(source, event_time, amount_mm, raw_value, created_at) '
                'VALUES (%s, %s, %s, %s, NOW());',
                (
                    source,
                    db_timestamp(event_time or datetime.datetime.now()),
                    amount_mm,
                    raw_value,
                )
            )
        except Exception as exc:
            return

    def log_watering_event(self, started_at, ended_at, source, program_id=None,
                           traseu_id=None, planned_seconds=None,
                           actual_seconds=None, rain_credit_mm=None,
                           result=None, error=None):
        try:
            self.execute(
                'log_watering_event',
                'INSERT INTO watering_log '
                '(started_at, ended_at, source, program_id, traseu_id, '
                'planned_seconds, actual_seconds, rain_credit_mm, result, error) '
                'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s);',
                (
                    db_timestamp(started_at),
                    db_timestamp(ended_at),
                    source,
                    program_id,
                    traseu_id,
                    planned_seconds,
                    actual_seconds,
                    rain_credit_mm,
                    result,
                    truncate_text(error, 255),
                )
            )
        except Exception as exc:
            return

    def get_manual_program(self, program_id):
        return self.fetchone(
            'get_manual_program',
            'SELECT * FROM progman WHERE id = %s;',
            (program_id,)
        )

    def get_zone(self, zone_id):
        return self.fetchone(
            'get_zone',
            'SELECT * FROM trasee WHERE id = %s;',
            (zone_id,)
        )

    def get_scheduled_program(self, program_id):
        sql = (
            'SELECT trasee.denumire, trasee.activ, trasee.id AS tid, '
            'programari.*, '
            'programari.ploaie AS rain_credit_mm, '
            'programari.max_ploaie AS rain_threshold_mm '
            'FROM programari LEFT JOIN trasee ON programari.traseu_id = trasee.id '
            'WHERE programari.id = %s;'
        )
        return self.fetchone('get_scheduled_program', sql, (program_id,))

    def reduce_rain_after_scheduled_program(self, row):
        rain_credit_mm = row['rain_credit_mm']
        rain_threshold_mm = row['rain_threshold_mm']
        days_without_rain = row['zile_fp']
        new_rain_credit_mm = (
            abs(rain_credit_mm - rain_threshold_mm * days_without_rain) +
            (rain_credit_mm - rain_threshold_mm * days_without_rain)
        ) / 2
        self.execute(
            'reduce_rain_after_scheduled_program',
            'UPDATE programari SET ploaie = %s, zile_fp = %s WHERE traseu_id = %s;',
            (new_rain_credit_mm, days_without_rain + 1, row['traseu_id'])
        )
        syslog.syslog(
            syslog.LOG_INFO,
            'Rain credit reduced to %.4f mm for route %s' %
            (float(new_rain_credit_mm), row['traseu_id'])
        )

    def set_runtime_state(self, state, source=None, command=None, program_id=None,
                          traseu_id=None, started_at=None, expected_end_at=None,
                          message=None):
        try:
            with self.runtime_state_lock:
                sql = (
                    'INSERT INTO runtime_state '
                    '(id, state, source, command, program_id, traseu_id, started_at, expected_end_at, heartbeat_at, updated_at, message) '
                    'VALUES (1, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s) '
                    'ON DUPLICATE KEY UPDATE '
                    'state = VALUES(state), source = VALUES(source), command = VALUES(command), '
                    'program_id = VALUES(program_id), traseu_id = VALUES(traseu_id), '
                    'started_at = VALUES(started_at), expected_end_at = VALUES(expected_end_at), '
                    'heartbeat_at = VALUES(heartbeat_at), updated_at = VALUES(updated_at), message = VALUES(message);'
                )
                self.execute(
                    'set_runtime_state',
                    sql,
                    (
                        state, source, command, program_id, traseu_id,
                        db_timestamp(started_at), db_timestamp(expected_end_at), message
                    )
                )
        except Exception as exc:
            return

    def update_runtime_zone(self, traseu_id, expected_end_at=None, message=None):
        try:
            with self.runtime_state_lock:
                self.execute(
                    'update_runtime_zone',
                    'UPDATE runtime_state SET traseu_id = %s, expected_end_at = %s, '
                    'heartbeat_at = NOW(), updated_at = NOW(), message = %s WHERE id = 1;',
                    (traseu_id, db_timestamp(expected_end_at), message)
                )
        except Exception as exc:
            return

    def heartbeat_runtime_state(self):
        try:
            with self.runtime_state_lock:
                self.execute(
                    'heartbeat_runtime_state',
                    'UPDATE runtime_state SET heartbeat_at = NOW(), updated_at = NOW() '
                    'WHERE id = 1 AND state IN (\'running\', \'stopping\');'
                )
        except Exception as exc:
            return

    def mark_runtime_idle(self, message='idle'):
        self.set_runtime_state('idle', message=message)

    def mark_runtime_error(self, message):
        self.set_runtime_state('error', message=message[:255])

    def mark_startup_runtime_state(self):
        try:
            with self.runtime_state_lock:
                row = self.fetchone(
                    'mark_startup_runtime_state select',
                    'SELECT state FROM runtime_state WHERE id = 1;'
                )
                if row is not None and row.get('state') == 'running':
                    self.execute(
                        'mark_startup_runtime_state interrupted',
                        'UPDATE runtime_state SET state = %s, heartbeat_at = NOW(), updated_at = NOW(), message = %s WHERE id = 1;',
                        ('interrupted', 'daemon startup found previous running state')
                    )
                    return
        except Exception as exc:
            pass
        self.mark_runtime_idle('daemon startup')


def log_database_error(operation, exc):
    syslog.syslog(
        syslog.LOG_ERR,
        'Database operation failed: %s: %r' % (operation, exc)
    )


def db_timestamp(value):
    if value is None:
        return None
    return value.strftime('%Y-%m-%d %H:%M:%S')


def truncate_text(value, max_length):
    if value is None:
        return None
    return str(value)[:max_length]
