#!/usr/bin/python
# noinspection PyUnresolvedReferences
# import RPi.GPIO as GPIO
import ConfigParser
import datetime
import gpiozero
import os
import pymysql
import signal
import socket
import syslog
import threading
import time
from pymysql.err import MySQLError


def citeste_param(fisier, sectiune, param):
    config = ConfigParser.ConfigParser()
    try:
        config.readfp(open(fisier))
    except IOError:
        if Deeebug:
            print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Fisierul ' + fisier +
                  'nu exista!!!' + '\033[0m')
        syslog.syslog(syslog.LOG_ERR, 'Fisierul ' + fisier + 'nu exista!!!')
        return
    try:
        rez = config.getint(sectiune, param)
        if Deeebug:
            print(str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': ' + param + ' = ' + str(rez))
        syslog.syslog(param + ' = ' + str(rez))
        return rez
    except ConfigParser.NoSectionError:
        if Deeebug:
            print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Sectiunea ' + sectiune +
                  ' nu exista!!!' + '\033[0m')
        syslog.syslog(syslog.LOG_ERR, 'Sectiunea ' + sectiune + ' nu exista!!!')
        return
    except ConfigParser.NoOptionError:
        if Deeebug:
            print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Valoarea ' + param +
                  ' nu exista!!!' + '\033[0m')
        syslog.syslog(syslog.LOG_ERR, 'Valoarea ' + param + ' nu exista!!!')
        return


def citeste_paramtext(fisier, sectiune, param):
    config = ConfigParser.ConfigParser()
    try:
        config.readfp(open(fisier))
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
    except ConfigParser.NoSectionError:
        if Deeebug:
            print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Sectiunea ' + sectiune +
                  ' nu exista!!!' + '\033[0m')
        syslog.syslog(syslog.LOG_ERR, 'Sectiunea ' + sectiune + ' nu exista!!!')
        return
    except ConfigParser.NoOptionError:
        if Deeebug:
            print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Sectiunea ' + sectiune +
                  ' nu exista!!!' + '\033[0m')
        syslog.syslog(syslog.LOG_ERR, 'Valoarea ' + param + ' nu exista!!!')
        return


def ploua():
    if Deeebug:
        print('\033[94m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Ploua +0,25l/mp' + '\033[0m')
    syslog.syslog(syslog.LOG_NOTICE, 'Ploua +0,2794 l/mp')
    sql = 'UPDATE programari SET ploaie = ploaie + 1;'
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
    ti = threading.Thread(target=program_manual, args=[but_apasat])
    ti.daemon = True
    ti.start()


