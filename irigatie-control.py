#!/usr/bin/python3
# -*- coding: utf-8 -*-

import datetime
import os
import pymysql
import queue
import signal
import socket
import subprocess
import syslog
import threading
import time
import traceback

from config import load_config
from gpio_hw import GpioHardware


# Deeebug
global Deeebug
Deeebug = False
# Deeebug = load_config('irigatie.conf', True).get_int('Deeebug', 'Deeebug', 0)

MAX_PENDING_WATERING_COMMANDS = 4

# if Deeebug:
#     pydevd_pycharm.settrace('192.168.19.185', port=12345, stdoutToServer=True, stderrToServer=True)


def ploua():
    if RAIN_ON == 1:
        if Deeebug:
            print('\033[94m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Ploua +0,25l/mp' + '\033[0m')
        syslog.syslog(syslog.LOG_NOTICE, 'Ploua +0,2794 l/mp')
        sql = 'UPDATE programari SET ploaie = ploaie + 1, zile_fp = 1;'
        conn.ping(True)
        cur.execute(sql)


def buton(but_apasat):
    if Deeebug:
        print('\033[92m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Butonul ' + str(but_apasat) + ' declansat\033[0m')
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


def reserve_watering_command(command, parameter, source):
    global pending_watering_commands

    with pending_watering_lock:
        if pending_watering_commands >= MAX_PENDING_WATERING_COMMANDS:
            syslog.syslog(syslog.LOG_ERR, 'Comanda respinsa, coada plina: %s %s (%s)' %
                          (command, parameter, source))
            return False

        pending_watering_commands += 1
        syslog.syslog(syslog.LOG_INFO, 'Comenzi udare in asteptare: %s/%s' %
                      (pending_watering_commands, MAX_PENDING_WATERING_COMMANDS))
        return True


def release_watering_command():
    global pending_watering_commands

    with pending_watering_lock:
        if pending_watering_commands > 0:
            pending_watering_commands -= 1
        syslog.syslog(syslog.LOG_INFO, 'Comenzi udare in asteptare: %s/%s' %
                      (pending_watering_commands, MAX_PENDING_WATERING_COMMANDS))


def enqueue_command(command, parameter=None, source='unknown'):
    if command == 'STOP':
        stop_requested.set()
        set_runtime_state('stopping', source=source, command=command,
                          message='stop requested')
    elif command == 'SHUTDOWN':
        set_runtime_state('stopping', source=source, command=command,
                          message='shutdown requested')

    if command == 'EXEC':
        with pending_watering_lock:
            if pending_watering_commands > 0:
                syslog.syslog(syslog.LOG_ERR, 'Comanda manuala respinsa, coada udare ocupata: %s %s (%s)' %
                              (command, parameter, source))
                return False

    if command in ('START', 'EXEC'):
        if not reserve_watering_command(command, parameter, source):
            return False

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

    if command in ('STOP', 'SHUTDOWN', 'RELOAD_SCHEDULES'):
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
                ruleaza_program(parameter, source)
            elif command == 'EXEC':
                program_manual(parameter, source)
            elif command == 'SHUTDOWN':
                shutdown_requested.set()
            elif command == 'STOP':
                syslog.syslog(syslog.LOG_NOTICE, 'Comanda STOP procesata')
            elif command == 'RELOAD_SCHEDULES':
                reload_systemd_schedules(source)
            else:
                syslog.syslog(syslog.LOG_ERR, 'Comanda ignorata de worker: %s %s (%s)' %
                              (command, parameter, source))
        except Exception as exc:
            syslog.syslog(syslog.LOG_ERR, 'Eroare la executia comenzii %s %s (%s): %r' %
                          (command, parameter, source, exc))
            mark_runtime_error('command %s %s failed: %r' % (command, parameter, exc))
            traceback.print_exc()
        finally:
            if command in ('START', 'EXEC'):
                release_watering_command()
            command_queue.task_done()


def reload_systemd_schedules(source='unknown'):
    syslog.syslog(syslog.LOG_NOTICE, 'Reincarca programarile systemd (%s)' % source)
    subprocess.check_call([
        '/usr/bin/python3',
        '/home/pi/irigatie/generate_systemd_schedules.py',
        '-c',
        '/home/pi/irigatie/irigatie.conf',
    ])
    syslog.syslog(syslog.LOG_NOTICE, 'Programarile systemd au fost reincarcate')


