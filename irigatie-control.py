#!/usr/bin/python3
# -*- coding: utf-8 -*-

import argparse
import datetime
import signal
import threading
import traceback

import log
from config import ConfigError, load_config
from controller import IrrigationController
from gpio_hw import GpioHardware
from rain import record_hardware_rain_pulse
from socket_server import UnixCommandServer


debug_enabled = False
cfg = None
RAIN_ON = None
hardware = None
database = None
controller = None
command_server = None
e = None
shutdown_requested = None


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

def parse_args():
    parser = argparse.ArgumentParser(description='Irigatie daemon and test commands')
    parser.add_argument('-c', '--config', default='irigatie.conf',
                        help='path to irigatie.conf')
    parser.add_argument('--check-config', action='store_true',
                        help='validate config and print non-secret effective settings')
    parser.add_argument('--test-db', action='store_true',
                        help='validate config and test database connection')
    parser.add_argument('--test-socket', action='store_true',
                        help='validate config and check whether the control socket exists')
    parser.add_argument('--test-relay-map', action='store_true',
                        help='print configured relay GPIO mapping without switching relays')
    parser.add_argument('--relays-off', action='store_true',
                        help='force all configured relays off and exit')
    return parser.parse_args()


def load_checked_config(path):
    try:
        loaded = load_config(path, False)
    except ConfigError as exc:
        log.err('startup', 'config validation failed', error=str(exc))
        print('ERROR: config validation failed: %s' % exc)
        raise SystemExit(2)
    return loaded


def print_effective_config(loaded):
    print('Config OK: %s' % loaded.path)
    print('GPIO relays: transformer=%s zone1=%s zone2=%s zone3=%s zone4=%s' %
          (loaded.r_traf, loaded.r_iri1, loaded.r_iri2, loaded.r_iri3, loaded.r_iri4))
    print('GPIO inputs: rain=%s button1=%s button2=%s button3=%s button4=%s' %
          (loaded.s_rain, loaded.b_but1, loaded.b_but2, loaded.b_but3, loaded.b_but4))
    print('GPIO LED: red=%s green=%s blue=%s' %
          (loaded.l_red, loaded.l_green, loaded.l_blue))
    print('Hardware: backend=%s transformer_mode=%s rain_on=%s' %
          (loaded.gpio_backend, loaded.p_traf, loaded.rain_on))
    print('Rain: source=%s hardware_pulse_mm=%s' %
          (loaded.rain_source, loaded.hardware_pulse_mm))
    print('DB: host=%s port=%s user=%s database=%s password=********' %
          (loaded.db_server, loaded.db_port, loaded.db_user, loaded.db_name))
    print('Socket: path=%s mode=0%o owner=%s group=%s' %
          (loaded.socket_path, loaded.socket_mode, loaded.socket_owner, loaded.socket_group))


def print_relay_map(loaded):
    print('Relay GPIO map:')
    print('  transformer GPIO%s' % loaded.r_traf)
    print('  zone 1 GPIO%s' % loaded.r_iri1)
    print('  zone 2 GPIO%s' % loaded.r_iri2)
    print('  zone 3 GPIO%s' % loaded.r_iri3)
    print('  zone 4 GPIO%s' % loaded.r_iri4)


def test_db(loaded):
    try:
        from db import IrrigationDatabase
    except ImportError as exc:
        print('DB ERROR: could not import database dependency: %s' % exc)
        return 1

    db = IrrigationDatabase(loaded)
    try:
        db.connect()
        ok, error = db.check_connection()
    finally:
        db.close()
    if ok:
        print('DB OK: %s:%s/%s as %s' %
              (loaded.db_server, loaded.db_port, loaded.db_name, loaded.db_user))
        return 0
    print('DB ERROR: %s' % error)
    return 1


def test_socket(loaded):
    import os
    if os.path.exists(loaded.socket_path):
        print('Socket OK: %s exists' % loaded.socket_path)
        return 0
    print('Socket missing: %s' % loaded.socket_path)
    return 1


def run_relays_off(loaded):
    test_hardware = GpioHardware(loaded, lambda: None, lambda button: None,
                                 loaded.debug_enabled)
    try:
        test_hardware.force_relays_off('manual test command')
    finally:
        test_hardware.close()
    print('Relays forced off')
    return 0


def handle_test_command(args, loaded):
    if args.check_config:
        loaded.log_effective_config()
        print_effective_config(loaded)
        return 0
    if args.test_db:
        return test_db(loaded)
    if args.test_socket:
        return test_socket(loaded)
    if args.test_relay_map:
        print_relay_map(loaded)
        return 0
    if args.relays_off:
        return run_relays_off(loaded)
    return None


def main():
    global cfg, RAIN_ON, debug_enabled
    global hardware, database, controller, command_server
    global e, shutdown_requested

    args = parse_args()
    cfg = load_checked_config(args.config)
    debug_enabled = cfg.debug_enabled
    RAIN_ON = cfg.rain_on

    test_result = handle_test_command(args, cfg)
    if test_result is not None:
        return test_result

    log.notice('startup', 'daemon starting',
               timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))

    e = threading.Event()
    shutdown_requested = threading.Event()
    signal.signal(signal.SIGTERM, request_shutdown)

    log.info('startup', 'config loaded',
             debug=debug_enabled,
             gpio_backend=cfg.gpio_backend,
             rain_source=cfg.rain_source,
             socket_path=cfg.socket_path)
    cfg.log_effective_config()

    hardware = GpioHardware(cfg, ploua, buton, debug_enabled)
    force_relays_off('daemon startup')
    hardware.initialize_transformer_mode()

    from db import IrrigationDatabase
    database = IrrigationDatabase(cfg, debug_enabled)
    controller = IrrigationController(cfg, hardware, database, shutdown_requested,
                                      debug_enabled)
    try:
        database.connect()
        log.notice('startup', 'database connected',
                   host=cfg.db_server, port=cfg.db_port, user=cfg.db_user,
                   database=cfg.db_name)
        database.mark_startup_runtime_state()
    except Exception as exc:
        log.err('db_error', 'database connection failed',
                error=repr(exc), errno=getattr(exc, 'args', [None])[0])
        log.err('startup', 'daemon entering offline mode')

    command_server = UnixCommandServer(
        path=cfg.socket_path,
        mode=cfg.socket_mode,
        owner=cfg.socket_owner,
        group=cfg.socket_group,
        debug=debug_enabled,
    )
    command_server.start()

    ts = threading.Thread(name='non-block', target=status_led, args=(e, 2))
    ts.daemon = True
    ts.start()

    tc = threading.Thread(name='controller-worker', target=controller.worker)
    tc.daemon = True
    tc.start()

    try:
        command_server.serve(shutdown_requested, controller.enqueue_command,
                             controller.status)
    except KeyboardInterrupt:
        log.notice('shutdown', 'keyboard interrupt received')
        shutdown_requested.set()
    except Exception as exc:
        log.err('shutdown', 'daemon loop failed',
                error=repr(exc), traceback=traceback.format_exc())
    finally:
        cortina()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
