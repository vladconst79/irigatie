#!/usr/bin/python3
# -*- coding: utf-8 -*-

import configparser
import os
import sys
import syslog
import traceback

from db import IrrigationDatabase
from pymysql.err import MySQLError
from rain import get_text, process_openmeteo_rain


CONF_FILE = '/home/pi/irigatie/irigatie.conf'


def log_info(msg):
    syslog.syslog(syslog.LOG_INFO, msg)
    print('INFO: ' + msg)


def log_err(msg):
    syslog.syslog(syslog.LOG_ERR, msg)
    print('ERROR: ' + msg, file=sys.stderr)

def log_warn(msg):
    syslog.syslog(syslog.LOG_WARNING, msg)
    print('WARNING: ' + msg)

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
    def add_rain_units(rain_units):
        database = IrrigationDatabase(DatabaseConfig(config))
        try:
            database.connect()
            database.add_rain_units(rain_units)
        finally:
            database.close()

    return process_openmeteo_rain(
        config,
        add_rain_units,
        log_info,
        log_warn,
    )


if __name__ == '__main__':
    try:
        sys.exit(main())
    except MySQLError as exc:
        log_err('Database error: %r' % (exc,))
        sys.exit(2)
    except Exception as exc:
        log_err('Unexpected error: %r' % (exc,))
        traceback.print_exc()
        sys.exit(1)