def interruptible_sleep(seconds):
    end_time = time.time() + seconds
    while time.time() < end_time:
        if stop_requested.is_set() or shutdown_requested.is_set():
            return False
        heartbeat_runtime_state()
        remaining = end_time - time.time()
        if remaining <= 0:
            break
        time.sleep(min(1, remaining))
    return True


def db_timestamp(value):
    if value is None:
        return None
    return value.strftime('%Y-%m-%d %H:%M:%S')


def set_runtime_state(state, source=None, command=None, program_id=None,
                      traseu_id=None, started_at=None, expected_end_at=None,
                      message=None):
    try:
        with runtime_state_lock:
            conn.ping(True)
            sql = (
                'INSERT INTO runtime_state '
                '(id, state, source, command, program_id, traseu_id, started_at, expected_end_at, heartbeat_at, updated_at, message) '
                'VALUES (1, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW(), %s) '
                'ON DUPLICATE KEY UPDATE '
                'state = VALUES(state), source = VALUES(source), command = VALUES(command), '
                'program_id = VALUES(program_id), traseu_id = VALUES(traseu_id), '
                'started_at = VALUES(started_at), expected_end_at = VALUES(expected_end_at), '
                'heartbeat_at = VALUES(heartbeat_at), updated_at = VALUES(updated_at), message = VALUES(message);'
            )
            cur.execute(sql, (
                state, source, command, program_id, traseu_id,
                db_timestamp(started_at), db_timestamp(expected_end_at), message
            ))
    except Exception as exc:
        syslog.syslog(syslog.LOG_ERR, 'Nu pot actualiza runtime_state: %r' % (exc,))


def update_runtime_zone(traseu_id, expected_end_at=None, message=None):
    try:
        with runtime_state_lock:
            conn.ping(True)
            cur.execute(
                'UPDATE runtime_state SET traseu_id = %s, expected_end_at = %s, '
                'heartbeat_at = NOW(), updated_at = NOW(), message = %s WHERE id = 1;',
                (traseu_id, db_timestamp(expected_end_at), message)
            )
    except Exception as exc:
        syslog.syslog(syslog.LOG_ERR, 'Nu pot actualiza zona runtime_state: %r' % (exc,))


def heartbeat_runtime_state():
    try:
        with runtime_state_lock:
            conn.ping(True)
            cur.execute(
                'UPDATE runtime_state SET heartbeat_at = NOW(), updated_at = NOW() '
                'WHERE id = 1 AND state IN (\'running\', \'stopping\');'
            )
    except Exception as exc:
        syslog.syslog(syslog.LOG_ERR, 'Nu pot actualiza heartbeat runtime_state: %r' % (exc,))


def mark_runtime_idle(message='idle'):
    set_runtime_state('idle', message=message)


def mark_runtime_error(message):
    set_runtime_state('error', message=message[:255])


def mark_startup_runtime_state():
    try:
        with runtime_state_lock:
            conn.ping(True)
            cur.execute('SELECT state FROM runtime_state WHERE id = 1;')
            row = cur.fetchone()
            if row is not None and row.get('state') == 'running':
                cur.execute(
                    'UPDATE runtime_state SET state = %s, heartbeat_at = NOW(), updated_at = NOW(), message = %s WHERE id = 1;',
                    ('interrupted', 'daemon startup found previous running state')
                )
                return
    except Exception as exc:
        syslog.syslog(syslog.LOG_ERR, 'Nu pot verifica runtime_state la startup: %r' % (exc,))
    mark_runtime_idle('daemon startup')


def validate_zone_duration(seconds, context):
    if seconds <= 0:
        return 0
    if seconds > MAX_ZONE_SECONDS:
        raise RuntimeError('Safety abort: %s zone duration %.3f exceeds max %s seconds' %
                           (context, seconds, MAX_ZONE_SECONDS))
    return seconds


def validate_program_duration(seconds, context):
    if seconds > MAX_PROGRAM_SECONDS:
        raise RuntimeError('Safety abort: %s program duration %.3f exceeds max %s seconds' %
                           (context, seconds, MAX_PROGRAM_SECONDS))
    return seconds


