#!/usr/bin/python3
# -*- coding: utf-8 -*-

# noinspection PyUnresolvedReferences
import configparser
import datetime
import gpiozero
import os
import pymysql
import queue
import signal
import socket
import syslog
import threading
import time
import traceback


# Deeebug
global Deeebug
Deeebug = False
# Deeebug = citeste_param('irigatie.conf', 'Deeebug', 'Deeebug')

# if Deeebug:
#     pydevd_pycharm.settrace('192.168.19.185', port=12345, stdoutToServer=True, stderrToServer=True)


def citeste_param(fisier, sectiune, param):
    config = configparser.ConfigParser()
    try:
        with open(fisier) as config_file:
            config.read_file(config_file)
    except IOError:
        if Deeebug:
            print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Fisierul ' + fisier +
                  ' nu exista!!!' + '\033[0m')
        syslog.syslog(syslog.LOG_ERR, 'Fisierul ' + fisier + 'nu exista!!!')
        return
    try:
        rez = config.getint(sectiune, param)
        if Deeebug:
            print(str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': ' + param + ' = ' + str(rez))
        syslog.syslog(param + ' = ' + str(rez))
        return rez
    except configparser.NoSectionError:
        if Deeebug:
            print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Sectiunea ' + sectiune +
                  ' nu exista!!!' + '\033[0m')
        syslog.syslog(syslog.LOG_ERR, 'Sectiunea ' + sectiune + ' nu exista!!!')
        return
    except configparser.NoOptionError:
        if Deeebug:
            print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Valoarea ' + param +
                  ' nu exista!!!' + '\033[0m')
        syslog.syslog(syslog.LOG_ERR, 'Valoarea ' + param + ' nu exista!!!')
        return


def citeste_paramtext(fisier, sectiune, param):
    config = configparser.ConfigParser()
    try:
        with open(fisier) as config_file:
            config.read_file(config_file)
    except IOError:
        if Deeebug:
            print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Fisierul ' + fisier +
                  'nu exista!!!' + '\033[0m')
        syslog.syslog(syslog.LOG_ERR, 'Fisierul ' + fisier + 'nu exista!!!')
        return
    try:
        rez = config.get(sectiune, param)
        if 'pass' in param.lower():
            syslog.syslog(param + ' = ********')
        else:
            syslog.syslog(param + ' = ' + str(rez))
        if Deeebug:
            print(str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': ' + param + ' = ' + str(rez))
        return rez
    except configparser.NoSectionError:
        if Deeebug:
            print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Sectiunea ' + sectiune +
                  ' nu exista!!!' + '\033[0m')
        syslog.syslog(syslog.LOG_ERR, 'Sectiunea ' + sectiune + ' nu exista!!!')
        return
    except configparser.NoOptionError:
        if Deeebug:
            print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Sectiunea ' + sectiune +
                  ' nu exista!!!' + '\033[0m')
        syslog.syslog(syslog.LOG_ERR, 'Valoarea ' + param + ' nu exista!!!')
        return


def ploua():
    if RAIN_ON == 1:
        if Deeebug:
            print('\033[94m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Ploua +0,25l/mp' + '\033[0m')
        syslog.syslog(syslog.LOG_NOTICE, 'Ploua +0,2794 l/mp')
        sql = 'UPDATE programari SET ploaie = ploaie + 1, zile_fp = 1;'
        conn.ping(True)
        cur.execute(sql)


