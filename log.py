#!/usr/bin/python3
# -*- coding: utf-8 -*-
import os
import sys
import syslog


def running_as_service():
    return bool(os.environ.get('INVOCATION_ID') or os.environ.get('JOURNAL_STREAM'))


def _format(category, message, fields):
    if category == 'http_access':
        return str(message)
    parts = ['[%s]' % category, str(message)]
    for key, value in fields:
        if value is not None:
            parts.append('%s=%s' % (key, value))
    return ' '.join(parts)


def write(priority, category, message, **fields):
    formatted = _format(category, message, fields.items())
    if running_as_service():
        syslog.syslog(priority, formatted)
        return
    stream = sys.stderr if priority <= syslog.LOG_WARNING else sys.stdout
    print(formatted, file=stream)


def debug(enabled, category, message, **fields):
    if enabled:
        write(syslog.LOG_DEBUG, category, message, **fields)


def info(category, message, **fields):
    write(syslog.LOG_INFO, category, message, **fields)


def notice(category, message, **fields):
    write(syslog.LOG_NOTICE, category, message, **fields)


def warning(category, message, **fields):
    write(syslog.LOG_WARNING, category, message, **fields)


def err(category, message, **fields):
    write(syslog.LOG_ERR, category, message, **fields)