def program_manual(prg, source='manual'):
    if try_start_program():
        completed = False
        try:
            hardware.set_led((0, 1, 0))
            if Deeebug:
                print('\033[0;33m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Porneste programul ' +
                      str(prg) + '...\033[0m')
            syslog.syslog('Porneste programul ' + str(prg))
            stop_requested.clear()
            sql = 'SELECT * FROM progman WHERE id = ' + str(prg) + ';'
            conn.ping(True)
            cur.execute(sql)
            row = cur.fetchone()
            manual_zones = []
            total_seconds = 0
            for zone_id, relay in sorted(ZONE_RELAYS.items()):
                duration_key = 'durata_t%s' % zone_id
                sql = 'SELECT * FROM trasee WHERE id = ' + str(zone_id)
                conn.ping(True)
                cur.execute(sql)
                irow = cur.fetchone()
                duration = 0
                if irow['activ'] != 0 and row[duration_key] > 0:
                    duration = validate_zone_duration(row[duration_key] * 60,
                                                      'manual program %s zone %s' % (prg, zone_id))
                    total_seconds += duration
                manual_zones.append({
                    'id': irow['id'],
                    'name': irow['denumire'],
                    'active': irow['activ'],
                    'relay': relay,
                    'duration': duration,
                })
            validate_program_duration(total_seconds, 'manual program %s' % prg)
            started_at = datetime.datetime.now()
            expected_end_at = started_at + datetime.timedelta(seconds=total_seconds)
            set_runtime_state('running', source=source, command='EXEC',
                              program_id=prg, started_at=started_at,
                              expected_end_at=expected_end_at,
                              message='manual program running')
            if P_TRAF == 'Auto':
                syslog.syslog('Porneste traful')
                if Deeebug:
                    print('\033[0;32m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Porneste traful\033[0m')
                hardware.transformer_on()
            for zone in manual_zones:
                if not interruptible_sleep(1):
                    break
                duration = zone['duration']
                if duration > 0:
                    zone_expected_end_at = datetime.datetime.now() + datetime.timedelta(seconds=duration)
                    update_runtime_zone(zone['id'], zone_expected_end_at,
                                        'manual program zone running')
                    run_zone(zone['id'], zone['name'], zone['relay'], duration)
            if Deeebug:
                print('\033[0;33m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Programul ' +
                      str(prg) + ' finalizat\033[0m')
            syslog.syslog('Programul ' + str(prg) + ' finalizat')
            completed = True
        finally:
            force_relays_off('manual program cleanup')
            restore_transformer_mode()
            hardware.led_off()
            if completed:
                if stop_requested.is_set():
                    mark_runtime_idle('manual program stopped')
                else:
                    mark_runtime_idle('manual program completed')
            program_lock.release()

