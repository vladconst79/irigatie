#!/usr/bin/python3
# -*- coding: utf-8 -*-
import datetime
import queue
import subprocess
import syslog
import threading
import time
import traceback


MAX_PENDING_WATERING_COMMANDS = 4


class IrrigationController:
    def __init__(self, config, hardware, database, shutdown_requested,
                 debug=False):
        self.config = config
        self.hardware = hardware
        self.database = database
        self.shutdown_requested = shutdown_requested
        self.debug = debug

        self.command_queue = queue.Queue()
        self.stop_requested = threading.Event()
        self.pending_watering_lock = threading.Lock()
        self.pending_watering_commands = 0
        self.program_lock = threading.Lock()
        self.zone_relays = hardware.zone_relays

    def enqueue_command(self, command, parameter=None, source='unknown'):
        if command == 'STOP':
            self.stop_requested.set()
            self.set_runtime_state('stopping', source=source, command=command,
                                   message='stop requested')
        elif command == 'SHUTDOWN':
            self.set_runtime_state('stopping', source=source, command=command,
                                   message='shutdown requested')

        if command == 'EXEC':
            with self.pending_watering_lock:
                if self.pending_watering_commands > 0:
                    syslog.syslog(syslog.LOG_ERR, 'Comanda manuala respinsa, coada udare ocupata: %s %s (%s)' %
                                  (command, parameter, source))
                    return False

        if command in ('START', 'EXEC'):
            if not self.reserve_watering_command(command, parameter, source):
                return False

        self.command_queue.put((command, parameter, source))
        syslog.syslog(syslog.LOG_INFO, 'Comanda acceptata: %s %s (%s)' %
                      (command, parameter, source))
        return True

    def reserve_watering_command(self, command, parameter, source):
        with self.pending_watering_lock:
            if self.pending_watering_commands >= MAX_PENDING_WATERING_COMMANDS:
                syslog.syslog(syslog.LOG_ERR, 'Comanda respinsa, coada plina: %s %s (%s)' %
                              (command, parameter, source))
                return False

            self.pending_watering_commands += 1
            syslog.syslog(syslog.LOG_INFO, 'Comenzi udare in asteptare: %s/%s' %
                          (self.pending_watering_commands, MAX_PENDING_WATERING_COMMANDS))
            return True

    def release_watering_command(self):
        with self.pending_watering_lock:
            if self.pending_watering_commands > 0:
                self.pending_watering_commands -= 1
            syslog.syslog(syslog.LOG_INFO, 'Comenzi udare in asteptare: %s/%s' %
                          (self.pending_watering_commands, MAX_PENDING_WATERING_COMMANDS))

    def worker(self):
        while not self.shutdown_requested.is_set():
            try:
                command, parameter, source = self.command_queue.get(timeout=1)
            except queue.Empty:
                continue

            try:
                if command == 'START':
                    self.ruleaza_program(parameter, source)
                elif command == 'EXEC':
                    self.program_manual(parameter, source)
                elif command == 'SHUTDOWN':
                    self.shutdown_requested.set()
                elif command == 'STOP':
                    syslog.syslog(syslog.LOG_NOTICE, 'Comanda STOP procesata')
                elif command == 'RELOAD_SCHEDULES':
                    self.reload_systemd_schedules(source)
                else:
                    syslog.syslog(syslog.LOG_ERR, 'Comanda ignorata de worker: %s %s (%s)' %
                                  (command, parameter, source))
            except Exception as exc:
                syslog.syslog(syslog.LOG_ERR, 'Eroare la executia comenzii %s %s (%s): %r' %
                              (command, parameter, source, exc))
                self.mark_runtime_error('command %s %s failed: %r' % (command, parameter, exc))
                traceback.print_exc()
            finally:
                if command in ('START', 'EXEC'):
                    self.release_watering_command()
                self.command_queue.task_done()

    def reload_systemd_schedules(self, source='unknown'):
        syslog.syslog(syslog.LOG_NOTICE, 'Reincarca programarile systemd (%s)' % source)
        subprocess.check_call([
            '/usr/bin/python3',
            '/home/pi/irigatie/generate_systemd_schedules.py',
            '-c',
            '/home/pi/irigatie/irigatie.conf',
        ])
        syslog.syslog(syslog.LOG_NOTICE, 'Programarile systemd au fost reincarcate')

    def try_start_program(self):
        if self.program_lock.acquire(False):
            return True

        syslog.syslog(syslog.LOG_ERR, 'Deja ruleaza alt program')
        if self.debug:
            print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) +
                  ': Deja ruleaza alt program\033[0m')
        return False

    def interruptible_sleep(self, seconds):
        end_time = time.time() + seconds
        while time.time() < end_time:
            if self.stop_requested.is_set() or self.shutdown_requested.is_set():
                return False
            self.heartbeat_runtime_state()
            remaining = end_time - time.time()
            if remaining <= 0:
                break
            time.sleep(min(1, remaining))
        return True

    def validate_zone_duration(self, seconds, context):
        if seconds <= 0:
            return 0
        if seconds > self.config.max_zone_seconds:
            raise RuntimeError('Safety abort: %s zone duration %.3f exceeds max %s seconds' %
                               (context, seconds, self.config.max_zone_seconds))
        return seconds

    def validate_program_duration(self, seconds, context):
        if seconds > self.config.max_program_seconds:
            raise RuntimeError('Safety abort: %s program duration %.3f exceeds max %s seconds' %
                               (context, seconds, self.config.max_program_seconds))
        return seconds

    def program_manual(self, prg, source='manual'):
        if self.try_start_program():
            completed = False
            try:
                self.hardware.set_led((0, 1, 0))
                if self.debug:
                    print('\033[0;33m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Porneste programul ' +
                          str(prg) + '...\033[0m')
                syslog.syslog('Porneste programul ' + str(prg))
                self.stop_requested.clear()
                row = self.database.get_manual_program(prg)
                manual_zones = []
                total_seconds = 0
                for zone_id, relay in sorted(self.zone_relays.items()):
                    duration_key = 'durata_t%s' % zone_id
                    irow = self.database.get_zone(zone_id)
                    duration = 0
                    if irow['activ'] != 0 and row[duration_key] > 0:
                        duration = self.validate_zone_duration(row[duration_key] * 60,
                                                               'manual program %s zone %s' % (prg, zone_id))
                        total_seconds += duration
                    manual_zones.append({
                        'id': irow['id'],
                        'name': irow['denumire'],
                        'active': irow['activ'],
                        'relay': relay,
                        'duration': duration,
                    })
                self.validate_program_duration(total_seconds, 'manual program %s' % prg)
                started_at = datetime.datetime.now()
                expected_end_at = started_at + datetime.timedelta(seconds=total_seconds)
                self.set_runtime_state('running', source=source, command='EXEC',
                                       program_id=prg, started_at=started_at,
                                       expected_end_at=expected_end_at,
                                       message='manual program running')
                if self.config.p_traf == 'Auto':
                    syslog.syslog('Porneste traful')
                    if self.debug:
                        print('\033[0;32m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Porneste traful\033[0m')
                    self.hardware.transformer_on()
                for zone in manual_zones:
                    if not self.interruptible_sleep(1):
                        break
                    duration = zone['duration']
                    if duration > 0:
                        zone_expected_end_at = datetime.datetime.now() + datetime.timedelta(seconds=duration)
                        self.update_runtime_zone(zone['id'], zone_expected_end_at,
                                                 'manual program zone running')
                        self.run_zone(zone['id'], zone['name'], zone['relay'], duration)
                if self.debug:
                    print('\033[0;33m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Programul ' +
                          str(prg) + ' finalizat\033[0m')
                syslog.syslog('Programul ' + str(prg) + ' finalizat')
                completed = True
            finally:
                self.force_relays_off('manual program cleanup')
                self.restore_transformer_mode()
                self.hardware.led_off()
                if completed:
                    if self.stop_requested.is_set():
                        self.mark_runtime_idle('manual program stopped')
                    else:
                        self.mark_runtime_idle('manual program completed')
                self.program_lock.release()

    def ruleaza_program(self, prg, source='scheduled'):
        if self.try_start_program():
            completed = False
            try:
                self.hardware.set_led((1, 0, 1))
                if self.debug:
                    print('\033[0;33m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Porneste programarea ' +
                          str(prg) + '...\033[0m')
                syslog.syslog('Porneste programarea ' + str(prg))
                self.stop_requested.clear()
                row = self.database.get_scheduled_program(prg)
                if self.debug:
                    print('\033[0;36m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Traseu determinat > ' +
                          row['denumire'] + ' - activ: ' + str(row['activ']) + '\033[0m')
                if row['activ']:
                    self.hardware.set_led((1, 0, 1))
                    a_releu = self.care_releu(int(row['tid']))
                    if self.debug:
                        print('\033[0;34m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Releu determinat > ' +
                              str(a_releu) + '...\033[0m')
                    rain_credit_mm = row['ploaie']
                    rain_threshold_mm = row['max_ploaie']
                    syslog.syslog(syslog.LOG_INFO, 'Precipitatii %.3f mm, maxim setat %.3f mm' %
                                  (float(rain_credit_mm), float(rain_threshold_mm)))
                    if rain_threshold_mm <= 0:
                        raise RuntimeError('Safety abort: scheduled program %s has max_ploaie <= 0' % prg)
                    if rain_credit_mm < rain_threshold_mm:
                        duration = self.validate_zone_duration(
                            (rain_threshold_mm - rain_credit_mm) / float(rain_threshold_mm) * row['durata'] * 60,
                            'scheduled program %s zone %s' % (prg, row['tid'])
                        )
                        self.validate_program_duration(duration, 'scheduled program %s' % prg)
                        if duration > 0:
                            started_at = datetime.datetime.now()
                            expected_end_at = started_at + datetime.timedelta(seconds=duration)
                            self.set_runtime_state('running', source=source, command='START',
                                                   program_id=prg, traseu_id=row['tid'],
                                                   started_at=started_at,
                                                   expected_end_at=expected_end_at,
                                                   message='scheduled program running')
                            if self.config.p_traf == 'Auto':
                                syslog.syslog('Porneste traful')
                                if self.debug:
                                    print('\033[0;32m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Porneste traful\033[0m')
                                self.hardware.transformer_on()
                            if not self.interruptible_sleep(1):
                                return
                            self.run_zone(row['tid'], row['denumire'], a_releu, duration)
                            self.interruptible_sleep(1)
                self.database.reduce_rain_after_scheduled_program(row)
                if self.debug:
                    print('\033[0;33m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': Programarea ' +
                          str(prg) + ' finalizata\033[0m')
                syslog.syslog('Programarea ' + str(prg) + ' finalizata')
                completed = True
            finally:
                self.force_relays_off('scheduled program cleanup')
                self.restore_transformer_mode()
                self.hardware.led_off()
                if completed:
                    if self.stop_requested.is_set():
                        self.mark_runtime_idle('scheduled program stopped')
                    else:
                        self.mark_runtime_idle('scheduled program completed')
                self.program_lock.release()

    def care_releu(self, traseu):
        return self.zone_relays.get(traseu, False)

    def run_zone(self, zone_id, zone_name, relay, duration_seconds):
        self.hardware.run_zone(zone_id, zone_name, duration_seconds,
                               self.interruptible_sleep)

    def set_runtime_state(self, state, source=None, command=None, program_id=None,
                          traseu_id=None, started_at=None, expected_end_at=None,
                          message=None):
        self.database.set_runtime_state(state, source, command, program_id,
                                        traseu_id, started_at, expected_end_at,
                                        message)

    def update_runtime_zone(self, traseu_id, expected_end_at=None, message=None):
        self.database.update_runtime_zone(traseu_id, expected_end_at, message)

    def heartbeat_runtime_state(self):
        self.database.heartbeat_runtime_state()

    def mark_runtime_idle(self, message='idle'):
        self.database.mark_runtime_idle(message)

    def mark_runtime_error(self, message):
        self.database.mark_runtime_error(message)

    def force_relays_off(self, reason):
        self.hardware.force_relays_off(reason)

    def restore_transformer_mode(self):
        self.hardware.restore_transformer_mode()
