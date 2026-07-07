#!/usr/bin/python3
# -*- coding: utf-8 -*-
import configparser
import datetime
import json
import os
import socket
import urllib.error
import urllib.parse
import urllib.request

import log


DEFAULT_STATE_FILE = '/home/pi/irigatie/online-rain-openmeteo.json'
DEFAULT_HARDWARE_PULSE_MM = 0.2794


def should_credit_rain(source, event_source):
    if source == event_source:
        return True
    return False


def record_hardware_rain_pulse(database, rain_on, rain_source='openmeteo',
                               hardware_pulse_mm=DEFAULT_HARDWARE_PULSE_MM,
                               debug=False):
    if rain_on == 1:
        log.notice('rain_update', 'hardware rain pulse',
                   amount_mm='%.4f' % hardware_pulse_mm)
        database.log_rain_event('hardware', hardware_pulse_mm, 'pulse=1')
        if should_credit_rain(rain_source, 'hardware'):
            database.record_hardware_rain_pulse(hardware_pulse_mm)
            log.info('rain_update', 'hardware rain credited',
                     amount_mm='%.4f' % hardware_pulse_mm)
        else:
            log.info('rain_update', 'hardware rain logged only',
                     rain_source=rain_source)


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


def local_today():
    return datetime.datetime.now().date()


def fetch_date_range(past_hours):
    # Historical APIs work with full local dates, not rolling "past_hours".
    # Add one extra day buffer so last_hour filtering still works safely.
    days_back = int((past_hours + 23) / 24) + 1
    end_date = local_today()
    start_date = end_date - datetime.timedelta(days=days_back)

    return start_date.isoformat(), end_date.isoformat()


def fetch_openmeteo(latitude, longitude, timezone_name, past_hours, log_info):
    start_date, end_date = fetch_date_range(past_hours)

    params = {
        'latitude': latitude,
        'longitude': longitude,
        'hourly': 'precipitation',
        'start_date': start_date,
        'end_date': end_date,
        'timezone': timezone_name
    }

    url = 'https://historical-forecast-api.open-meteo.com/v1/forecast?' + urllib.parse.urlencode(params)

    log_info('Fetching historical rain from Open-Meteo: %s to %s' % (start_date, end_date))

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

    completion_lag_hours = 2
    safe_hour = (
            datetime.datetime.now().replace(minute=0, second=0, microsecond=0)
            - datetime.timedelta(hours=completion_lag_hours)
    )

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

        if hour_dt >= safe_hour:
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


def log_openmeteo_event(log_rain_event, rain_mm, processed_count, newest_hour,
                        credit_mm=None):
    if log_rain_event is None:
        return

    if credit_mm is None:
        raw_value = 'hours=%d;newest=%s' % (processed_count, newest_hour)
    else:
        raw_value = 'hours=%d;newest=%s;credit_mm=%.3f' % (
            processed_count, newest_hour, float(credit_mm)
        )

    log_rain_event(
        'openmeteo',
        rain_mm,
        raw_value,
        parse_hour(newest_hour),
    )


def process_openmeteo_rain(config, add_rain_credit_mm, log_info, log_warn,
                           log_rain_event=None):
    rain_source = get_text(config, 'Rain', 'SOURCE', 'openmeteo').strip().lower()
    if rain_source not in ('hardware', 'openmeteo', 'manual', 'hybrid', 'disabled'):
        log_warn('Rain SOURCE invalid: %s, using openmeteo' % rain_source)
        rain_source = 'openmeteo'

    latitude = get_float(config, 'Weather API', 'LATITUDE')
    longitude = get_float(config, 'Weather API', 'LONGITUDE')
    timezone_name = get_text(config, 'Weather API', 'TIMEZONE', 'Europe/Bucharest')
    past_hours = get_int(config, 'Weather API', 'PAST_HOURS', 30)
    min_mm = get_float(config, 'Weather API', 'MIN_MM', 0.05)
    state_file = get_text(config, 'Weather API', 'STATE_FILE', DEFAULT_STATE_FILE)

    if latitude is None or longitude is None:
        raise RuntimeError('Missing LATITUDE or LONGITUDE in [Weather API]')

    state = load_state(state_file)

    try:
        api_data = fetch_openmeteo(latitude, longitude, timezone_name, past_hours, log_info)
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
        log_openmeteo_event(
            log_rain_event,
            rain_mm,
            processed_count,
            newest_hour,
        )
        state['last_hour'] = newest_hour
        save_state(state_file, state)
        log_info('Processed %d weather hours up to %s, rain %.3f mm below threshold %.3f mm' %
                 (processed_count, newest_hour, rain_mm, min_mm))
        return 0

    credit_mm = rain_mm
    state['remainder'] = 0.0

    if credit_mm <= 0:
        log_openmeteo_event(
            log_rain_event,
            rain_mm,
            processed_count,
            newest_hour,
            credit_mm,
        )
        state['last_hour'] = newest_hour
        save_state(state_file, state)
        log_info('Processed %d weather hours up to %s, rain %.3f mm, no rain credit added' %
                 (processed_count, newest_hour, rain_mm))
        return 0

    log_openmeteo_event(
        log_rain_event,
        rain_mm,
        processed_count,
        newest_hour,
        credit_mm,
    )
    credited = False
    if should_credit_rain(rain_source, 'openmeteo'):
        add_rain_credit_mm(credit_mm)
        credited = True
    else:
        log_info('Open-Meteo rain logged only; Rain SOURCE=%s' % rain_source)

    state['last_hour'] = newest_hour
    save_state(state_file, state)

    if credited:
        log_info('Processed %d weather hours up to %s, rain %.3f mm, added %.3f mm rain credit' %
                 (processed_count, newest_hour, rain_mm, float(credit_mm)))
    else:
        log_info('Processed %d weather hours up to %s, rain %.3f mm, added 0.000 mm rain credit' %
                 (processed_count, newest_hour, rain_mm))

    return 0
