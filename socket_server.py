#!/usr/bin/python3
# -*- coding: utf-8 -*-
import json
import os
import socket
import syslog


DEFAULT_SOCKET_PATH = '/tmp/python_irigatie_unix_socket'


def parse_socket_command(message):
    parts = message.split()
    if len(parts) == 0:
        return None, None

    command = parts[0].upper()

    if command in ('START', 'EXEC'):
        if len(parts) != 2:
            syslog.syslog(syslog.LOG_ERR, 'Comanda invalida: ' + message)
            return None, None
        try:
            return command, int(parts[1])
        except ValueError:
            syslog.syslog(syslog.LOG_ERR, 'Parametru invalid pentru comanda: ' + message)
            return None, None

    if command in ('STOP', 'SHUTDOWN', 'RELOAD_SCHEDULES', 'STATUS'):
        return command, None

    syslog.syslog(syslog.LOG_ERR, 'Comanda necunoscuta: ' + message)
    return None, None


class UnixCommandServer:
    def __init__(self, path=DEFAULT_SOCKET_PATH, mode=0o777, timeout=1.0,
                 debug=False):
        self.path = path
        self.mode = mode
        self.timeout = timeout
        self.debug = debug
        self.server = None

    def start(self):
        if os.path.exists(self.path):
            os.remove(self.path)
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
        self.server.bind(self.path)
        os.chmod(self.path, self.mode)
        self.server.settimeout(self.timeout)

    def serve(self, shutdown_requested, on_command, on_status=None):
        while not shutdown_requested.is_set():
            try:
                datagram, address = self.server.recvfrom(1024)
            except socket.timeout:
                continue
            if not datagram:
                break

            message = str(datagram.decode('utf-8'))
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

