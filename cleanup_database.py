#!/usr/bin/python3
# -*- coding: utf-8 -*-

import argparse
import configparser
import datetime
import os
import sys
import syslog
import traceback

import log
from rain import get_bool, get_int, get_text


CONF_FILE = '/home/pi/irigatie/irigatie.conf'
DEFAULT_RETENTION_DAYS = 730
DEFAULT_DELETE_BATCH_SIZE = 1000


class CleanupConfig:
    def __init__(self, parser):
        self.db_server = get_text(parser, 'SQL', 'DB_SERVER', '127.0.0.1')
        self.db_port = get_text(parser, 'SQL', 'DB_PORT', '3306')
        self.db_user = get_text(parser, 'SQL', 'DB_USER', 'irigatie_user')
        self.db_pass = get_text(parser, 'SQL', 'DB_PASS', '')
        self.db_name = get_text(parser, 'SQL', 'DB_NAME', 'irigatie')

        self.rain_events_retention_days = get_int(
            parser,
            'Database Cleanup',
            'RAIN_EVENTS_RETENTION_DAYS',
            DEFAULT_RETENTION_DAYS,
        )
        self.watering_log_retention_days = get_int(
            parser,
            'Database Cleanup',
            'WATERING_LOG_RETENTION_DAYS',
            DEFAULT_RETENTION_DAYS,
        )
        self.delete_batch_size = get_int(
            parser,
            'Database Cleanup',
            'DELETE_BATCH_SIZE',
            DEFAULT_DELETE_BATCH_SIZE,
        )
        self.delete_zero_openmeteo = get_bool(
            parser,
            'Database Cleanup',
            'DELETE_ZERO_OPENMETEO',
            True,
        )

        self.validate()

    def validate(self):
        if self.rain_events_retention_days <= 0:
            raise RuntimeError('RAIN_EVENTS_RETENTION_DAYS must be greater than zero')
        if self.watering_log_retention_days <= 0:
            raise RuntimeError('WATERING_LOG_RETENTION_DAYS must be greater than zero')
        if self.delete_batch_size <= 0:
            raise RuntimeError('DELETE_BATCH_SIZE must be greater than zero')


def log_info(msg, **fields):
    log.info('db_cleanup', msg, **fields)


def log_err(msg, **fields):
    log.err('db_cleanup', msg, **fields)


def parse_args():
    parser = argparse.ArgumentParser(
        description='Prune old irrigation history rows from MySQL.'
    )
    parser.add_argument('config', nargs='?', default=CONF_FILE,
                        help='path to irigatie.conf')
    parser.add_argument('--dry-run', action='store_true',
                        help='count matching rows without deleting anything')
    return parser.parse_args()


def read_config(path):
    if not os.path.exists(path):
        raise RuntimeError('Config file not found: %s' % path)
    parser = configparser.ConfigParser()
    parser.read(path)
    return CleanupConfig(parser)


def count_rows(database, operation, table, where_sql, params):
    row = database.fetchone(
        operation,
        'SELECT COUNT(*) AS row_count FROM %s WHERE %s;' % (table, where_sql),
        params,
    )
    return int(row.get('row_count') or 0)


def delete_rows_batched(database, operation, table, where_sql, params, batch_size):
    total_deleted = 0
    while True:
        result = database.execute_result(
            operation,
            'DELETE FROM %s WHERE %s LIMIT %%s;' % (table, where_sql),
            tuple(list(params) + [batch_size]),
        )
        deleted = int(result.get('rowcount') or 0)
        total_deleted += deleted
        if deleted < batch_size:
            return total_deleted


def cleanup_target(database, label, table, where_sql, params, batch_size, dry_run):
    if dry_run:
        matched = count_rows(
            database,
            'count_%s' % label,
            table,
            where_sql,
            params,
        )
        log_info('dry run matched rows', target=label, rows=matched)
        return matched

    deleted = delete_rows_batched(
        database,
        'delete_%s' % label,
        table,
        where_sql,
        params,
        batch_size,
    )
    log_info('deleted rows', target=label, rows=deleted)
    return deleted


def run_cleanup(config, dry_run=False):
    from db import IrrigationDatabase

    now = datetime.datetime.now().replace(microsecond=0)
    rain_cutoff = now - datetime.timedelta(days=config.rain_events_retention_days)
    watering_cutoff = now - datetime.timedelta(days=config.watering_log_retention_days)

    database = IrrigationDatabase(config)
    database.connect()
    try:
        log_info(
            'database cleanup starting',
            dry_run=dry_run,
            batch_size=config.delete_batch_size,
            rain_events_retention_days=config.rain_events_retention_days,
            watering_log_retention_days=config.watering_log_retention_days,
        )

        results = {}
        if config.delete_zero_openmeteo:
            results['zero_openmeteo_rain_events'] = cleanup_target(
                database,
                'zero_openmeteo_rain_events',
                'rain_events',
                'source = %s AND amount_mm = %s',
                ('openmeteo', 0),
                config.delete_batch_size,
                dry_run,
            )

        results['old_rain_events'] = cleanup_target(
            database,
            'old_rain_events',
            'rain_events',
            'event_time < %s',
            (rain_cutoff.strftime('%Y-%m-%d %H:%M:%S'),),
            config.delete_batch_size,
            dry_run,
        )

        results['old_watering_log'] = cleanup_target(
            database,
            'old_watering_log',
            'watering_log',
            'started_at < %s',
            (watering_cutoff.strftime('%Y-%m-%d %H:%M:%S'),),
            config.delete_batch_size,
            dry_run,
        )

        log_info(
            'database cleanup finished',
            dry_run=dry_run,
            zero_openmeteo_rain_events=results.get('zero_openmeteo_rain_events', 0),
            old_rain_events=results['old_rain_events'],
            old_watering_log=results['old_watering_log'],
        )
    finally:
        database.close()


def main():
    syslog.openlog('irigatie-db-cleanup')
    args = parse_args()
    config = read_config(args.config)
    run_cleanup(config, args.dry_run)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        log_err('database cleanup failed',
                error=repr(exc), traceback=traceback.format_exc())
        sys.exit(1)
