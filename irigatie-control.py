#!/usr/bin/python3
# -*- coding: utf-8 -*-

import datetime
import pymysql
import signal
import threading
import traceback

import log
from config import load_config
from controller import IrrigationController
from db import IrrigationDatabase
from gpio_hw import GpioHardware
from rain import record_hardware_rain_pulse
from socket_server import UnixCommandServer


debug_enabled = False


def ploua():
    record_hardware_rain_pulse(
        database,
        RAIN_ON,
        cfg.rain_source,
        cfg.hardware_pulse_mm,
        debug_enabled,
    )


def buton(but_apasat):
    log.notice('command_received', 'button pressed', button=but_apasat)
    controller.enqueue_command('EXEC', but_apasat, 'button')

def status_led(e, ts):
    hardware.status_led_loop(e, ts)

def cortina():
    log.info('shutdown', 'daemon cleanup starting')
    force_relays_off('daemon shutdown')
    hardware.close()
    e.set()
    database.close()
    command_server.close()
    log.info('shutdown', 'daemon cleanup finished')
    # sys.exit(0)

def request_shutdown(signum, frame):
    log.notice('shutdown', 'signal received', signum=signum)
    controller.set_runtime_state('stopping', source='signal', command='SIGTERM',
                                 message='daemon shutdown requested')
    shutdown_requested.set()

def force_relays_off(reason):
    hardware.force_relays_off(reason)

### Program principal ###
log.notice('startup', 'daemon starting',
           timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))

e = threading.Event()
shutdown_requested = threading.Event()
signal.signal(signal.SIGTERM, request_shutdown)

# Citeste config
cfg = load_config('irigatie.conf', False)
debug_enabled = cfg.debug_enabled
RAIN_ON = cfg.rain_on
log.info('startup', 'config loaded',
         debug=debug_enabled,
         gpio_backend=cfg.gpio_backend,
         rain_source=cfg.rain_source,
         socket_path=cfg.socket_path)

# Setup GPIO
hardware = GpioHardware(cfg, ploua, buton, debug_enabled)
force_relays_off('daemon startup')
hardware.initialize_transformer_mode()

### Config SQL ###
G_db_online = False
database = IrrigationDatabase(cfg, debug_enabled)
controller = IrrigationController(cfg, hardware, database, shutdown_requested,
                                  debug_enabled)
try:
    database.connect()
    log.notice('startup', 'database connected',
               host=cfg.db_server, port=cfg.db_port, user=cfg.db_user,
               database=cfg.db_name)
    G_db_online = True
    database.mark_startup_runtime_state()
except pymysql.err.MySQLError as e:
    log.err('db_error', 'database connection failed',
            error=repr(e), errno=e.args[0])
    log.err('startup', 'daemon entering offline mode')
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
    debug=debug_enabled,
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
    log.notice('shutdown', 'keyboard interrupt received')
    shutdown_requested.set()
except Exception as exc:
    log.err('shutdown', 'daemon loop failed',
            error=repr(exc), traceback=traceback.format_exc())
finally:
    cortina()

# GPIO.cleanup()
