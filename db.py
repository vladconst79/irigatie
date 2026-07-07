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
        self.cur = None
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
        self.cur = self.conn.cursor(pymysql.cursors.DictCursor)
        self.conn.ping(True)
        return self

    def close(self):
        if self.cur is not None:
            self.cur.close()
            self.cur = None
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def ping(self):
        self.conn.ping(True)

    def add_rain_credit_mm(self, amount_mm):
        sql = 'UPDATE programari SET ploaie = ploaie + %s, zile_fp = 1;'
        self.ping()
        self.cur.execute(sql, (amount_mm,))

    def record_hardware_rain_pulse(self, amount_mm):
        self.add_rain_credit_mm(amount_mm)

    def log_rain_event(self, source, amount_mm, raw_value=None,
                       event_time=None):
        try:
            self.ping()
            self.cur.execute(
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
            syslog.syslog(syslog.LOG_ERR, 'Nu pot inregistra rain_events: %r' % (exc,))

    def get_manual_program(self, program_id):
        sql = 'SELECT * FROM progman WHERE id = ' + str(program_id) + ';'
        self.ping()
        self.cur.execute(sql)
        return self.cur.fetchone()

    def get_zone(self, zone_id):
        sql = 'SELECT * FROM trasee WHERE id = ' + str(zone_id)
        self.ping()
        self.cur.execute(sql)
        return self.cur.fetchone()

    def get_scheduled_program(self, program_id):
        sql = (
            'SELECT trasee.denumire, trasee.activ, trasee.id AS tid, programari.* '
            'FROM programari LEFT JOIN trasee ON programari.traseu_id = trasee.id '
            'WHERE programari.id = %s;' % str(program_id)
        )
        self.ping()
        self.cur.execute(sql)
        return self.cur.fetchone()

    def reduce_rain_after_scheduled_program(self, row):
        rain_credit_mm = row['ploaie']
        rain_threshold_mm = row['max_ploaie']
        days_without_rain = row['zile_fp']
        new_rain_credit_mm = (
            abs(rain_credit_mm - rain_threshold_mm * days_without_rain) +
            (rain_credit_mm - rain_threshold_mm * days_without_rain)
        ) / 2
        sql = (
            'UPDATE programari SET ploaie = ' + str(new_rain_credit_mm) +
            ', zile_fp = ' + str(days_without_rain + 1) +
            ' WHERE traseu_id = %s;' % str(row['traseu_id'])
        )
        self.ping()
        self.cur.execute(sql)
        syslog.syslog('SQL reduce ploaie: ' + sql)

    def set_runtime_state(self, state, source=None, command=None, program_id=None,
                          traseu_id=None, started_at=None, expected_end_at=None,
                          message=None):
        try:
            with self.runtime_state_lock:
                self.ping()
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
                self.cur.execute(sql, (
                    state, source, command, program_id, traseu_id,
                    db_timestamp(started_at), db_timestamp(expected_end_at), message
                ))
        except Exception as exc:
            syslog.syslog(syslog.LOG_ERR, 'Nu pot actualiza runtime_state: %r' % (exc,))

    def update_runtime_zone(self, traseu_id, expected_end_at=None, message=None):
        try:
            with self.runtime_state_lock:
                self.ping()
                self.cur.execute(
                    'UPDATE runtime_state SET traseu_id = %s, expected_end_at = %s, '
                    'heartbeat_at = NOW(), updated_at = NOW(), message = %s WHERE id = 1;',
                    (traseu_id, db_timestamp(expected_end_at), message)
                )
        except Exception as exc:
            syslog.syslog(syslog.LOG_ERR, 'Nu pot actualiza zona runtime_state: %r' % (exc,))

    def heartbeat_runtime_state(self):
        try:
            with self.runtime_state_lock:
                self.ping()
                self.cur.execute(
                    'UPDATE runtime_state SET heartbeat_at = NOW(), updated_at = NOW() '
                    'WHERE id = 1 AND state IN (\'running\', \'stopping\');'
                )
        except Exception as exc:
            syslog.syslog(syslog.LOG_ERR, 'Nu pot actualiza heartbeat runtime_state: %r' % (exc,))

    def mark_runtime_idle(self, message='idle'):
        self.set_runtime_state('idle', message=message)

    def mark_runtime_error(self, message):
        self.set_runtime_state('error', message=message[:255])

    def mark_startup_runtime_state(self):
        try:
            with self.runtime_state_lock:
                self.ping()
                self.cur.execute('SELECT state FROM runtime_state WHERE id = 1;')
                row = self.cur.fetchone()
                if row is not None and row.get('state') == 'running':
                    self.cur.execute(
                        'UPDATE runtime_state SET state = %s, heartbeat_at = NOW(), updated_at = NOW(), message = %s WHERE id = 1;',
                        ('interrupted', 'daemon startup found previous running state')
                    )
                    return
        except Exception as exc:
            syslog.syslog(syslog.LOG_ERR, 'Nu pot verifica runtime_state la startup: %r' % (exc,))
        self.mark_runtime_idle('daemon startup')


def db_timestamp(value):
    if value is None:
        return None
    return value.strftime('%Y-%m-%d %H:%M:%S')
