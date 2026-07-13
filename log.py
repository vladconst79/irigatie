#!/usr/bin/python3
# -*- coding: utf-8 -*-
import syslog


def _format(category, message, fields):
    if category == 'http_access':
        return str(message)
    parts = ['[%s]' % category, str(message)]
    for key, value in fields:
        if value is not None:
            parts.append('%s=%s' % (key, value))
    return ' '.join(parts)


def write(priority, category, message, **fields):
    syslog.syslog(priority, _format(category, message, fields.items()))


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
