#!/usr/bin/python3
# -*- coding: utf-8 -*-

import datetime
import pymysql
import signal
import syslog
import threading
import traceback

from config import load_config
from controller import IrrigationController
from db import IrrigationDatabase
from gpio_hw import GpioHardware
from rain import record_hardware_rain_pulse
from socket_server import UnixCommandServer


# Deeebug
global Deeebug
Deeebug = False
# Deeebug = load_config('irigatie.conf', True).get_int('Deeebug', 'Deeebug', 0)

# if Deeebug:
#     pydevd_pycharm.settrace('192.168.19.185', port=12345, stdoutToServer=True, stderrToServer=True)


def ploua():
    record_hardware_rain_pulse(
        database,
        RAIN_ON,
        cfg.rain_source,
        cfg.hardware_pulse_mm,
        Deeebug,
    )


def buton(but_apasat):
    if Deeebug:
        print('\033[92m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Butonul ' + str(but_apasat) + ' declansat\033[0m')
    if Deeebug:
        print('\033[92m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Butonul ' + str(but_apasat) + ' apasat')
    syslog.syslog(syslog.LOG_NOTICE, 'Butonul ' + str(but_apasat) + ' apasat\033[0m')
    controller.enqueue_command('EXEC', but_apasat, 'button')

def status_led(e, ts):
    hardware.status_led_loop(e, ts)

def cortina():
    syslog.syslog(syslog.LOG_INFO, 'Serverul se opreste!')
    force_relays_off('daemon shutdown')
    hardware.close()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Opreste LED status\033[0m')
    e.set()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Inchide cursor BD\033[0m')
    database.close()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Inchide server socket\033[0m')
    command_server.close()
    if Deeebug:
        print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Sterge socket ' + cfg.socket_path + '\033[0m')
    # sys.exit(0)

def request_shutdown(signum, frame):
    syslog.syslog(syslog.LOG_NOTICE, 'Semnal oprire primit: %s' % signum)
    controller.set_runtime_state('stopping', source='signal', command='SIGTERM',
                                 message='daemon shutdown requested')
    shutdown_requested.set()

def force_relays_off(reason):
    hardware.force_relays_off(reason)

### Program principal ###
print('\033[30;48;5;82m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
      ': ****** START PROGRAM ****** ' + '\033[0m')

e = threading.Event()
shutdown_requested = threading.Event()
signal.signal(signal.SIGTERM, request_shutdown)

# Citeste config
cfg = load_config('irigatie.conf', Deeebug)
RAIN_ON = cfg.rain_on

# Setup GPIO
hardware = GpioHardware(cfg, ploua, buton, Deeebug)
force_relays_off('daemon startup')
hardware.initialize_transformer_mode()

### Config SQL ###
G_db_online = False
database = IrrigationDatabase(cfg, Deeebug)
controller = IrrigationController(cfg, hardware, database, shutdown_requested,
                                  Deeebug)
try:
    database.connect()
    if Deeebug:
        print(str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Conectare cu succes la baza de date, sistemul trece in modul online')
    syslog.syslog(syslog.LOG_NOTICE, 'Conectare cu succes la baza de date, sistemul trece in modul online')
    G_db_online = True
    database.mark_startup_runtime_state()
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
command_server = UnixCommandServer(
    path=cfg.socket_path,
    mode=cfg.socket_mode,
    owner=cfg.socket_owner,
    group=cfg.socket_group,
    debug=Deeebug,
)
command_server.start()

# Thread status
ts = threading.Thread(name='non-block', target=status_led, args=(e, 2))
ts.daemon = True
ts.start()

# Thread controller
tc = threading.Thread(name='controller-worker', target=controller.worker)
tc.daemon = True
tc.start()

# Bucla infinita
try:
    command_server.serve(shutdown_requested, controller.enqueue_command,
                         controller.status)
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
