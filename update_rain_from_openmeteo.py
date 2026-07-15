#!/usr/bin/python3
# -*- coding: utf-8 -*-

import configparser
import os
import sys
import syslog
import traceback

import log
from db import IrrigationDatabase
from notifications import manager_from_parser
from pymysql.err import MySQLError
from rain import get_text, process_openmeteo_rain


CONF_FILE = '/home/pi/irigatie/irigatie.conf'


def log_info(msg):
    log.info('rain_update', msg)


def log_err(msg):
    log.err('rain_update', msg)


def log_warn(msg):
    log.warning('rain_update', msg)


def read_config(path):
    config = configparser.ConfigParser()
    if not os.path.exists(path):
        raise RuntimeError('Config file not found: %s' % path)
    config.read(path)
    return config


class DatabaseConfig:
    def __init__(self, config):
        self.db_server = get_text(config, 'SQL', 'DB_SERVER', '127.0.0.1')
        self.db_port = get_text(config, 'SQL', 'DB_PORT', '3306')
        self.db_user = get_text(config, 'SQL', 'DB_USER', 'irigatie_user')
        self.db_pass = get_text(config, 'SQL', 'DB_PASS', '')
        self.db_name = get_text(config, 'SQL', 'DB_NAME', 'irigatie')


def main():
    syslog.openlog('irigatie-online-rain')

    config_path = CONF_FILE
    if len(sys.argv) > 1:
        config_path = sys.argv[1]

    config = read_config(config_path)
    notifier = manager_from_parser(config)
    database = IrrigationDatabase(DatabaseConfig(config))
    try:
        database.connect()
    except Exception:
        notifier.record_rain_import_result(False, 'Database connection failed')
        raise

    def add_rain_credit_mm(amount_mm):
        database.add_rain_credit_mm(amount_mm)

    def log_rain_event(source, amount_mm, raw_value=None, event_time=None):
        database.log_rain_event(
            source, amount_mm, raw_value, event_time, suppress_errors=False)

    def record_rain_event_with_credit(source, amount_mm, raw_value=None,
                                      event_time=None, credit_mm=0.0):
        database.record_rain_event_with_credit(
            source, amount_mm, raw_value, event_time, credit_mm)

    def report_import_status(success, detail=None):
        notifier.record_rain_import_result(success, detail)

    try:
        try:
            return process_openmeteo_rain(
                config,
                add_rain_credit_mm,
                log_info,
                log_warn,
                log_rain_event,
                record_rain_event_with_credit,
                report_import_status,
            )
        except Exception as exc:
            notifier.record_rain_import_result(False, repr(exc))
            raise
    finally:
        database.close()


if __name__ == '__main__':
    try:
        sys.exit(main())
    except MySQLError as exc:
        log_err('Database error: %r' % (exc,))
        sys.exit(2)
    except Exception as exc:
        log_err('Unexpected error: %r traceback=%s' %
                (exc, traceback.format_exc()))
        sys.exit(1)
