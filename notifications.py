#!/usr/bin/python3
# -*- coding: utf-8 -*-
import datetime
import json
import os
import smtplib
import socket
import urllib.error
import urllib.parse
import urllib.request
from email.mime.text import MIMEText

import log


DEFAULT_STATE_FILE = '/home/pi/irigatie/notification-state.json'
DEFAULT_COOLDOWN_SECONDS = 300
DEFAULT_REPEAT_SECONDS = 21600
DEFAULT_RAIN_STALE_HOURS = 6
PROBLEM_RESULTS = set([
    'interrupted',
    'failed',
    'safety_abort',
    'test_interrupted',
])


class NotificationConfig:
    def __init__(self, parser):
        self.enabled = get_bool(parser, 'Notifications', 'ENABLED', False)
        self.channels = get_channels(parser)
        self.state_file = get_text(
            parser, 'Notifications', 'STATE_FILE', DEFAULT_STATE_FILE)
        self.min_seconds_between_alerts = get_int(
            parser,
            'Notifications',
            'MIN_SECONDS_BETWEEN_ALERTS',
            DEFAULT_COOLDOWN_SECONDS,
        )
        self.repeat_active_issue_after_seconds = get_int(
            parser,
            'Notifications',
            'REPEAT_ACTIVE_ISSUE_AFTER_SECONDS',
            DEFAULT_REPEAT_SECONDS,
        )
        self.on_watering_failure = get_bool(
            parser, 'Notifications', 'ON_WATERING_FAILURE', True)
        self.on_rain_import_stale = get_bool(
            parser, 'Notifications', 'ON_RAIN_IMPORT_STALE', True)
        self.on_daemon_restart_during_watering = get_bool(
            parser,
            'Notifications',
            'ON_DAEMON_RESTART_DURING_WATERING',
            True,
        )
        self.rain_import_stale_hours = get_int(
            parser,
            'Notifications',
            'RAIN_IMPORT_STALE_HOURS',
            DEFAULT_RAIN_STALE_HOURS,
        )

        self.smtp_host = get_text(parser, 'SMTP Notifications', 'HOST', '')
        self.smtp_port = get_int(parser, 'SMTP Notifications', 'PORT', 587)
        self.smtp_starttls = get_bool(
            parser, 'SMTP Notifications', 'STARTTLS', True)
        self.smtp_username = get_text(
            parser, 'SMTP Notifications', 'USERNAME', '')
        self.smtp_password = get_text(
            parser, 'SMTP Notifications', 'PASSWORD', '')
        self.smtp_from = get_text(parser, 'SMTP Notifications', 'FROM', '')
        self.smtp_to = get_text(parser, 'SMTP Notifications', 'TO', '')

        self.callmebot_phone = get_text(parser, 'CallMeBot', 'PHONE', '')
        self.callmebot_api_key = get_text(parser, 'CallMeBot', 'API_KEY', '')

        self.validate()

    def validate(self):
        if self.min_seconds_between_alerts < 0:
            self.min_seconds_between_alerts = DEFAULT_COOLDOWN_SECONDS
        if self.repeat_active_issue_after_seconds < 0:
            self.repeat_active_issue_after_seconds = DEFAULT_REPEAT_SECONDS
        if self.rain_import_stale_hours <= 0:
            self.rain_import_stale_hours = DEFAULT_RAIN_STALE_HOURS


