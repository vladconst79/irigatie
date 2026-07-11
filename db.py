#!/usr/bin/python3
# -*- coding: utf-8 -*-
import datetime
import decimal
import threading

import pymysql
import log


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
            connect_timeout=5,
            read_timeout=5,
            write_timeout=5,
        )
        self.conn.ping(True)
        return self

    def close(self):
        if self.conn is not None:
            self.conn.close()
            self.conn = None

    def ping(self):
        self.conn.ping(True)

    def check_connection(self):
        try:
            with self.db_lock:
                self.ping()
            return True, None
        except Exception as exc:
            log_database_error('check_connection', exc)
            return False, repr(exc)

    def execute(self, operation, sql, params=()):
        try:
            with self.db_lock:
                self.ping()
                with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(sql, params)
        except Exception as exc:
            log_database_error(operation, exc)
            raise

    def execute_result(self, operation, sql, params=()):
        try:
            with self.db_lock:
                self.ping()
                with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(sql, params)
                    return {
                        'rowcount': cursor.rowcount,
                        'lastrowid': cursor.lastrowid,
                    }
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

    def fetchall(self, operation, sql, params=()):
        try:
            with self.db_lock:
                self.ping()
                with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
                    cursor.execute(sql, params)
                    return cursor.fetchall()
        except Exception as exc:
            log_database_error(operation, exc)
            raise

    def add_rain_credit_mm(self, amount_mm):
        self.execute(
            'add_rain_credit_mm',
            'UPDATE programari SET ploaie = ploaie + %s, zile_fp = 1;',
            (amount_mm,)
        )

    def record_rain_event_with_credit(self, source, amount_mm, raw_value=None,
                                      event_time=None, credit_mm=0.0):
        try:
            with self.db_lock:
                self.ping()
                self.conn.begin()
                try:
                    with self.conn.cursor(pymysql.cursors.DictCursor) as cursor:
                        cursor.execute(
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
                        if credit_mm != 0.0:
                            cursor.execute(
                                'UPDATE programari SET ploaie = ploaie + %s, zile_fp = 1;',
                                (credit_mm,)
                            )
                    self.conn.commit()
                except Exception:
                    self.conn.rollback()
                    raise
        except Exception as exc:
            log_database_error('record_rain_event_with_credit', exc)
            raise

    def record_hardware_rain_pulse(self, amount_mm):
        self.add_rain_credit_mm(amount_mm)

    def log_rain_event(self, source, amount_mm, raw_value=None,
                       event_time=None, suppress_errors=True):
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
            log_database_error('log_rain_event suppressed', exc)
            if not suppress_errors:
                raise

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
                    db_decimal(planned_seconds, '0.001'),
                    db_decimal(actual_seconds, '0.001'),
                    db_decimal(rain_credit_mm, '0.0001'),
                    result,
                    truncate_text(error, 255),
                )
            )
        except Exception as exc:
            log_database_error('log_watering_event suppressed', exc)
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
            'SELECT trasee.denumire, trasee.activ AS zone_enabled, trasee.id AS tid, '
            'programari.id, programari.traseu_id, programari.m, programari.h, '
            'programari.dom, programari.mon, programari.dow, programari.durata, '
            'programari.ploaie, programari.max_ploaie, programari.zile_fp, '
            'programari.activ AS schedule_enabled, '
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
        log.info('rain_update', 'rain credit reduced',
                 rain_credit_mm='%.4f' % float(new_rain_credit_mm),
                 traseu_id=row['traseu_id'])

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
            log_database_error('set_runtime_state suppressed', exc)
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
            log_database_error('update_runtime_zone suppressed', exc)
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
            log_database_error('heartbeat_runtime_state suppressed', exc)
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
                        'UPDATE runtime_state SET state = %s, program_id = NULL, traseu_id = NULL, '
                        'expected_end_at = NULL, heartbeat_at = NOW(), updated_at = NOW(), message = %s '
                        'WHERE id = 1;',
                        ('interrupted', 'daemon startup found previous running state')
                    )
                    return
        except Exception as exc:
            log_database_error('mark_startup_runtime_state suppressed', exc)
        self.mark_runtime_idle('daemon startup')

    def get_runtime_state(self):
        return self.fetchone(
            'get_runtime_state',
            'SELECT id, state, source, command, program_id, traseu_id, '
            'started_at, expected_end_at, heartbeat_at, updated_at, message '
            'FROM runtime_state WHERE id = 1;'
        )

    def get_last_rain_update(self):
        return self.fetchone(
            'get_last_rain_update',
            'SELECT id, source, event_time, amount_mm, raw_value, created_at '
            'FROM rain_events ORDER BY event_time DESC, id DESC LIMIT 1;'
        )

    def get_app_snapshot_data(self):
        zones = self.get_app_zones()
        return {
            'zones': zones,
            'schedules': self.get_app_schedules(),
            'manual_programs': self.get_app_manual_programs(zones),
            'runtime': self.get_app_runtime(),
            'last_rain': self.get_app_last_rain(),
            'rain_24h': self.get_app_rain_24h(),
        }

    def get_app_zones(self):
        rows = self.fetchall(
            'get_app_zones',
            'SELECT id, denumire AS name, tip AS type, activ AS enabled '
            'FROM trasee ORDER BY id;'
        )
        zones = []
        for row in rows:
            zone = normalize_app_row(row)
            zone['type'] = zone_type_name(row.get('type'))
            zone['enabled'] = bool(row.get('enabled'))
            zones.append(zone)
        return zones

    def get_app_schedules(self):
        rows = self.fetchall(
            'get_app_schedules',
            'SELECT id, traseu_id AS zone_id, mon AS month, '
            'dom AS day_of_month, dow AS day_of_week, h AS hour, '
            'm AS minute, durata AS duration_minutes, '
            'max_ploaie AS max_rain_mm, ploaie AS current_rain_mm, '
            'activ AS enabled '
            'FROM programari ORDER BY mon, dom, dow, '
            'CAST(SUBSTRING_INDEX(h, \',\', 1) AS UNSIGNED), '
            'CAST(SUBSTRING_INDEX(m, \',\', 1) AS UNSIGNED), id;'
        )
        schedules = []
        for row in rows:
            schedule = normalize_app_row(row)
            schedule['enabled'] = bool(row.get('enabled'))
            schedules.append(schedule)
        return schedules

    def get_app_manual_programs(self, zones):
        rows = self.fetchall(
            'get_app_manual_programs',
            'SELECT * FROM progman ORDER BY id;'
        )
        programs = []
        for row in rows:
            durations = {}
            for zone in zones:
                zone_id = int(zone['id'])
                durations[str(zone_id)] = int(row.get('durata_t%d' % zone_id) or 0)
            programs.append({
                'id': int(row['id']),
                'name': row.get('denumire') or 'Manual %s' % row['id'],
                'zone_durations': durations,
            })
        return programs

    def get_app_runtime(self):
        row = self.fetchone(
            'get_app_runtime',
            'SELECT * FROM runtime_state WHERE id = 1;'
        )
        if not row:
            return {
                'state': 'unknown',
                'source': None,
                'command': None,
                'program_id': None,
                'zone_id': None,
                'remaining_seconds': 0,
                'heartbeat_at': None,
                'message': 'runtime_state row missing',
            }

        normalized = normalize_app_row(row)
        active = row.get('state') in ('running', 'stopping')
        return {
            'state': row.get('state') or 'unknown',
            'source': row.get('source'),
            'command': row.get('command'),
            'program_id': row.get('program_id') if active else None,
            'zone_id': row.get('traseu_id') if active else None,
            'remaining_seconds': calculate_app_remaining_seconds(row),
            'heartbeat_at': normalized.get('heartbeat_at'),
            'message': row.get('message'),
        }

    def get_app_last_rain(self):
        row = self.fetchone(
            'get_app_last_rain',
            'SELECT source, event_time, amount_mm, raw_value '
            'FROM rain_events ORDER BY event_time DESC, id DESC LIMIT 1;'
        )
        if not row:
            return {
                'source': 'N/A',
                'event_time': 'N/A',
                'amount_mm': 0,
                'raw_value': None,
            }
        return normalize_app_row(row)

    def get_app_rain_24h(self):
        window_end = datetime.datetime.now().replace(microsecond=0)
        window_start = window_end - datetime.timedelta(hours=24)
        rain_24h = empty_app_rain_24h(window_start, window_end)
        rows = self.fetchall(
            'get_app_rain_24h',
            'SELECT source, SUM(amount_mm) AS amount_mm, '
            'COUNT(*) AS event_count, MAX(event_time) AS latest_event_time '
            'FROM rain_events '
            'WHERE source IN (%s, %s) '
            'AND amount_mm > 0 '
            'AND event_time >= %s '
            'AND event_time <= %s '
            'GROUP BY source;',
            (
                'openmeteo',
                'hardware',
                db_timestamp(window_start),
                db_timestamp(window_end),
            )
        )
        for row in rows:
            source = row.get('source')
            if source not in rain_24h['sources']:
                continue
            normalized = normalize_app_row(row)
            rain_24h['sources'][source] = {
                'amount_mm': normalized.get('amount_mm') or 0,
                'event_count': int(normalized.get('event_count') or 0),
                'latest_event_time': normalized.get('latest_event_time'),
            }
        return rain_24h

    def get_watering_history(self, limit=50, before_id=None, since_hours=None,
                             result=None, source=None, zone_id=None,
                             program_id=None):
        conditions = []
        params = []
        if before_id is not None:
            conditions.append('watering_log.id < %s')
            params.append(before_id)
        if since_hours is not None:
            conditions.append(
                'watering_log.started_at >= DATE_SUB(NOW(), INTERVAL %s HOUR)'
            )
            params.append(since_hours)
        if result is not None:
            conditions.append('watering_log.result = %s')
            params.append(result)
        if source is not None:
            conditions.append('watering_log.source = %s')
            params.append(source)
        if zone_id is not None:
            conditions.append('watering_log.traseu_id = %s')
            params.append(zone_id)
        if program_id is not None:
            conditions.append('watering_log.program_id = %s')
            params.append(program_id)

        where_sql = ''
        if conditions:
            where_sql = 'WHERE ' + ' AND '.join(conditions) + ' '

        params.append(limit + 1)
        rows = self.fetchall(
            'get_watering_history',
            'SELECT watering_log.id, watering_log.started_at, '
            'watering_log.ended_at, watering_log.source, '
            'watering_log.program_id, '
            'CASE '
            'WHEN watering_log.program_id IS NULL THEN NULL '
            'WHEN watering_log.source IN (%s, %s) '
            'AND progman.denumire IS NOT NULL '
            'THEN progman.denumire '
            'WHEN programari.id IS NULL AND progman.id IS NOT NULL '
            'THEN progman.denumire '
            'ELSE CONCAT(%s, watering_log.program_id) '
            'END AS program_name, '
            'watering_log.traseu_id AS zone_id, trasee.denumire AS zone_name, '
            'watering_log.planned_seconds, watering_log.actual_seconds, '
            'watering_log.rain_credit_mm, watering_log.result, '
            'watering_log.error '
            'FROM watering_log '
            'LEFT JOIN trasee ON watering_log.traseu_id = trasee.id '
            'LEFT JOIN progman ON watering_log.program_id = progman.id '
            'LEFT JOIN programari ON watering_log.program_id = programari.id '
            'AND watering_log.traseu_id = programari.traseu_id '
            + where_sql +
            'ORDER BY watering_log.started_at DESC, watering_log.id DESC '
            'LIMIT %s;',
            tuple(['manual', 'button', 'Program #'] + params)
        )
        has_more = len(rows) > limit
        rows = rows[:limit]
        items = [normalize_watering_history_row(row) for row in rows]
        return {
            'ok': True,
            'items': items,
            'next_before_id': items[-1]['id'] if has_more and items else None,
            'has_more': has_more,
        }

    def update_zone(self, zone_id, fields):
        assignments = []
        params = []
        if 'name' in fields:
            assignments.append('denumire = %s')
            params.append(fields['name'])
        if 'type' in fields:
            assignments.append('tip = %s')
            params.append(zone_type_id(fields['type']))
        if 'enabled' in fields:
            assignments.append('activ = %s')
            params.append(1 if fields['enabled'] else 0)
        if not assignments:
            return False
        params.append(zone_id)
        result = self.execute_result(
            'update_zone',
            'UPDATE trasee SET %s WHERE id = %%s;' % ', '.join(assignments),
            tuple(params)
        )
        return result['rowcount'] > 0

    def create_schedule(self, fields):
        result = self.execute_result(
            'create_schedule',
            'INSERT INTO programari '
            '(traseu_id, h, m, dom, mon, dow, durata, max_ploaie, activ) '
            'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s);',
            (
                fields['zone_id'],
                fields['hour'],
                fields['minute'],
                fields['day_of_month'],
                fields['month'],
                fields['day_of_week'],
                fields['duration_minutes'],
                fields['max_rain_mm'],
                1 if fields['enabled'] else 0,
            )
        )
        return result['lastrowid']

    def update_schedule(self, schedule_id, fields):
        column_map = {
            'zone_id': 'traseu_id',
            'hour': 'h',
            'minute': 'm',
            'day_of_month': 'dom',
            'month': 'mon',
            'day_of_week': 'dow',
            'duration_minutes': 'durata',
            'max_rain_mm': 'max_ploaie',
            'enabled': 'activ',
        }
        assignments = []
        params = []
        for field, column in column_map.items():
            if field in fields:
                assignments.append('%s = %%s' % column)
                if field == 'enabled':
                    params.append(1 if fields[field] else 0)
                else:
                    params.append(fields[field])
        if not assignments:
            return False
        params.append(schedule_id)
        result = self.execute_result(
            'update_schedule',
            'UPDATE programari SET %s WHERE id = %%s;' % ', '.join(assignments),
            tuple(params)
        )
        return result['rowcount'] > 0

    def delete_schedule(self, schedule_id):
        result = self.execute_result(
            'delete_schedule',
            'DELETE FROM programari WHERE id = %s;',
            (schedule_id,)
        )
        return result['rowcount'] > 0

    def update_manual_program(self, program_id, fields):
        assignments = []
        params = []
        if 'name' in fields:
            assignments.append('denumire = %s')
            params.append(fields['name'])
        if 'zone_durations' in fields:
            columns = self.get_manual_duration_columns()
            duration_fields = self.prepare_manual_duration_fields(
                fields['zone_durations'], columns)
            for column in sorted(duration_fields.keys()):
                assignments.append('`%s` = %%s' % column)
                params.append(duration_fields[column])
        if not assignments:
            return False
        params.append(program_id)
        result = self.execute_result(
            'update_manual_program',
            'UPDATE progman SET %s WHERE id = %%s;' % ', '.join(assignments),
            tuple(params)
        )
        return result['rowcount'] > 0

    def get_manual_duration_columns(self):
        rows = self.fetchall(
            'get_manual_duration_columns',
            'SHOW COLUMNS FROM progman LIKE %s;',
            ('durata_t%',)
        )
        return set(row['Field'] for row in rows)

    def prepare_manual_duration_fields(self, zone_durations, columns):
        fields = {}
        for zone_id, duration in zone_durations.items():
            column = 'durata_t%d' % int(zone_id)
            if column in columns:
                fields[column] = int(duration)
        return fields