def ruleaza_program(prg, source='scheduled'):
    if try_start_program():
        completed = False
        try:
            hardware.set_led((1, 0, 1))
            if Deeebug:
                print('\033[0;33m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Porneste programarea ' +
                      str(prg) + '...\033[0m')
            syslog.syslog('Porneste programarea ' + str(prg))
            stop_requested.clear()
            sql = 'SELECT trasee.denumire, trasee.activ, trasee.id AS tid, programari.* FROM programari LEFT JOIN trasee ON programari.traseu_id = trasee.id WHERE programari.id = %s;' % str(prg)
            conn.ping(True)
            cur.execute(sql)
            row = cur.fetchone()
            if Deeebug:
                print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Traseu determinat > ' +
                      row['denumire'] + ' - activ: ' + str(row['activ']) + '\033[0m')
            if row['activ']:
                hardware.set_led((1, 0, 1))
                a_releu = care_releu(int(row['tid']))
                if Deeebug:
                    print('\033[0;34m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Releu determinat > ' +
                          str(a_releu) + '...\033[0m')
                syslog.syslog(syslog.LOG_INFO, 'Precipitatii %s, maxim setat %s' % (str(row['ploaie']), str(row['max_ploaie'])))
                if row['max_ploaie'] <= 0:
                    raise RuntimeError('Safety abort: scheduled program %s has max_ploaie <= 0' % prg)
                if row['ploaie'] < row['max_ploaie']:
                    duration = validate_zone_duration(
                        (row['max_ploaie'] - row['ploaie']) / float(row['max_ploaie']) * row['durata'] * 60,
                        'scheduled program %s zone %s' % (prg, row['tid'])
                    )
                    validate_program_duration(duration, 'scheduled program %s' % prg)
                    if duration > 0:
                        started_at = datetime.datetime.now()
                        expected_end_at = started_at + datetime.timedelta(seconds=duration)
                        set_runtime_state('running', source=source, command='START',
                                          program_id=prg, traseu_id=row['tid'],
                                          started_at=started_at,
                                          expected_end_at=expected_end_at,
                                          message='scheduled program running')
                        if P_TRAF == 'Auto':
                            syslog.syslog('Porneste traful')
                            if Deeebug:
                                print('\033[0;32m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Porneste traful\033[0m')
                            hardware.transformer_on()
                        if not interruptible_sleep(1):
                            return
                        run_zone(row['tid'], row['denumire'], a_releu, duration)
                        interruptible_sleep(1)
            sql = 'UPDATE programari SET ploaie = ' + str((abs(row['ploaie'] - row['max_ploaie'] * row['zile_fp']) + (row['ploaie'] - row['max_ploaie'] * row['zile_fp'])) / 2) + ', zile_fp = ' + str(row['zile_fp'] + 1) + ' WHERE traseu_id = %s;' % str(row['traseu_id'])
            conn.ping(True)
            cur.execute(sql)
            syslog.syslog('SQL reduce ploaie: ' + sql);
            if Deeebug:
                print('\033[0;33m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Programarea ' +
                      str(prg) + ' finalizata\033[0m')
            syslog.syslog('Programarea ' + str(prg) + ' finalizata')
            completed = True
        finally:
            force_relays_off('scheduled program cleanup')
            restore_transformer_mode()
            hardware.led_off()
            if completed:
                if stop_requested.is_set():
                    mark_runtime_idle('scheduled program stopped')
                else:
                    mark_runtime_idle('scheduled program completed')
            program_lock.release()

def care_releu(traseu):
    return ZONE_RELAYS.get(traseu, False)

def run_zone(zone_id, zone_name, relay, duration_seconds):
    hardware.run_zone(zone_id, zone_name, duration_seconds, interruptible_sleep)

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
    set_runtime_state('stopping', source='signal', command='SIGTERM',
                      message='daemon shutdown requested')
    shutdown_requested.set()

def force_relays_off(reason):
    hardware.force_relays_off(reason)

def restore_transformer_mode():
    hardware.restore_transformer_mode()

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
stop_requested = threading.Event()
pending_watering_lock = threading.Lock()
pending_watering_commands = 0
runtime_state_lock = threading.Lock()

# Anti paralelism
program_lock = threading.Lock()

# Citeste config
cfg = load_config('irigatie.conf', Deeebug)
P_TRAF = cfg.p_traf
RAIN_ON = cfg.rain_on
MAX_ZONE_SECONDS = cfg.max_zone_seconds
MAX_PROGRAM_SECONDS = cfg.max_program_seconds

# Setup GPIO
hardware = GpioHardware(cfg, ploua, buton, Deeebug)
ZONE_RELAYS = hardware.zone_relays
force_relays_off('daemon startup')
hardware.initialize_transformer_mode()

### Config SQL ###
G_db_online = False
DB_SERVER = cfg.db_server
DB_PORT = cfg.db_port
DB_USER = cfg.db_user
DB_PASS = cfg.db_pass
DB_NAME = cfg.db_name
try:
    conn = pymysql.connect(host=DB_SERVER, port=int(DB_PORT), user=DB_USER, password=DB_PASS, db=DB_NAME, autocommit=True)
    cur = conn.cursor(pymysql.cursors.DictCursor)
    conn.ping(True)
    if Deeebug:
        print(str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
              ': Conectare cu succes la baza de date, sistemul trece in modul online')
    syslog.syslog(syslog.LOG_NOTICE, 'Conectare cu succes la baza de date, sistemul trece in modul online')
    G_db_online = True
    mark_startup_runtime_state()
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
