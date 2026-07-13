#!/usr/bin/python3
# -*- coding: utf-8 -*-
import getopt
import os
import socket
import sys

import log


DEFAULT_SERVER_SOCKET = "/run/irigatie/control.sock"
STATUS_TIMEOUT_SECONDS = 5


def usage():
    print('client.py [-s <socket>] -c <comanda> -p <parametru>')
    print('client.py status')
    print('commands with parameter: START, EXEC, TEST')


def send_command(server_socket, command):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        client.connect(server_socket)
        client.send(command.encode('utf-8'))
    finally:
        client.close()


def request_status(server_socket):
    client_path = '/tmp/irigatie-client-%s.sock' % os.getpid()
    if os.path.exists(client_path):
        os.remove(client_path)

    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        client.bind(client_path)
        client.settimeout(STATUS_TIMEOUT_SECONDS)
        client.sendto('STATUS'.encode('utf-8'), server_socket)
        response = client.recv(65535)
        print(response.decode('utf-8'))
    finally:
        client.close()
        if os.path.exists(client_path):
            os.remove(client_path)


def handle_command(server_socket, command, parameter):
    command = command.upper()

    if command == "STATUS":
        log.info('client', 'sending command', command='STATUS')
        request_status(server_socket)
        return 0

    if command == "SHUTDOWN":
        log.info('client', 'sending command', command='SHUTDOWN')
        send_command(server_socket, "SHUTDOWN")
        log.info('client', 'shutting down')
        return 0

    if command == "STOP":
        log.info('client', 'sending command', command='STOP')
        send_command(server_socket, "STOP")
        return 0

    if command == "RELOAD_SCHEDULES":
        log.info('client', 'sending command', command='RELOAD_SCHEDULES')
        send_command(server_socket, "RELOAD_SCHEDULES")
        return 0

    if command in ("START", "EXEC", "TEST"):
        if not parameter:
            log.err('client', 'missing command parameter', command=command)
            usage()
            return 2
        log.info('client', 'sending command', command=command, parameter=parameter)
        send_command(server_socket, command + " " + parameter)
        return 0

    log.err('client', 'unknown command', command=command)
    usage()
    return 2


def main():
    log.info('client', 'connecting')
    server_socket = os.environ.get("IRIGATIE_SOCKET_PATH", DEFAULT_SERVER_SOCKET)
    command = None
    parameter = None
    if len(sys.argv) > 1:
        argv = sys.argv[1:]
        if len(argv) == 1 and argv[0].lower() == 'status':
            command = 'STATUS'
            argv = []
        try:
            opts, args = getopt.getopt(
                argv, "hc:p:s:", ["command=", "parameter=", "socket="])
        except getopt.GetoptError:
            usage()
            return 2
        for opt, arg in opts:
            if opt == '-h':
                usage()
                return 2
            elif opt in ("-c", "--command"):
                command = arg
            elif opt in ("-p", "--parameter"):
                parameter = arg
            elif opt in ("-s", "--socket"):
                server_socket = arg

    if os.path.exists(server_socket):
        if command:
            return handle_command(server_socket, command, parameter)
        elif len(sys.argv) > 1:
            usage()
            return 2

        print("Ready.")
        print("Ctrl-C to quit.")
        print("Sending 'SHUTDOWN' shuts down the server and quits.")
        while True:
            try:
                x = input("> ").strip()
                if x != "":
                    log.info('client', 'sending raw command', command=x)
                    if x.upper() == "STATUS":
                        request_status(server_socket)
                    else:
                        send_command(server_socket, x)
                    if x == "SHUTDOWN":
                        log.info('client', 'shutting down')
                        break
            except KeyboardInterrupt as k:
                log.info('client', 'shutting down')
                break
        return 0

    log.err('client', 'could not connect', socket=server_socket)
    log.info('client', 'done')
    return 1


if __name__ == '__main__':
    raise SystemExit(main())
