#!/usr/bin/python3
# -*- coding: utf-8 -*-

import configparser
import datetime
import json
import os
import sys
import syslog
import traceback
import urllib.parse
import urllib.request
import socket
import urllib.error

import pymysql
from pymysql.err import MySQLError


CONF_FILE = '/home/pi/irigatie/irigatie.conf'
DEFAULT_STATE_FILE = '/home/pi/irigatie/online-rain-openmeteo.json'


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


def get_text(config, section, option, default=None):
    try:
        return config.get(section, option)
    except configparser.Error:
        return default


def get_int(config, section, option, default=None):
    try:
        return config.getint(section, option)
    except configparser.Error:
        return default


def get_float(config, section, option, default=None):
    try:
        return config.getfloat(section, option)
    except configparser.Error:
        return default


def get_bool(config, section, option, default=False):
    try:
        return config.getboolean(section, option)
    except configparser.Error:
        return default


def parse_hour(value):
    return datetime.datetime.strptime(value, '%Y-%m-%dT%H:%M')


def format_hour(value):
    return value.strftime('%Y-%m-%dT%H:%M')


def load_state(path):
    if not os.path.exists(path):
        return {
            'last_hour': None,
            'remainder': 0.0
        }

    fh = open(path, 'r')
    try:
        data = fh.read().strip()
    finally:
        fh.close()

    if not data:
        return {
            'last_hour': None,
            'remainder': 0.0
        }

    try:
        parsed = json.loads(data)
        return {
            'last_hour': parsed.get('last_hour'),
            'remainder': float(parsed.get('remainder', 0.0))
        }
    except ValueError:
        return {
            'last_hour': data,
            'remainder': 0.0
        }