class NotificationManager:
    def __init__(self, config):
        self.config = config
        self.state = load_state(config.state_file)

    def notify_issue(self, key, title, message, fields=None, repeatable=True):
        if not self.config.enabled:
            return False
        if fields is None:
            fields = {}

        now = datetime.datetime.now().replace(microsecond=0)
        entry = self.state.get(key) or {
            'first_seen_at': format_ts(now),
            'count': 0,
        }
        entry['last_seen_at'] = format_ts(now)
        entry['resolved_at'] = None
        entry['count'] = int(entry.get('count') or 0) + 1

        last_notified_at = parse_ts(entry.get('last_notified_at'))
        should_send = last_notified_at is None
        if last_notified_at is not None:
            seconds_since = (now - last_notified_at).total_seconds()
            if seconds_since >= self.config.min_seconds_between_alerts:
                if repeatable and seconds_since >= self.config.repeat_active_issue_after_seconds:
                    should_send = True

        self.state[key] = entry
        if not should_send:
            save_state(self.config.state_file, self.state)
            log.info('notification', 'suppressed duplicate alert', key=key)
            return False

        body = format_body(message, fields)
        sent = self.send(title, body)
        if sent:
            entry['last_notified_at'] = format_ts(now)
            self.state[key] = entry
            save_state(self.config.state_file, self.state)
            log.notice('notification', 'alert sent', key=key, title=title)
            return True

        save_state(self.config.state_file, self.state)
        return False

    def resolve_issue(self, key):
        entry = self.state.get(key)
        if entry is None or entry.get('resolved_at'):
            return
        entry['resolved_at'] = format_ts(datetime.datetime.now())
        self.state[key] = entry
        save_state(self.config.state_file, self.state)

    def notify_watering_problem(self, source, program_id, zone_id, result,
                                error=None):
        if not self.config.on_watering_failure:
            return False
        key = 'watering_problem:%s:%s:%s:%s' % (
            safe_key(source), safe_key(program_id), safe_key(zone_id),
            safe_key(result)
        )
        return self.notify_issue(
            key,
            'Irigatie watering problem',
            'Watering ended with result %s.' % result,
            {
                'source': source,
                'program_id': program_id,
                'zone_id': zone_id,
                'result': result,
                'error': error,
            },
            repeatable=True,
        )

    def notify_daemon_restart_during_watering(self, runtime_state):
        if not self.config.on_daemon_restart_during_watering:
            return False
        key = 'daemon_restart_during_watering:%s:%s:%s' % (
            safe_key(runtime_state.get('source')),
            safe_key(runtime_state.get('program_id')),
            safe_key(runtime_state.get('traseu_id')),
        )
        return self.notify_issue(
            key,
            'Irigatie restarted during watering',
            'Daemon startup found a previous running watering state.',
            {
                'source': runtime_state.get('source'),
                'command': runtime_state.get('command'),
                'program_id': runtime_state.get('program_id'),
                'zone_id': runtime_state.get('traseu_id'),
                'started_at': runtime_state.get('started_at'),
                'expected_end_at': runtime_state.get('expected_end_at'),
            },
            repeatable=False,
        )

    def record_rain_import_result(self, success, detail=None):
        if not self.config.enabled:
            return False
        now = datetime.datetime.now().replace(microsecond=0)
        key = 'rain_import_stale'
        if success:
            self.state['rain_import_last_success_at'] = format_ts(now)
            self.state['rain_import_last_detail'] = detail
            if 'rain_import_first_failure_at' in self.state:
                del self.state['rain_import_first_failure_at']
            self.resolve_issue(key)
            save_state(self.config.state_file, self.state)
            return False

        self.state['rain_import_last_failure_at'] = format_ts(now)
        self.state['rain_import_last_detail'] = detail
        if not self.state.get('rain_import_first_failure_at'):
            self.state['rain_import_first_failure_at'] = format_ts(now)
        last_success_at = parse_ts(self.state.get('rain_import_last_success_at'))
        if last_success_at is None:
            first_failure_at = parse_ts(self.state.get('rain_import_first_failure_at'))
            age_hours = (now - first_failure_at).total_seconds() / 3600.0
            stale = age_hours >= self.config.rain_import_stale_hours
        else:
            age_hours = (now - last_success_at).total_seconds() / 3600.0
            stale = age_hours >= self.config.rain_import_stale_hours
        save_state(self.config.state_file, self.state)

        if not stale or not self.config.on_rain_import_stale:
            return False

        return self.notify_issue(
            key,
            'Irigatie Open-Meteo import stale',
            'Open-Meteo rain import has not succeeded recently.',
            {
                'last_success_at': format_ts(last_success_at),
                'stale_after_hours': self.config.rain_import_stale_hours,
                'age_hours': 'unknown' if age_hours is None else '%.2f' % age_hours,
                'detail': detail,
            },
            repeatable=True,
        )

    def send(self, title, body):
        sent = False
        if 'smtp' in self.config.channels:
            sent = self.send_smtp(title, body) or sent
        if 'callmebot' in self.config.channels:
            sent = self.send_callmebot(title, body) or sent
        return sent

    def send_smtp(self, title, body):
        if not self.config.smtp_host or not self.config.smtp_to:
            log.warning('notification', 'SMTP notification not configured')
            return False
        sender = self.config.smtp_from or self.config.smtp_username
        if not sender:
            log.warning('notification', 'SMTP sender not configured')
            return False

        msg = MIMEText(body, 'plain', 'utf-8')
        msg['Subject'] = title
        msg['From'] = sender
        msg['To'] = self.config.smtp_to
        recipients = [
            item.strip()
            for item in self.config.smtp_to.split(',')
            if item.strip()
        ]
        try:
            server = smtplib.SMTP(
                self.config.smtp_host, self.config.smtp_port, timeout=15)
            try:
                if self.config.smtp_starttls:
                    server.starttls()
                if self.config.smtp_username:
                    server.login(
                        self.config.smtp_username,
                        self.config.smtp_password,
                    )
                server.sendmail(sender, recipients, msg.as_string())
            finally:
                server.quit()
            return True
        except Exception as exc:
            log.err('notification', 'SMTP notification failed',
                    error=repr(exc))
            return False

    def send_callmebot(self, title, body):
        if not self.config.callmebot_phone or not self.config.callmebot_api_key:
            log.warning('notification', 'CallMeBot notification not configured')
            return False
        text = '%s\n\n%s' % (title, body)
        params = urllib.parse.urlencode({
            'phone': self.config.callmebot_phone,
            'text': text,
            'apikey': self.config.callmebot_api_key,
        })
        url = 'https://api.callmebot.com/whatsapp.php?' + params
        try:
            response = urllib.request.urlopen(url, timeout=15)
            try:
                response.read()
            finally:
                response.close()
            return True
        except (urllib.error.URLError, socket.timeout, Exception) as exc:
            log.err('notification', 'CallMeBot notification failed',
                    error=repr(exc))
            return False


