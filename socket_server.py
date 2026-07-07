#!/usr/bin/python3
# -*- coding: utf-8 -*-
import json
import os
import grp
import pwd
import socket
import syslog


DEFAULT_SOCKET_PATH = '/run/irigatie/control.sock'
DEFAULT_SOCKET_MODE = 0o660


def parse_socket_command(message):
    message = message.strip()
    if '\x00' in message:
        syslog.syslog(syslog.LOG_ERR, 'Comanda invalida contine NUL')
        return None, None

    parts = message.split()
    if len(parts) == 0:
        return None, None

    command = parts[0].upper()

    if command in ('START', 'EXEC'):
        if len(parts) != 2:
            syslog.syslog(syslog.LOG_ERR, 'Comanda invalida: ' + message)
            return None, None
        if not parts[1].isdigit():
            syslog.syslog(syslog.LOG_ERR, 'Parametru invalid pentru comanda: ' + message)
            return None, None
        try:
            parameter = int(parts[1])
        except ValueError:
            syslog.syslog(syslog.LOG_ERR, 'Parametru invalid pentru comanda: ' + message)
            return None, None
        if parameter <= 0:
            syslog.syslog(syslog.LOG_ERR, 'Parametru invalid pentru comanda: ' + message)
            return None, None
        return command, parameter

    if command in ('STOP', 'SHUTDOWN', 'RELOAD_SCHEDULES', 'STATUS'):
        if len(parts) != 1:
            syslog.syslog(syslog.LOG_ERR, 'Comanda invalida: ' + message)
            return None, None
        return command, None

    syslog.syslog(syslog.LOG_ERR, 'Comanda necunoscuta: ' + message)
    return None, None


class UnixCommandServer:
    def __init__(self, path=DEFAULT_SOCKET_PATH, mode=DEFAULT_SOCKET_MODE,
                 owner=None, group=None, timeout=1.0, debug=False):
        self.path = path
        self.mode = mode
        self.owner = owner
        self.group = group
        self.timeout = timeout
        self.debug = debug
        self.server = None

    def start(self):
        directory = os.path.dirname(self.path)
        if directory and not os.path.isdir(directory):
            os.makedirs(directory, mode=0o755)
        if os.path.exists(self.path):
            os.remove(self.path)
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.server.bind(self.path)
        self._chown_socket()
        os.chmod(self.path, self.mode)
        self.server.settimeout(self.timeout)

    def _chown_socket(self):
        uid = -1
        gid = -1
        if self.owner:
            uid = pwd.getpwnam(self.owner).pw_uid
        if self.group:
            gid = grp.getgrnam(self.group).gr_gid
        if uid != -1 or gid != -1:
            os.chown(self.path, uid, gid)

    def serve(self, shutdown_requested, on_command, on_status=None):
        while not shutdown_requested.is_set():
            try:
                datagram, address = self.server.recvfrom(1024)
            except socket.timeout:
                continue
            if not datagram:
                break

            try:
                message = datagram.decode('utf-8')
            except UnicodeDecodeError:
                syslog.syslog(syslog.LOG_ERR, 'Comanda invalida: datagrama nu este UTF-8')
                continue
            if self.debug:
                print("-" * 20)
                print(message)
            command, parameter = parse_socket_command(message)
            if command is not None:
                if command == 'STATUS':
                    self.reply_status(address, on_status)
                else:
                    on_command(command, parameter, 'socket')

    def reply_status(self, address, on_status):
        if address is None:
            syslog.syslog(syslog.LOG_ERR, 'STATUS cerut fara adresa de raspuns')
            return
        if on_status is None:
            response = {
                'ok': False,
                'error': 'STATUS not supported by daemon',
            }
        else:
            try:
                response = on_status()
            except Exception as exc:
                syslog.syslog(syslog.LOG_ERR, 'Eroare STATUS: %r' % exc)
                response = {
                    'ok': False,
                    'error': 'failed to build status',
                    'detail': repr(exc),
                }
        self.server.sendto(json.dumps(response, sort_keys=True).encode('utf-8'), address)

    def close(self):
        if self.server is not None:
            self.server.close()
            self.server = None
        if os.path.exists(self.path):
            os.remove(self.path)
