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
from rain import (credit_amount_for_source, default_hybrid_factor, get_float,
                  get_text)


CONF_FILE = '/home/pi/irigatie/irigatie.conf'
VALID_SOURCES = ('hardware', 'openmeteo', 'manual', 'hybrid', 'disabled')


class DatabaseConfig:
    def __init__(self, config):
        self.db_server = get_text(config, 'SQL', 'DB_SERVER', '127.0.0.1')
        self.db_port = get_text(config, 'SQL', 'DB_PORT', '3306')
        self.db_user = get_text(config, 'SQL', 'DB_USER', 'irigatie_user')
        self.db_pass = get_text(config, 'SQL', 'DB_PASS', '')
        self.db_name = get_text(config, 'SQL', 'DB_NAME', 'irigatie')


def parse_args():
    parser = argparse.ArgumentParser(
        description='Log a manual rain correction and apply configured credit')
    parser.add_argument('-c', '--config', default=CONF_FILE,
                        help='path to irigatie.conf')
    parser.add_argument('--amount-mm', type=float, required=True,
                        help='manual correction in millimeters; may be negative')
    parser.add_argument('--reason', default='manual correction',
                        help='operator note stored in rain_events.raw_value')
    parser.add_argument('--event-time',
                        help='event time, either YYYY-mm-dd HH:MM:SS or ISO format')
    parser.add_argument('--log-only', action='store_true',
                        help='log the event without changing rain credit')
    return parser.parse_args()


def read_config(path):
    config = configparser.ConfigParser()
    if not os.path.exists(path):
        raise RuntimeError('Config file not found: %s' % path)
    config.read(path)
    return config


def parse_event_time(value):
    if not value:
        return datetime.datetime.now()
    normalized = value.replace('T', ' ')
    for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
        try:
            return datetime.datetime.strptime(normalized, fmt)
        except ValueError:
            pass
    raise RuntimeError('Invalid --event-time: %s' % value)


def log_info(msg):
    log.info('rain_update', msg)


def log_err(msg):
    log.err('rain_update', msg)


def truncate_text(value, max_length):
    if value is None:
        return None
    return str(value)[:max_length]


def main():
    syslog.openlog('irigatie-manual-rain')
    args = parse_args()

    if args.amount_mm == 0:
        raise RuntimeError('--amount-mm must not be zero')

    config = read_config(args.config)
    rain_source = get_text(config, 'Rain', 'SOURCE', 'openmeteo').strip().lower()
    if rain_source not in VALID_SOURCES:
        raise RuntimeError('Invalid [Rain] SOURCE: %s' % rain_source)

    hybrid_manual_factor = get_float(
        config,
        'Rain',
        'HYBRID_MANUAL_FACTOR',
        default_hybrid_factor('manual'),
    )
    if hybrid_manual_factor < 0 or hybrid_manual_factor > 1:
        raise RuntimeError('[Rain] HYBRID_MANUAL_FACTOR must be between 0 and 1')

    event_time = parse_event_time(args.event_time)
    raw_value = truncate_text('reason=%s' % args.reason, 255)
    credit_mm = 0.0
    if not args.log_only:
        credit_mm = credit_amount_for_source(
            rain_source,
            'manual',
            args.amount_mm,
            hybrid_manual_factor,
        )

    from db import IrrigationDatabase

    database = IrrigationDatabase(DatabaseConfig(config))
    try:
        database.connect()
        database.record_rain_event_with_credit(
            'manual',
            args.amount_mm,
            raw_value,
            event_time,
            credit_mm,
        )
    finally:
        database.close()

    log_info('Manual rain correction logged: amount %.4f mm, credited %.4f mm, source %s' %
             (args.amount_mm, credit_mm, rain_source))
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as exc:
        log_err('Unexpected error: %r traceback=%s' %
                (exc, traceback.format_exc()))
        sys.exit(1)