def program_manual(prg):
    led.color = (0, 1, 0)
    if Deeebug:
        print('\033[0;33m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Porneste programul ' +
              str(prg) + '...\033[0m')
    syslog.syslog('Porneste programul ' + str(prg))
    sql = 'SELECT * FROM progman WHERE id = ' + str(prg) + ';'
    cur.execute(sql)
    row = cur.fetchone()
    # GPIO.output(R_TRAF, GPIO.HIGH)
    releu_traf.on()
    time.sleep(1)
    sql = 'SELECT * FROM trasee WHERE id = 1'
    cur.execute(sql)
    irow = cur.fetchone()
    if irow['activ'] != 0 and row['durata_t1'] > 0:
        if Deeebug:
            print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Deschide traseul ' +
                  irow['denumire'] + '...\033[0m')
        syslog.syslog('Deschide traseul ' + irow['denumire'])
        # GPIO.output(R_IRI1, GPIO.HIGH)
        releu_1.on()
        time.sleep(row['durata_t1'] * 60)
        if Deeebug:
            print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Inchide traseul ' +
                  irow['denumire'] + '...\033[0m')
        syslog.syslog('Inchide traseul ' + irow['denumire'])
        # GPIO.output(R_IRI1, GPIO.LOW)
        releu_1.off()
    time.sleep(1)
    sql = 'SELECT * FROM trasee WHERE id = 2'
    cur.execute(sql)
    irow = cur.fetchone()
    if irow['activ'] != 0 and row['durata_t2'] > 0:
        if Deeebug:
            print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Deschide traseul ' +
                  irow['denumire'] + '...\033[0m')
        syslog.syslog('Deschide traseul ' + irow['denumire'])
        # GPIO.output(R_IRI2, GPIO.HIGH)
        releu_2.on()
        time.sleep(row['durata_t2'] * 60)
        if Deeebug:
            print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Inchide traseul ' +
                  irow['denumire'] + '...\033[0m')
        syslog.syslog('Inchide traseul ' + irow['denumire'])
        # GPIO.output(R_IRI2, GPIO.LOW)
        releu_2.off()
    time.sleep(1)
    sql = 'SELECT * FROM trasee WHERE id = 3'
    cur.execute(sql)
    irow = cur.fetchone()
    if irow['activ'] != 0 and row['durata_t3'] > 0:
        if Deeebug:
            print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Deschide traseul ' +
                  irow['denumire'] + '...\033[0m')
        syslog.syslog('Deschide traseul ' + irow['denumire'])
        # GPIO.output(R_IRI3, GPIO.HIGH)
        releu_3.on()
        time.sleep(row['durata_t3'] * 60)
        if Deeebug:
            print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Inchide traseul ' +
                  irow['denumire'] + '...\033[0m')
        syslog.syslog('Inchide traseul ' + irow['denumire'])
        # GPIO.output(R_IRI3, GPIO.LOW)
        releu_3.off()
    time.sleep(1)
    sql = 'SELECT * FROM trasee WHERE id = 4'
    cur.execute(sql)
    irow = cur.fetchone()
    if irow['activ'] != 0 and row['durata_t4'] > 0:
        if Deeebug:
            print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Deschide traseul ' +
                  irow['denumire'] + '...\033[0m')
        syslog.syslog('Deschide traseul ' + irow['denumire'])
        # GPIO.output(R_IRI4, GPIO.HIGH)
        releu_4.on()
        time.sleep(row['durata_t4'] * 60)
        if Deeebug:
            print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Inchide traseul ' +
                  irow['denumire'] + '...\033[0m')
        syslog.syslog('Inchide traseul ' + irow['denumire'])
        # GPIO.output(R_IRI4, GPIO.LOW)
        releu_4.off()
    time.sleep(1)
    # GPIO.output(R_TRAF, GPIO.LOW)
    releu_traf.off()
    led.off()

def ruleaza_program(prg):
    led.color = (1, 0, 1)
    sql = 'SELECT trasee.denumire, trasee.activ, trasee.id AS tid, programari.* FROM programari LEFT JOIN trasee ON ' \
          'programari.traseu_id = trasee.id WHERE programari.id = %s;' % str(prg)
    if Deeebug:
        print(str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': SQL>>> ' + sql)
    cur.execute(sql)
    row = cur.fetchone()
    if Deeebug:
        print('\033[0;33m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Porneste programarea ' +
              str(prg) + '...\033[0m')
    syslog.syslog('Porneste programarea ' + str(prg))
    if row['activ']:
        led.color = (1, 0, 1)
        a_releu = care_releu(row['tid'])
        if not a_releu and row['ploaie'] < row['max_ploaie']:
            releu_traf.on()
            time.sleep(1)
            if Deeebug:
                print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Deschide traseul ' +
                      row['denumire'] + '...\033[0m')
            syslog.syslog('Deschide traseul ' + row['denumire'])
            a_releu.on()
            time.sleep((row['max_ploaie'] - row['durata']) / row['max_ploaie'] * 60)
            if Deeebug:
                print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Inchide traseul ' +
                      row['denumire'] + '...\033[0m')
            syslog.syslog('Inchide traseul ' + row['denumire'])
            a_releu.off()
            time.sleep(1)
            releu_traf.off()
        led.off()
    sql = 'UPDATE programari SET ploaie = 0 WHERE id = %s;' % str(prg)
    cur.execute(sql)

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

