#!/usr/bin/python3
# -*- coding: utf-8 -*-
import datetime
import decimal
import queue
import subprocess
import threading
import time

import log

MAX_PENDING_WATERING_COMMANDS = 4
TEST_ZONE_SECONDS = 30


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

        if command in ('EXEC', 'TEST'):
            with self.pending_watering_lock:
                if self.pending_watering_commands > 0:
                    log.err('command_received', 'command rejected queue busy',
                            command=command, parameter=parameter, source=source)
                    return False

        if command in ('START', 'EXEC', 'TEST'):
            if not self.reserve_watering_command(command, parameter, source):
                return False

        self.command_queue.put((command, parameter, source))
        log.info('command_received', 'accepted',
                 command=command, parameter=parameter, source=source)
        return True

    def reserve_watering_command(self, command, parameter, source):
        with self.pending_watering_lock:
            if self.pending_watering_commands >= MAX_PENDING_WATERING_COMMANDS:
                log.err('command_received', 'rejected queue full',
                        command=command, parameter=parameter, source=source)
                return False

            self.pending_watering_commands += 1
            log.info('command_received', 'watering command reserved',
                     pending=self.pending_watering_commands,
                     max_pending=MAX_PENDING_WATERING_COMMANDS)
            return True

    def release_watering_command(self):
        with self.pending_watering_lock:
            if self.pending_watering_commands > 0:
                self.pending_watering_commands -= 1
            log.info('command_received', 'watering command released',
                     pending=self.pending_watering_commands,
                     max_pending=MAX_PENDING_WATERING_COMMANDS)

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
                elif command == 'TEST':
                    self.test_zone(parameter, source)
                elif command == 'SHUTDOWN':
                    self.shutdown_requested.set()
                elif command == 'STOP':
                    log.notice('command_received', 'STOP processed', source=source)
                    self.mark_runtime_idle('stop processed')
                elif command == 'RELOAD_SCHEDULES':
                    self.reload_systemd_schedules(source)
                else:
                    log.err('command_received', 'ignored by worker',
                            command=command, parameter=parameter, source=source)
            except Exception as exc:
                log.err('command_received', 'execution failed',
                        command=command, parameter=parameter, source=source,
                        error=repr(exc))
                self.mark_runtime_error('command %s %s failed: %r' % (command, parameter, exc))
            finally:
                if command in ('START', 'EXEC', 'TEST'):
                    self.release_watering_command()
                self.command_queue.task_done()

    def reload_systemd_schedules(self, source='unknown'):
        log.notice('command_received', 'reload systemd schedules starting', source=source)
        subprocess.check_call([
            '/usr/bin/python3',
            '/home/pi/irigatie/generate_systemd_schedules.py',
            '-c',
            '/home/pi/irigatie/irigatie.conf',
        ])
        log.notice('command_received', 'reload systemd schedules finished', source=source)

    def try_start_program(self):
        if self.program_lock.acquire(False):
            return True

        log.err('command_received', 'program already running')
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

    def test_zone(self, zone_id, source='socket'):
        if self.try_start_program():
            completed = False
            started_at = None
            zone = None
            duration = self.validate_zone_duration(
                TEST_ZONE_SECONDS, 'test zone %s' % zone_id)
            try:
                zone = self.database.get_zone(zone_id)
                if zone is None:
                    raise RuntimeError('Zone %s not found' % zone_id)

                relay = self.care_releu(int(zone_id))
                if relay is False:
                    raise RuntimeError('Zone %s has no configured relay' % zone_id)

                self.hardware.set_led((1, 1, 0))
                self.stop_requested.clear()
                started_at = datetime.datetime.now()
                expected_end_at = started_at + datetime.timedelta(seconds=duration)
                self.set_runtime_state('running', source=source, command='TEST',
                                       traseu_id=zone_id,
                                       started_at=started_at,
                                       expected_end_at=expected_end_at,
                                       message='zone test running')
                if self.config.p_traf == 'Auto':
                    log.info('relay_safety', 'transformer on',
                             source=source, zone_id=zone_id, command='TEST')
                    self.hardware.transformer_on()
                if not self.interruptible_sleep(1):
                    completed = True
                    return
                log.notice('watering_start', 'zone test starting',
                           source=source, zone_id=zone_id,
                           duration_seconds=duration)
                zone_completed = self.run_zone(
                    zone['id'], zone['denumire'], relay, duration)
                ended_at = datetime.datetime.now()
                result = 'test_completed' if zone_completed else 'test_interrupted'
                self.log_watering_event(
                    started_at, ended_at, source, None, zone['id'],
                    duration, elapsed_seconds(started_at, ended_at),
                    None, result
                )
                log.notice('watering_stop', 'zone test finished',
                           source=source, zone_id=zone_id, result=result,
                           actual_seconds=elapsed_seconds(started_at, ended_at))
                completed = True
            except Exception as exc:
                now = datetime.datetime.now()
                result = exception_result(exc)
                self.log_watering_event(
                    started_at or now, now, source, None,
                    zone['id'] if zone is not None else zone_id,
                    duration, 0, None, result, repr(exc)
                )
                log.err('watering_stop', 'zone test failed',
                        source=source, zone_id=zone_id,
                        result=result, error=repr(exc))
                raise
            finally:
                self.force_relays_off('zone test cleanup')
                self.restore_transformer_mode()
                self.hardware.led_off()
                if completed:
                    if self.stop_requested.is_set():
                        self.mark_runtime_idle('zone test stopped')
                    else:
                        self.mark_runtime_idle('zone test completed')
                self.program_lock.release()

    def program_manual(self, prg, source='manual'):
        if self.try_start_program():
            completed = False
            current_event = None
            try:
                self.hardware.set_led((0, 1, 0))
                log.notice('watering_start', 'manual program starting',
                           source=source, program_id=prg)
                self.stop_requested.clear()
                row = self.database.get_manual_program(prg)
                manual_zones = []
                total_seconds = 0
                for zone_id, relay in sorted(self.zone_relays.items()):
                    duration_key = 'durata_t%s' % zone_id
                    irow = self.database.get_zone(zone_id)
                    duration = 0
                    planned_seconds = row[duration_key] * 60
                    if irow['activ'] != 0 and row[duration_key] > 0:
                        duration = self.validate_zone_duration(planned_seconds,
                                                               'manual program %s zone %s' % (prg, zone_id))
                        total_seconds += duration
                    elif irow['activ'] == 0 and row[duration_key] > 0:
                        now = datetime.datetime.now()
                        self.log_watering_event(
                            now, now, source, prg, irow['id'],
                            planned_seconds, 0, None, 'skipped_inactive'
                        )
                        log.info('watering_stop', 'zone skipped inactive',
                                 source=source, program_id=prg,
                                 zone_id=irow['id'],
                                 planned_seconds=planned_seconds)
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
                    log.info('relay_safety', 'transformer on',
                             source=source, program_id=prg)
                    self.hardware.transformer_on()
                for zone in manual_zones:
                    if not self.interruptible_sleep(1):
                        break
                    duration = zone['duration']
                    if duration > 0:
                        zone_expected_end_at = datetime.datetime.now() + datetime.timedelta(seconds=duration)
                        self.update_runtime_zone(zone['id'], zone_expected_end_at,
                                                 'manual program zone running')
                        started_at = datetime.datetime.now()
                        current_event = {
                            'started_at': started_at,
                            'source': source,
                            'program_id': prg,
                            'traseu_id': zone['id'],
                            'planned_seconds': duration,
                            'rain_credit_mm': None,
                        }
                        log.notice('watering_start', 'zone starting',
                                   source=source, program_id=prg,
                                   zone_id=zone['id'],
                                   duration_seconds=duration)
                        zone_completed = self.run_zone(zone['id'], zone['name'], zone['relay'], duration)
                        ended_at = datetime.datetime.now()
                        result = 'completed' if zone_completed else 'interrupted'
                        self.log_watering_event(
                            started_at, ended_at, source, prg, zone['id'],
                            duration, elapsed_seconds(started_at, ended_at),
                            None, result
                        )
                        log.notice('watering_stop', 'zone finished',
                                   source=source, program_id=prg,
                                   zone_id=zone['id'], result=result,
                                   actual_seconds=elapsed_seconds(started_at, ended_at))
                        current_event = None
                        if not zone_completed:
                            break
                log.notice('watering_stop', 'manual program finished',
                           source=source, program_id=prg)
                completed = True
            except Exception as exc:
                if current_event is not None:
                    ended_at = datetime.datetime.now()
                    result = exception_result(exc)
                    self.log_watering_event(
                        current_event['started_at'], ended_at,
                        current_event['source'], current_event['program_id'],
                        current_event['traseu_id'],
                        current_event['planned_seconds'],
                        elapsed_seconds(current_event['started_at'], ended_at),
                        current_event['rain_credit_mm'],
                        result, repr(exc)
                    )
                    log.err('watering_stop', 'zone failed',
                            source=current_event['source'],
                            program_id=current_event['program_id'],
                            zone_id=current_event['traseu_id'],
                            result=result, error=repr(exc))
                else:
                    now = datetime.datetime.now()
                    result = exception_result(exc)
                    self.log_watering_event(
                        now, now, source, prg, None,
                        None, 0, None, result, repr(exc)
                    )
                    log.err('watering_stop', 'manual program failed',
                            source=source, program_id=prg,
                            result=result, error=repr(exc))
                raise
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
            current_event = None
            try:
                self.hardware.set_led((1, 0, 1))
                log.notice('watering_start', 'scheduled program starting',
                           source=source, program_id=prg)
                self.stop_requested.clear()
                row = self.database.get_scheduled_program(prg)
                planned_full_seconds = row['durata'] * 60
                rain_credit_mm = float(row['rain_credit_mm'])
                rain_threshold_mm = float(row['rain_threshold_mm'])
                if not row['schedule_enabled']:
                    now = datetime.datetime.now()
                    self.log_watering_event(
                        now, now, source, prg, row['tid'],
                        planned_full_seconds, 0, rain_credit_mm,
                        'skipped_disabled'
                    )
                    log.info('watering_stop', 'schedule skipped disabled',
                             source=source, program_id=prg,
                             zone_id=row['tid'])
                elif row['zone_enabled']:
                    self.hardware.set_led((1, 0, 1))
                    a_releu = self.care_releu(int(row['tid']))
                    log.info('rain_update', 'rain credit evaluated',
                             program_id=prg, zone_id=row['tid'],
                             rain_credit_mm='%.3f' % rain_credit_mm,
                             rain_threshold_mm='%.3f' % rain_threshold_mm)
                    if rain_threshold_mm <= 0:
                        raise RuntimeError('Safety abort: scheduled program %s has rain_threshold_mm <= 0' % prg)
                    if rain_credit_mm < rain_threshold_mm:
                        duration = self.validate_zone_duration(
                            (rain_threshold_mm - rain_credit_mm) / rain_threshold_mm * row['durata'] * 60,
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
                                log.info('relay_safety', 'transformer on',
                                         source=source, program_id=prg)
                                self.hardware.transformer_on()
                            if not self.interruptible_sleep(1):
                                ended_at = datetime.datetime.now()
                                self.log_watering_event(
                                    started_at, ended_at, source, prg, row['tid'],
                                    duration, 0, rain_credit_mm, 'interrupted'
                                )
                                log.notice('watering_stop', 'scheduled program interrupted',
                                           source=source, program_id=prg,
                                           zone_id=row['tid'])
                                completed = True
                                return
                            zone_started_at = datetime.datetime.now()
                            current_event = {
                                'started_at': zone_started_at,
                                'source': source,
                                'program_id': prg,
                                'traseu_id': row['tid'],
                                'planned_seconds': duration,
                                'rain_credit_mm': rain_credit_mm,
                            }
                            log.notice('watering_start', 'zone starting',
                                       source=source, program_id=prg,
                                       zone_id=row['tid'],
                                       duration_seconds=duration)
                            zone_completed = self.run_zone(row['tid'], row['denumire'], a_releu, duration)
                            ended_at = datetime.datetime.now()
                            result = 'completed' if zone_completed else 'interrupted'
                            self.log_watering_event(
                                zone_started_at, ended_at, source, prg, row['tid'],
                                duration, elapsed_seconds(zone_started_at, ended_at),
                                rain_credit_mm, result
                            )
                            log.notice('watering_stop', 'zone finished',
                                       source=source, program_id=prg,
                                       zone_id=row['tid'], result=result,
                                       actual_seconds=elapsed_seconds(zone_started_at, ended_at))
                            current_event = None
                            if zone_completed:
                                self.interruptible_sleep(1)
                    else:
                        now = datetime.datetime.now()
                        self.log_watering_event(
                            now, now, source, prg, row['tid'],
                            planned_full_seconds, 0, rain_credit_mm,
                            'skipped_rain'
                        )
                        log.info('watering_stop', 'zone skipped rain',
                                 source=source, program_id=prg,
                                 zone_id=row['tid'],
                                 rain_credit_mm='%.3f' % rain_credit_mm,
                                 rain_threshold_mm='%.3f' % rain_threshold_mm)
                else:
                    now = datetime.datetime.now()
                    self.log_watering_event(
                        now, now, source, prg, row['tid'],
                        planned_full_seconds, 0, rain_credit_mm,
                        'skipped_inactive'
                    )
                    log.info('watering_stop', 'zone skipped inactive',
                             source=source, program_id=prg,
                             zone_id=row['tid'])
                self.database.reduce_rain_after_scheduled_program(row)
                log.notice('watering_stop', 'scheduled program finished',
                           source=source, program_id=prg)
                completed = True
            except Exception as exc:
                if current_event is not None:
                    ended_at = datetime.datetime.now()
                    result = exception_result(exc)
                    self.log_watering_event(
                        current_event['started_at'], ended_at,
                        current_event['source'], current_event['program_id'],
                        current_event['traseu_id'],
                        current_event['planned_seconds'],
                        elapsed_seconds(current_event['started_at'], ended_at),
                        current_event['rain_credit_mm'],
                        result, repr(exc)
                    )
                    log.err('watering_stop', 'zone failed',
                            source=current_event['source'],
                            program_id=current_event['program_id'],
                            zone_id=current_event['traseu_id'],
                            result=result, error=repr(exc))
                else:
                    now = datetime.datetime.now()
                    result = exception_result(exc)
                    self.log_watering_event(
                        now, now, source, prg, None,
                        None, 0, None, result, repr(exc)
                    )
                    log.err('watering_stop', 'scheduled program failed',
                            source=source, program_id=prg,
                            result=result, error=repr(exc))
                raise
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
        return self.hardware.run_zone(zone_id, zone_name, duration_seconds,
                                      self.interruptible_sleep)

    def status(self):
        db_ok, db_error = self.database.check_connection()
        runtime_state = None
        last_rain_update = None

        if db_ok:
            try:
                runtime_state = self.database.get_runtime_state()
                last_rain_update = self.database.get_last_rain_update()
            except Exception as exc:
                db_ok = False
                db_error = repr(exc)

        daemon_state = 'unknown'
        current_program = None
        current_zone = None
        remaining_seconds = None

        if runtime_state is not None:
            daemon_state = runtime_state.get('state') or daemon_state
            if daemon_state in ('running', 'stopping'):
                current_program = runtime_state.get('program_id')
                current_zone = runtime_state.get('traseu_id')
            remaining_seconds = calculate_remaining_seconds(runtime_state)

        with self.pending_watering_lock:
            pending_watering_commands = self.pending_watering_commands

        return {
            'ok': True,
            'daemon_state': daemon_state,
            'current_program': normalize_status_value(current_program),
            'current_zone': normalize_status_value(current_zone),
            'remaining_seconds': remaining_seconds,
            'last_rain_update': normalize_status_value(last_rain_update),
            'db': {
                'ok': db_ok,
                'error': db_error,
            },
            'relay_state': self.hardware.relay_states(),
            'runtime': normalize_status_value(runtime_state),
            'queue': {
                'pending_watering_commands': pending_watering_commands,
                'max_pending_watering_commands': MAX_PENDING_WATERING_COMMANDS,
            },
        }

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

    def log_watering_event(self, started_at, ended_at, source, program_id,
                           traseu_id, planned_seconds, actual_seconds,
                           rain_credit_mm, result, error=None):
        self.database.log_watering_event(
            started_at, ended_at, source, program_id, traseu_id,
            planned_seconds, actual_seconds, rain_credit_mm, result, error
        )

    def force_relays_off(self, reason):
        self.hardware.force_relays_off(reason)

    def restore_transformer_mode(self):
        self.hardware.restore_transformer_mode()


def elapsed_seconds(started_at, ended_at):
    return (ended_at - started_at).total_seconds()


def calculate_remaining_seconds(runtime_state):
    if runtime_state.get('state') not in ('running', 'stopping'):
        return 0

    expected_end_at = runtime_state.get('expected_end_at')
    if expected_end_at is None:
        return None

    remaining = (expected_end_at - datetime.datetime.now()).total_seconds()
    return max(0, int(round(remaining)))


def normalize_status_value(value):
    if isinstance(value, datetime.datetime):
        return value.isoformat()
    if isinstance(value, datetime.date):
        return value.isoformat()
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, dict):
        return {
            str(key): normalize_status_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [normalize_status_value(item) for item in value]
    return value


def exception_result(exc):
    if str(exc).startswith('Safety abort:'):
        return 'safety_abort'
    return 'failed'