def log_database_error(operation, exc):
    log.err('db_error', 'database operation failed',
            operation=operation, error=repr(exc))


def db_timestamp(value):
    if value is None:
        return None
    return value.strftime('%Y-%m-%d %H:%M:%S')


def db_decimal(value, quantum):
    if value is None:
        return None
    return decimal.Decimal(str(value)).quantize(decimal.Decimal(quantum))


def truncate_text(value, max_length):
    if value is None:
        return None
    return str(value)[:max_length]


def empty_app_rain_24h(window_start=None, window_end=None):
    if window_end is None:
        window_end = datetime.datetime.now().replace(microsecond=0)
    if window_start is None:
        window_start = window_end - datetime.timedelta(hours=24)
    return {
        'window_hours': 24,
        'window_start': db_timestamp(window_start),
        'window_end': db_timestamp(window_end),
        'sources': {
            'openmeteo': {
                'amount_mm': 0,
                'event_count': 0,
                'latest_event_time': None,
            },
            'hardware': {
                'amount_mm': 0,
                'event_count': 0,
                'latest_event_time': None,
            },
        },
    }


def zone_type_name(value):
    try:
        value = int(value)
    except (TypeError, ValueError):
        return 'unknown'
    if value == 1:
        return 'sprinkler'
    if value == 2:
        return 'drip'
    return 'unknown'