def buton(channel):
    if Deeebug:
        print('\033[92m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': ' + str(channel) + ' declansat\033[0m')
        print('\033[92m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Pinul ' + str(channel.pin) + ' declansat\033[0m')
    if channel.pin.number == B_BUT1:
        but_apasat = 1
    elif channel.pin.number == B_BUT2:
        but_apasat = 2
    elif channel.pin.number == B_BUT3:
        but_apasat = 3
    elif channel.pin.number == B_BUT4:
        but_apasat = 4
    else:
        if Deeebug:
            print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
                  ': Acest buton nu este definit\033[0m')
    if Deeebug:
        print('\033[92m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Butonul ' + str(but_apasat) + ' apasat')
    syslog.syslog(syslog.LOG_NOTICE, 'Butonul ' + str(but_apasat) + ' apasat\033[0m')
    enqueue_command('EXEC', but_apasat, 'button')


def try_start_program():
    if program_lock.acquire(False):
        return True

    syslog.syslog(syslog.LOG_ERR, 'Deja ruleaza alt program')
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Deja ruleaza alt program\033[0m')
    return False


def enqueue_command(command, parameter=None, source='unknown'):
    if command in ('START', 'EXEC'):
        if controller_busy.is_set():
            syslog.syslog(syslog.LOG_ERR, 'Comanda respinsa, program activ: %s %s (%s)' %
                          (command, parameter, source))
            return False
        controller_busy.set()

    command_queue.put((command, parameter, source))
    syslog.syslog(syslog.LOG_INFO, 'Comanda acceptata: %s %s (%s)' %
                  (command, parameter, source))
    return True


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

    if command == 'SHUTDOWN':
        return command, None

    syslog.syslog(syslog.LOG_ERR, 'Comanda necunoscuta: ' + message)
    return None, None


def controller_worker():
    while not shutdown_requested.is_set():
        try:
            command, parameter, source = command_queue.get(timeout=1)
        except queue.Empty:
            continue

        try:
            if command == 'START':
                ruleaza_program(parameter)
            elif command == 'EXEC':
                program_manual(parameter)
            elif command == 'SHUTDOWN':
                shutdown_requested.set()
            else:
                syslog.syslog(syslog.LOG_ERR, 'Comanda ignorata de worker: %s %s (%s)' %
                              (command, parameter, source))
        finally:
            if command in ('START', 'EXEC'):
                controller_busy.clear()
            command_queue.task_done()


def program_manual(prg):
    if try_start_program():
        try:
            led.color = (0, 1, 0)
            if Deeebug:
                print('\033[0;33m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Porneste programul ' +
                      str(prg) + '...\033[0m')
            syslog.syslog('Porneste programul ' + str(prg))
            sql = 'SELECT * FROM progman WHERE id = ' + str(prg) + ';'
            conn.ping(True)
            cur.execute(sql)
            row = cur.fetchone()
            if P_TRAF == 'Auto':
                syslog.syslog('Porneste traful')
                if Deeebug:
                    print('\033[0;32m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Porneste traful\033[0m')
                releu_traf.on()
            zones = [
                (1, 'durata_t1', releu_1),
                (2, 'durata_t2', releu_2),
                (3, 'durata_t3', releu_3),
                (4, 'durata_t4', releu_4),
            ]
            for zone_id, duration_key, relay in zones:
                time.sleep(1)
                sql = 'SELECT * FROM trasee WHERE id = ' + str(zone_id)
                conn.ping(True)
                cur.execute(sql)
                irow = cur.fetchone()
                if irow['activ'] != 0 and row[duration_key] > 0:
                    if Deeebug:
                        print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Deschide traseul ' +
                              irow['denumire'] + '...\033[0m')
                    syslog.syslog('Deschide traseul ' + irow['denumire'])
                    relay.on()
                    try:
                        if Deeebug:
                            print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Uda timp de ' +
                                  str(row[duration_key] * 60) + ' secunde\033[0m')
                        syslog.syslog('Uda timp de ' + str(row[duration_key] * 60) + ' secunde')
                        time.sleep(row[duration_key] * 60)
                    finally:
                        if Deeebug:
                            print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Inchide traseul ' +
                                  irow['denumire'] + '...\033[0m')
                        syslog.syslog('Inchide traseul ' + irow['denumire'])
                        relay.off()
            if Deeebug:
                print('\033[0;33m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Programul ' +
                      str(prg) + ' finalizat\033[0m')
            syslog.syslog('Programul ' + str(prg) + ' finalizat')
        finally:
            force_relays_off('manual program cleanup')
            restore_transformer_mode()
            led.off()
            program_lock.release()