def manager_from_parser(parser):
    return NotificationManager(NotificationConfig(parser))


def disabled_manager():
    return NotificationManager(NotificationConfig(EmptyParser()))


class EmptyParser:
    def get(self, section, option):
        raise KeyError()

    def getint(self, section, option):
        raise KeyError()

    def getboolean(self, section, option):
        raise KeyError()


def get_text(parser, section, option, default=''):
    try:
        return parser.get(section, option).strip()
    except Exception:
        return default


def get_int(parser, section, option, default=0):
    try:
        return parser.getint(section, option)
    except Exception:
        return default


def get_bool(parser, section, option, default=False):
    try:
        return parser.getboolean(section, option)
    except Exception:
        return default


def get_channels(parser):
    value = get_text(parser, 'Notifications', 'CHANNELS', '')
    channels = []
    for item in value.split(','):
        item = item.strip().lower()
        if item in ('smtp', 'callmebot'):
            channels.append(item)
    return channels


def load_state(path):
    if not os.path.exists(path):
        return {}
    try:
        fh = open(path, 'r')
        try:
            data = fh.read().strip()
        finally:
            fh.close()
        if not data:
            return {}
        return json.loads(data)
    except Exception as exc:
        log.err('notification', 'failed to load notification state',
                path=path, error=repr(exc))
        return {}


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


def format_ts(value):
    if value is None:
        return None
    if isinstance(value, datetime.datetime):
        return value.strftime('%Y-%m-%d %H:%M:%S')
    return str(value)


def parse_ts(value):
    if not value:
        return None
    if isinstance(value, datetime.datetime):
        return value
    try:
        return datetime.datetime.strptime(str(value), '%Y-%m-%d %H:%M:%S')
    except ValueError:
        return None


def format_body(message, fields):
    lines = [message]
    for key in sorted(fields.keys()):
        value = fields[key]
        if value is not None:
            lines.append('%s: %s' % (key, format_ts(value)))
    return '\n'.join(lines)


def safe_key(value):
    if value is None:
        return 'none'
    return str(value).replace(':', '_').replace(' ', '_')