def zone_type_id(value):
    if value == 'sprinkler':
        return 1
    if value == 'drip':
        return 2
    raise ValueError('invalid zone type')


def normalize_app_row(row):
    normalized = {}
    for key, value in row.items():
        if isinstance(value, datetime.datetime):
            normalized[key] = value.strftime('%Y-%m-%d %H:%M:%S')
        elif isinstance(value, decimal.Decimal):
            normalized[key] = float(value)
        else:
            normalized[key] = value
    return normalized


def normalize_watering_history_row(row):
    normalized = normalize_app_row(row)
    return {
        'id': normalized.get('id'),
        'started_at': normalized.get('started_at'),
        'ended_at': normalized.get('ended_at'),
        'source': normalized.get('source'),
        'program_id': normalized.get('program_id'),
        'program_name': normalized.get('program_name'),
        'zone_id': normalized.get('zone_id'),
        'zone_name': normalized.get('zone_name'),
        'planned_seconds': normalized.get('planned_seconds'),
        'actual_seconds': normalized.get('actual_seconds'),
        'rain_credit_mm': normalized.get('rain_credit_mm'),
        'result': normalized.get('result'),
        'error': normalized.get('error'),
    }


def calculate_app_remaining_seconds(runtime_state):
    if runtime_state.get('state') not in ('running', 'stopping'):
        return 0

    expected_end_at = runtime_state.get('expected_end_at')
    if expected_end_at is None:
        return None

    remaining = (expected_end_at - datetime.datetime.now()).total_seconds()
    return max(0, int(remaining))
