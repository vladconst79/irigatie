#!/usr/bin/python
# -*- coding: utf-8 -*-
import socket
import os
import sys
import getopt

print("Connecting...")
if os.path.exists("/tmp/python_irigatie_unix_socket"):
    client = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    client.connect("/tmp/python_irigatie_unix_socket")
    if len(sys.argv) > 1:
        print str(sys.argv)
        argv = sys.argv[1:]
        try:
            opts, args = getopt.getopt(argv, "hc:p:", ["command=","parameter="])
            print("opts: " + str(opts))
            print("args: " + str(args))
        except getopt.GetoptError:
            print 'client.py -c <comanda> -p <parametru>'
        for opt, arg in opts:
            if opt == '-h':
                print 'client.py -c <comanda> -p <parametru>'
                sys.exit(2)
            elif opt in ("-c", "--command"):
                comanda = arg
            elif opt in ("-p", "--parameter"):
                parametru = arg
        if comanda.upper() == "SHUTDOWN":
            print("SEND: SHUTDOWN")
            client.send("SHUTDOWN".encode('utf-8'))
            print("Shutting down.")
            sys.exit(0)
        if str(comanda).upper() == "START":
            if not parametru:
                print("Parametru nu poate lipsi la comanda START")
                print 'client.py -c <comanda> -p <parametru>'
                sys.exit(2)
            else:
                print("SEND: START " + parametru)
                client.send(("START " + parametru).encode('utf-8'))
                sys.exit(0)
        if str(comanda).upper() == "EXEC":
            if not parametru:
                print("Parametru nu poate lipsi la comanda START")
                print 'client.py -c <comanda> -p <parametru>'
                sys.exit(2)
            else:
                print("SEND: EXEC " + parametru)
                client.send(("EXEC " + parametru).encode('utf-8'))
                sys.exit(0)
    print("Ready.")
    print("Ctrl-C to quit.")
    print("Sending 'SHUTDOWN' shuts down the server and quits.")
    while True:
        try:
            x = raw_input("> ")
            if "" != x:
                print("SEND:", x)
                client.send(x.encode('utf-8'))
                if "SHUTDOWN" == x:
                    print("Shutting down.")
                    break
        except KeyboardInterrupt as k:
            print("Shutting down.")
            client.close()
            break
else:
    print("Couldn't Connect!")
    print("Done")
