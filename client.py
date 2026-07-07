#!/usr/bin/python3
# -*- coding: utf-8 -*-
import getopt
import os
import socket
import sys


SERVER_SOCKET = "/tmp/python_irigatie_unix_socket"
STATUS_TIMEOUT_SECONDS = 5


def usage():
    print('client.py -c <comanda> -p <parametru>')


def send_command(command):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        client.connect(SERVER_SOCKET)
        client.send(command.encode('utf-8'))
    finally:
        client.close()


def request_status():
    client_path = '/tmp/irigatie-client-%s.sock' % os.getpid()
    if os.path.exists(client_path):
        os.remove(client_path)

    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        client.bind(client_path)
        client.settimeout(STATUS_TIMEOUT_SECONDS)
        client.sendto('STATUS'.encode('utf-8'), SERVER_SOCKET)
        response = client.recv(65535)
        print(response.decode('utf-8'))
    finally:
        client.close()
        if os.path.exists(client_path):
            os.remove(client_path)


def handle_command(command, parameter):
    command = command.upper()

    if command == "STATUS":
        print("SEND: STATUS")
        request_status()
        return 0

    if command == "SHUTDOWN":
        print("SEND: SHUTDOWN")
        send_command("SHUTDOWN")
        print("Shutting down.")
        return 0

    if command == "STOP":
        print("SEND: STOP")
        send_command("STOP")
        return 0

    if command == "RELOAD_SCHEDULES":
        print("SEND: RELOAD_SCHEDULES")
        send_command("RELOAD_SCHEDULES")
        return 0

    if command in ("START", "EXEC"):
        if not parameter:
            print("Parametru nu poate lipsi la comanda " + command)
            usage()
            return 2
        print("SEND: " + command + " " + parameter)
        send_command(command + " " + parameter)
        return 0

    print("Comanda necunoscuta: " + command)
    usage()
    return 2


print("Connecting...")
if os.path.exists(SERVER_SOCKET):
    if len(sys.argv) > 1:
        argv = sys.argv[1:]
        command = None
        parameter = None
        try:
            opts, args = getopt.getopt(
                argv, "hc:p:", ["command=", "parameter="])
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
        if not command:
            usage()
            sys.exit(2)
        sys.exit(handle_command(command, parameter))

    print("Ready.")
    print("Ctrl-C to quit.")
    print("Sending 'SHUTDOWN' shuts down the server and quits.")
    while True:
        try:
            x = input("> ").strip()
            if x != "":
                print("SEND:", x)
                if x.upper() == "STATUS":
                    request_status()
                else:
                    send_command(x)
                if x == "SHUTDOWN":
                    print("Shutting down.")
                    break
        except KeyboardInterrupt as k:
            print("Shutting down.")
            break
else:
    print("Couldn't Connect!")
    print("Done")