def ruleaza_program(prg):
    if try_start_program():
        try:
            led.color = (1, 0, 1)
            if Deeebug:
                print('\033[0;33m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Porneste programarea ' +
                      str(prg) + '...\033[0m')
            syslog.syslog('Porneste programarea ' + str(prg))
            sql = 'SELECT trasee.denumire, trasee.activ, trasee.id AS tid, programari.* FROM programari LEFT JOIN trasee ON programari.traseu_id = trasee.id WHERE programari.id = %s;' % str(prg)
            conn.ping(True)
            cur.execute(sql)
            row = cur.fetchone()
            if Deeebug:
                print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Traseu determinat > ' +
                      row['denumire'] + ' - activ: ' + str(row['activ']) + '\033[0m')
            if row['activ']:
                led.color = (1, 0, 1)
                a_releu = care_releu(int(row['tid']))
                if Deeebug:
                    print('\033[0;34m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Releu determinat > ' +
                          str(a_releu) + '...\033[0m')
                syslog.syslog(syslog.LOG_INFO, 'Precipitatii %s, maxim setat %s' % (str(row['ploaie']), str(row['max_ploaie'])))
                if row['ploaie'] < row['max_ploaie']:
                    if P_TRAF == 'Auto':
                        syslog.syslog('Porneste traful')
                        if Deeebug:
                            print('\033[0;32m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Porneste traful\033[0m')
                        releu_traf.on()
                    time.sleep(1)
                    if Deeebug:
                        print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Deschide traseul ' +
                              row['denumire'] + '...\033[0m')
                    syslog.syslog('Deschide traseul ' + row['denumire'])
                    a_releu.on()
                    try:
                        duration = (row['max_ploaie'] - row['ploaie']) / float(row['max_ploaie']) * row['durata'] * 60
                        if Deeebug:
                            print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Uda timp de ' +
                                  str(duration) + ' secunde\033[0m')
                        syslog.syslog('Uda timp de ' + str(duration) + ' secunde')
                        time.sleep(duration)
                    finally:
                        if Deeebug:
                            print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Inchide traseul ' +
                                  row['denumire'] + '...\033[0m')
                        syslog.syslog('Inchide traseul ' + row['denumire'])
                        a_releu.off()
                    time.sleep(1)
            sql = 'UPDATE programari SET ploaie = ' + str((abs(row['ploaie'] - row['max_ploaie'] * row['zile_fp']) + (row['ploaie'] - row['max_ploaie'] * row['zile_fp'])) / 2) + ', zile_fp = ' + str(row['zile_fp'] + 1) + ' WHERE traseu_id = %s;' % str(row['traseu_id'])
            conn.ping(True)
            cur.execute(sql)
            syslog.syslog('SQL reduce ploaie: ' + sql);
            if Deeebug:
                print('\033[0;33m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Programarea ' +
                      str(prg) + ' finalizata\033[0m')
            syslog.syslog('Programarea ' + str(prg) + ' finalizata')
        finally:
            force_relays_off('scheduled program cleanup')
            restore_transformer_mode()
            led.off()
            program_lock.release()

def care_releu(traseu):
    if traseu == 1:
        return releu_1
    elif traseu == 2:
        return  releu_2
    elif traseu == 3:
        return releu_3
    elif traseu == 4:
        return releu_4
    else:
        return False

def status_led(e, ts):
    while not e.is_set():
        led.color = (abs(led.red - 0.3), abs(led.green - 0.3), abs(led.blue -0.3))
        time.sleep(0.5)
        event_is_set = e.wait(ts)
        if event_is_set:
            syslog.syslog(syslog.LOG_ERR, 'Main thread intrerupt')
            if Deeebug:
                print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
                      ': Main thread intrerupt!\033[0m')
            led.off()
            if Deeebug:
                print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
                      ': Reseteaza GPIO' + str(L_RED) + ', ' + str(L_GREEN) + ', ' + str(L_BLUE) + ', LED RGB\033[0m')
            led.close()
        else:
            led.color = (not led.red, not led.green, not led.blue)
            time.sleep(0.5)