def cortina():
    senzor_ploaie.close()
    buton_1.close()
    buton_2.close()
    buton_3.close()
    buton_4.close()
    releu_traf.close()
    releu_1.close()
    releu_2.close()
    releu_3.close()
    releu_4.close()
    led.close()
    cur.close()
    conn.close()
    server.close()
    os.remove("/tmp/python_irigatie_unix_socket")


### Program principal ###
print('\033[30;48;5;82m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
      ' ****** START PROGRAM ****** ' + '\033[0m')

# Deeebug
global Deeebug
Deeebug = False
Deeebug = citeste_param('irigatie.conf', 'Deeebug', 'Deeebug')

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

# Setup GPIO
# GPIO.setmode(GPIO.BCM)
# GPIO.setwarnings(False)
# GPIO.setup([R_TRAF, R_IRI1, R_IRI2, R_IRI3, R_IRI4, L_RED, L_GREEN, L_BLUE], GPIO.OUT, initial=GPIO.LOW)
# GPIO.setup([S_RAIN, B_BUT1, B_BUT2, B_BUT3, B_BUT4], GPIO.IN, pull_up_down=GPIO.PUD_UP)

# cu gpiozero
senzor_ploaie = gpiozero.DigitalInputDevice(S_RAIN, pull_up=True)
senzor_ploaie.when_activated = ploua
buton_1 = gpiozero.Button(B_BUT1, bounce_time=200)
buton_1.when_pressed = buton
buton_2 = gpiozero.Button(B_BUT2, bounce_time=200)
buton_2.when_pressed = buton
buton_3 = gpiozero.Button(B_BUT3, bounce_time=200)
buton_3.when_pressed = buton
buton_4 = gpiozero.Button(B_BUT4, bounce_time=200)
buton_4.when_pressed = buton
led = gpiozero.RGBLED(red=L_RED, green=L_GREEN, blue=L_BLUE)
releu_traf = gpiozero.DigitalOutputDevice(R_TRAF)
releu_1 = gpiozero.DigitalOutputDevice(R_IRI1)
releu_2 = gpiozero.DigitalOutputDevice(R_IRI2)
releu_3 = gpiozero.DigitalOutputDevice(R_IRI3)
releu_4 = gpiozero.DigitalOutputDevice(R_IRI4)

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
    conn = pymysql.connect(host=DB_SERVER, user=DB_USER, password=DB_PASS, db=DB_NAME, autocommit=True)
    cur = conn.cursor(pymysql.cursors.DictCursor)
    if Deeebug:
        print(str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Conectare cu succes la baza de date, sistemul trece in modul online')
    syslog.syslog(syslog.LOG_NOTICE, 'Conectare cu succes la baza de date, sistemul trece in modul online')
    G_db_online = True
except MySQLError as e:
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
server =  socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
server.bind("/tmp/python_irigatie_unix_socket")

# Bucla infinita
try:
    while True:
        datagram = server.recv(1024)
        if not datagram:
            break
        else:
            dtgdecoded = str(datagram.decode('utf-8'))
            if Deeebug:
                print("-" * 20)
                print(dtgdecoded)
                print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + '[0:5]>>> ' +
                      dtgdecoded[0:5] + '\033[0m')
                print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + '[6]>>>>> ' +
                      dtgdecoded[6] + '\033[0m')
            if dtgdecoded[0:5] == "START":
                tp = threading.Thread(target=ruleaza_program, args=[int(dtgdecoded[6])])
                tp.daemon = True
                tp.start()
            if dtgdecoded == "SHUTDOWN":
                cortina()
                break
        # time.sleep(1e6)
        # signal.pause()
except KeyboardInterrupt:
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Bucla intrerupta cu <CTRL>+<C>\033[0m')
    syslog.syslog(syslog.LOG_ERR, 'Bucla intrerupta cu <CTRL>+<C>')
    cortina()

# GPIO.cleanup()
