#!/usr/bin/python3
# -*- coding: utf-8 -*-
import getopt
import os
import socket
import sys


DEFAULT_SERVER_SOCKET = "/run/irigatie/control.sock"
STATUS_TIMEOUT_SECONDS = 5


def usage():
    print('client.py [-s <socket>] -c <comanda> -p <parametru>')
    print('client.py status')


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
        print("SEND: STATUS")
        request_status(server_socket)
        return 0

    if command == "SHUTDOWN":
        print("SEND: SHUTDOWN")
        send_command(server_socket, "SHUTDOWN")
        print("Shutting down.")
        return 0

    if command == "STOP":
        print("SEND: STOP")
        send_command(server_socket, "STOP")
        return 0

    if command == "RELOAD_SCHEDULES":
        print("SEND: RELOAD_SCHEDULES")
        send_command(server_socket, "RELOAD_SCHEDULES")
        return 0

    if command in ("START", "EXEC"):
        if not parameter:
            print("Parametru nu poate lipsi la comanda " + command)
            usage()
            return 2
        print("SEND: " + command + " " + parameter)
        send_command(server_socket, command + " " + parameter)
        return 0

    print("Comanda necunoscuta: " + command)
    usage()
    return 2


print("Connecting...")
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
        sys.exit(2)
    for opt, arg in opts:
        if opt == '-h':
            usage()
            sys.exit(2)
        elif opt in ("-c", "--command"):
            command = arg
        elif opt in ("-p", "--parameter"):
            parameter = arg
        elif opt in ("-s", "--socket"):
            server_socket = arg

if os.path.exists(server_socket):
    if command:
        sys.exit(handle_command(server_socket, command, parameter))
    elif len(sys.argv) > 1:
        usage()
        sys.exit(2)

    print("Ready.")
    print("Ctrl-C to quit.")
    print("Sending 'SHUTDOWN' shuts down the server and quits.")
    while True:
        try:
            x = input("> ").strip()
            if x != "":
                print("SEND:", x)
                if x.upper() == "STATUS":
                    request_status(server_socket)
                else:
                    send_command(server_socket, x)
                if x == "SHUTDOWN":
                    print("Shutting down.")
                    break
        except KeyboardInterrupt as k:
            print("Shutting down.")
            break
else:
    print("Couldn't Connect!")
    print("Done")