def cortina():
    syslog.syslog(syslog.LOG_INFO, 'Serverul se opreste!')
    force_relays_off('daemon shutdown')
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Reseteaza GPIO' + str(S_RAIN) + ', senzor de ploaie\033[0m')
    senzor_ploaie.close()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Reseteaza GPIO' + str(B_BUT1) + ', buton 1\033[0m')
    buton_1.close()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Reseteaza GPIO' + str(B_BUT2) + ', buton 2\033[0m')
    buton_2.close()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Reseteaza GPIO' + str(B_BUT3) + ', buton 3\033[0m')
    buton_3.close()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Reseteaza GPIO' + str(B_BUT4) + ', buton 4\033[0m')
    buton_4.close()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Reseteaza GPIO' + str(R_TRAF) + ', releu traf\033[0m')
    releu_traf.close()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Reseteaza GPIO' + str(R_IRI1) + ', releu irigatie 1\033[0m')
    releu_1.close()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Reseteaza GPIO' + str(R_IRI2) + ', releu irigatie 2\033[0m')
    releu_2.close()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Reseteaza GPIO' + str(R_IRI3) + ', releu irigatie 3\033[0m')
    releu_3.close()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Reseteaza GPIO' + str(R_IRI4) + ', releu irigatie 4\033[0m')
    releu_4.close()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Opreste LED status\033[0m')
    e.set()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Inchide cursor BD\033[0m')
    cur.close()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Inchide conexiune BD\033[0m')
    conn.close()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Inchide server socket\033[0m')
    server.close()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Sterge socket /tmp/python_irigatie_unix_socket\033[0m')
    os.remove("/tmp/python_irigatie_unix_socket")
    # sys.exit(0)

def request_shutdown(signum, frame):
    syslog.syslog(syslog.LOG_NOTICE, 'Semnal oprire primit: %s' % signum)
    shutdown_requested.set()

def force_relays_off(reason):
    relays = [
        ('traf', releu_traf),
        ('irigatie 1', releu_1),
        ('irigatie 2', releu_2),
        ('irigatie 3', releu_3),
        ('irigatie 4', releu_4),
    ]
    for name, relay in relays:
        relay.off()
        syslog.syslog(syslog.LOG_INFO, 'Opreste releu %s: %s' % (name, reason))

def restore_transformer_mode():
    if P_TRAF == 'On':
        syslog.syslog(syslog.LOG_INFO, 'Reporneste traful: mod Always ON')
        releu_traf.on()

def socks_server():
    while not shutdown_requested.is_set():
        try:
            datagram = server.recv(1024)
        except socket.timeout:
            continue
        if not datagram:
            break
        else:
            dtgdecoded = str(datagram.decode('utf-8'))
            if Deeebug:
                print("-" * 20)
                print(dtgdecoded)
            command, parameter = parse_socket_command(dtgdecoded)
            if command is not None:
                enqueue_command(command, parameter, 'socket')


### Program principal ###
print('\033[30;48;5;82m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
      ': ****** START PROGRAM ****** ' + '\033[0m')

e = threading.Event()
shutdown_requested = threading.Event()
signal.signal(signal.SIGTERM, request_shutdown)
command_queue = queue.Queue()
controller_busy = threading.Event()

# Anti paralelism
program_lock = threading.Lock()

# Citeste config
R_TRAF = citeste_param('irigatie.conf', 'ConectGPIO', 'R_TRAF')
if not R_TRAF:
    R_TRAF = 18
R_IRI1 = citeste_param('irigatie.conf', 'ConectGPIO', 'R_IRI1')
if not R_IRI1:
    R_IRI1 = 21
R_IRI2 = citeste_param('irigatie.conf', 'ConectGPIO', 'R_IRI2')
if not R_IRI2:
    R_IRI2 = 20
R_IRI3 = citeste_param('irigatie.conf', 'ConectGPIO', 'R_IRI3')
if not R_IRI3:
    R_IRI3 = 16
R_IRI4 = citeste_param('irigatie.conf', 'ConectGPIO', 'R_IRI4')
if not R_IRI4:
    R_IRI4 = 12
S_RAIN = citeste_param('irigatie.conf', 'ConectGPIO', 'S_RAIN')
if not S_RAIN:
    S_RAIN = 23
L_RED = citeste_param('irigatie.conf', 'ConectGPIO', 'L_RED')
if not L_RED:
    L_RED = 19
L_GREEN = citeste_param('irigatie.conf', 'ConectGPIO', 'L_GREEN')
if not L_GREEN:
    L_GREEN = 13
L_BLUE = citeste_param('irigatie.conf', 'ConectGPIO', 'L_BLUE')
if not L_BLUE:
    L_BLUE = 26
B_BUT1 = citeste_param('irigatie.conf', 'ConectGPIO', 'B_BUT1')
if not B_BUT1:
    B_BUT1 = 9
B_BUT2 = citeste_param('irigatie.conf', 'ConectGPIO', 'B_BUT2')
if not B_BUT2:
    B_BUT2 = 11
B_BUT3 = citeste_param('irigatie.conf', 'ConectGPIO', 'B_BUT3')
if not B_BUT3:
    B_BUT3 = 22
B_BUT4 = citeste_param('irigatie.conf', 'ConectGPIO', 'B_BUT4')
if not B_BUT4:
    B_BUT4 = 10
P_TRAF = citeste_paramtext('irigatie.conf', 'Hardware Control', 'P_TRAF')
if not P_TRAF:
    P_TRAF = 'Auto'
RAIN_ON = citeste_param('irigatie.conf', 'Hardware Control', 'RAIN_ON')
if not RAIN_ON:
    RAIN_ON = 1

# Setup GPIO
# GPIO.setmode(GPIO.BCM)
# GPIO.setwarnings(False)
# GPIO.setup([R_TRAF, R_IRI1, R_IRI2, R_IRI3, R_IRI4, L_RED, L_GREEN, L_BLUE], GPIO.OUT, initial=GPIO.LOW)
# GPIO.setup([S_RAIN, B_BUT1, B_BUT2, B_BUT3, B_BUT4], GPIO.IN, pull_up_down=GPIO.PUD_UP)

# cu gpiozero
releu_traf = gpiozero.DigitalOutputDevice(R_TRAF)
releu_1 = gpiozero.DigitalOutputDevice(R_IRI1)
releu_2 = gpiozero.DigitalOutputDevice(R_IRI2)
releu_3 = gpiozero.DigitalOutputDevice(R_IRI3)
releu_4 = gpiozero.DigitalOutputDevice(R_IRI4)
force_relays_off('daemon startup')

led = gpiozero.RGBLED(red=L_RED, green=L_GREEN, blue=L_BLUE, pwm=True)
senzor_ploaie = gpiozero.DigitalInputDevice(S_RAIN, pull_up=True)
senzor_ploaie.when_activated = ploua
buton_1 = gpiozero.Button(B_BUT1, bounce_time=0.2, pull_up=True)
buton_1.when_pressed = buton
buton_2 = gpiozero.Button(B_BUT2, bounce_time=0.2, pull_up=True)
buton_2.when_pressed = buton
buton_3 = gpiozero.Button(B_BUT3, bounce_time=0.2, pull_up=True)
buton_3.when_pressed = buton
buton_4 = gpiozero.Button(B_BUT4, bounce_time=0.2, pull_up=True)
buton_4.when_pressed = buton
if P_TRAF == 'On':
    syslog.syslog(syslog.LOG_INFO, 'Releul de traf este in mod Always ON')
    if Deeebug:
        print('\033[0;33m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Releul de traf este in mod Always ON\033[0m')
    releu_traf.on()
else:
    syslog.syslog(syslog.LOG_INFO, 'Releul de traf este in mod AUTO')
    if Deeebug:
        print('\033[0;33m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Releul de traf este in mod AUTO\033[0m')

### Config SQL ###
G_db_online = False
DB_SERVER = citeste_paramtext('irigatie.conf', 'SQL', 'DB_SERVER')
if not DB_SERVER:
    DB_SERVER = '127.0.0.1'
DB_PORT = citeste_paramtext('irigatie.conf', 'SQL', 'DB_PORT')
if not DB_PORT:
    DB_PORT = '3306'
DB_USER = citeste_paramtext('irigatie.conf', 'SQL', 'DB_USER')
if not DB_USER:
    DB_USER = 'thumpback'
DB_PASS = citeste_paramtext('irigatie.conf', 'SQL', 'DB_PASS')
if not DB_PASS:
    DB_PASS = 'hip4#staler'
DB_NAME = citeste_paramtext('irigatie.conf', 'SQL', 'DB_NAME')
if not DB_NAME:
    DB_NAME = 'irigatie'
try:
    conn = pymysql.connect(host=DB_SERVER, port=int(DB_PORT), user=DB_USER, password=DB_PASS, db=DB_NAME, autocommit=True)
    cur = conn.cursor(pymysql.cursors.DictCursor)
    conn.ping(True)
    if Deeebug:
        print(str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Conectare cu succes la baza de date, sistemul trece in modul online')
    syslog.syslog(syslog.LOG_NOTICE, 'Conectare cu succes la baza de date, sistemul trece in modul online')
    G_db_online = True
except pymysql.err.MySQLError as e:
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Eroare la conectarea la baza de date: {!r}, errno: {}\033[0m'.format(e, e.args[0]))
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Sistemul trece in modul offline' + '\033[0m')
    syslog.syslog(syslog.LOG_ERR, 'Eroare la conectarea la baza de date: {!r}, errno: {}'.format(e, e.args[0]))
    syslog.syslog(syslog.LOG_ERR, 'Sistemul trece in modul offline')
    G_db_online = False

# cu RPi.GPIO
# GPIO.add_event_detect(S_RAIN, GPIO.FALLING, callback=ploua, bouncetime=500)
# GPIO.add_event_detect(B_BUT1, GPIO.RISING, buton, bouncetime=200)
# GPIO.add_event_detect(B_BUT2, GPIO.RISING, buton, bouncetime=200)
# GPIO.add_event_detect(B_BUT3, GPIO.RISING, buton, bouncetime=200)
# GPIO.add_event_detect(B_BUT4, GPIO.RISING, buton, bouncetime=200)

# Cream socket
if os.path.exists("/tmp/python_irigatie_unix_socket"):
    os.remove("/tmp/python_irigatie_unix_socket")
server = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
server.bind("/tmp/python_irigatie_unix_socket")
os.chmod("/tmp/python_irigatie_unix_socket", 0o777)
server.settimeout(1.0)

# Thread status
ts = threading.Thread(name='non-block', target=status_led, args=(e, 2))
ts.daemon = True
ts.start()

# Thread controller
tc = threading.Thread(name='controller-worker', target=controller_worker)
tc.daemon = True
tc.start()

# Bucla infinita
try:
    # tsk = threading.Thread(target=socks_server)
    # tsk.daemon = True
    # tsk.start()
    while not shutdown_requested.is_set():
        try:
            datagram = server.recv(1024)
        except socket.timeout:
            continue
        if not datagram:
            break
        else:
            dtgdecoded = str(datagram.decode('utf-8'))
            if Deeebug:
                print("-" * 20)
                print(dtgdecoded)
            command, parameter = parse_socket_command(dtgdecoded)
            if command is not None:
                enqueue_command(command, parameter, 'socket')
    # time.sleep(1e6)
    # signal.pause()
except KeyboardInterrupt:
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Bucla intrerupta cu <CTRL>+<C>\033[0m')
    syslog.syslog(syslog.LOG_ERR, 'Bucla intrerupta cu <CTRL>+<C>')
    shutdown_requested.set()
except:
    traceback.print_exc()
finally:
    cortina()

# GPIO.cleanup()