def save_state(path, state):
    directory = os.path.dirname(path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

    tmp_path = path + '.tmp'
    fh = open(tmp_path, 'w')
    try:
        fh.write(json.dumps(state, sort_keys=True, indent=2))
        fh.write('\n')
    finally:
        fh.close()

    os.rename(tmp_path, path)


def fetch_openmeteo(latitude, longitude, timezone_name, past_hours):
    params = {
        'latitude': latitude,
        'longitude': longitude,
        'hourly': 'precipitation',
        'past_hours': past_hours,
        'forecast_hours': 1,
        'timezone': timezone_name
    }

    url = 'https://api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(params)

    req = urllib.request.Request(url)
    req.add_header('User-Agent', 'irigatie-online-rain/1.0 vlad@shaitan.ro')

    response = urllib.request.urlopen(req, timeout=30)
    try:
        body = response.read()
    finally:
        response.close()

    return json.loads(body.decode('utf-8'))


def sum_new_completed_rain_mm(api_data, last_hour):
    hourly = api_data.get('hourly', {})
    times = hourly.get('time', [])
    precipitation = hourly.get('precipitation', [])

    if len(times) != len(precipitation):
        raise RuntimeError('Open-Meteo response has mismatched time/precipitation arrays')

    now_hour = datetime.datetime.now().replace(minute=0, second=0, microsecond=0)

    if last_hour:
        last_dt = parse_hour(last_hour)
    else:
        last_dt = None

    total_mm = 0.0
    newest_processed = last_hour
    processed_count = 0

    for idx in range(len(times)):
        hour_text = times[idx]
        hour_dt = parse_hour(hour_text)

        if hour_dt >= now_hour:
            continue

        if last_dt is not None and hour_dt <= last_dt:
            continue

        value = precipitation[idx]
        if value is None:
            value = 0.0

        total_mm += float(value)
        newest_processed = hour_text
        processed_count += 1

    return total_mm, newest_processed, processed_count


def connect_db(config):
    db_server = get_text(config, 'SQL', 'DB_SERVER', '127.0.0.1')
    db_port = int(get_text(config, 'SQL', 'DB_PORT', '3306'))
    db_user = get_text(config, 'SQL', 'DB_USER', 'thumpback')
    db_pass = get_text(config, 'SQL', 'DB_PASS', 'hip4#staler')
    db_name = get_text(config, 'SQL', 'DB_NAME', 'irigatie')

    return pymysql.connect(
        host=db_server,
        port=db_port,
        user=db_user,
        password=db_pass,
        db=db_name,
        autocommit=True
    )


def update_rain_db(conn, rain_units):
    sql = 'UPDATE programari SET ploaie = ploaie + %s, zile_fp = 1;'

    cur = conn.cursor()
    try:
        cur.execute(sql, (rain_units,))
    finally:
        cur.close()


def describe_url_error(exc):
    reason = getattr(exc, 'reason', None)

    if isinstance(reason, OSError):
        errno_value = getattr(reason, 'errno', None)
        strerror = getattr(reason, 'strerror', None)

        if errno_value is not None and strerror:
            return 'network error: errno %s, %s' % (errno_value, strerror)

        return 'network error: %r' % (reason,)

    if isinstance(reason, socket.timeout):
        return 'network timeout'

    if reason is not None:
        return 'url error: %r' % (reason,)

    return 'url error: %r' % (exc,)


def main():
    syslog.openlog('irigatie-online-rain')

    config_path = CONF_FILE
    if len(sys.argv) > 1:
        config_path = sys.argv[1]

    config = read_config(config_path)

    latitude = get_float(config, 'Weather API', 'LATITUDE')
    longitude = get_float(config, 'Weather API', 'LONGITUDE')
    timezone_name = get_text(config, 'Weather API', 'TIMEZONE', 'Europe/Bucharest')
    past_hours = get_int(config, 'Weather API', 'PAST_HOURS', 30)
    mm_per_pulse = get_float(config, 'Weather API', 'MM_PER_PULSE', 0.2794)
    min_mm = get_float(config, 'Weather API', 'MIN_MM', 0.05)
    round_pulses = get_bool(config, 'Weather API', 'ROUND_PULSES', False)
    state_file = get_text(config, 'Weather API', 'STATE_FILE', DEFAULT_STATE_FILE)

    if latitude is None or longitude is None:
        raise RuntimeError('Missing LATITUDE or LONGITUDE in [Weather API]')

    if mm_per_pulse <= 0:
        raise RuntimeError('MM_PER_PULSE must be greater than zero')

    state = load_state(state_file)

    # api_data = fetch_openmeteo(latitude, longitude, timezone_name, past_hours)

    try:
        api_data = fetch_openmeteo(latitude, longitude, timezone_name, past_hours)
    except urllib.error.HTTPError as exc:
        log_warn('Open-Meteo HTTP error: status %s, reason %s' %
                 (getattr(exc, 'code', 'unknown'), getattr(exc, 'reason', 'unknown')))
        return 0
    except urllib.error.URLError as exc:
        log_warn('Open-Meteo unavailable: %s' % describe_url_error(exc))
        return 0
    except socket.timeout:
        log_warn('Open-Meteo unavailable: request timed out')
        return 0
    except ValueError as exc:
        log_warn('Open-Meteo returned invalid JSON: %r' % (exc,))
        return 0

    rain_mm, newest_hour, processed_count = sum_new_completed_rain_mm(
        api_data,
        state.get('last_hour')
    )

    if newest_hour is None or processed_count == 0:
        log_info('No new completed weather hours to process')
        return 0

    if rain_mm < min_mm:
        state['last_hour'] = newest_hour
        save_state(state_file, state)
        log_info('Processed %d hours, rain %.3f mm below threshold %.3f mm' %
                 (processed_count, rain_mm, min_mm))
        return 0

    rain_units = rain_mm / mm_per_pulse

    if round_pulses:
        total_units = rain_units + float(state.get('remainder', 0.0))
        add_units = int(total_units)
        state['remainder'] = total_units - add_units
    else:
        add_units = rain_units
        state['remainder'] = 0.0

    if add_units <= 0:
        state['last_hour'] = newest_hour
        save_state(state_file, state)
        log_info('Processed %d hours, rain %.3f mm, accumulated remainder only' %
                 (processed_count, rain_mm))
        return 0

    conn = None
    try:
        conn = connect_db(config)
        update_rain_db(conn, add_units)
    finally:
        if conn is not None:
            conn.close()

    state['last_hour'] = newest_hour
    save_state(state_file, state)

    log_info('Processed %d hours, rain %.3f mm, added %.3f rain units, newest hour %s' %
             (processed_count, rain_mm, float(add_units), newest_hour))

    return 0


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
