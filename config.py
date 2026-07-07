#!/usr/bin/python3
# -*- coding: utf-8 -*-
import configparser
import datetime

import log


class IrigatieConfig:
    def __init__(self, path='irigatie.conf', debug=False):
        self.path = path
        self.debug = debug

        self.r_traf = self.get_int('ConectGPIO', 'R_TRAF', 18)
        self.r_iri1 = self.get_int('ConectGPIO', 'R_IRI1', 21)
        self.r_iri2 = self.get_int('ConectGPIO', 'R_IRI2', 20)
        self.r_iri3 = self.get_int('ConectGPIO', 'R_IRI3', 16)
        self.r_iri4 = self.get_int('ConectGPIO', 'R_IRI4', 12)
        self.s_rain = self.get_int('ConectGPIO', 'S_RAIN', 23)
        self.l_red = self.get_int('ConectGPIO', 'L_RED', 19)
        self.l_green = self.get_int('ConectGPIO', 'L_GREEN', 13)
        self.l_blue = self.get_int('ConectGPIO', 'L_BLUE', 26)
        self.b_but1 = self.get_int('ConectGPIO', 'B_BUT1', 9)
        self.b_but2 = self.get_int('ConectGPIO', 'B_BUT2', 11)
        self.b_but3 = self.get_int('ConectGPIO', 'B_BUT3', 22)
        self.b_but4 = self.get_int('ConectGPIO', 'B_BUT4', 10)

        self.p_traf = self.get_text('Hardware Control', 'P_TRAF', 'Auto')
        self.rain_on = self.get_int('Hardware Control', 'RAIN_ON', 1)
        self.gpio_backend = self.get_text('Hardware Control', 'GPIO_BACKEND', 'real').strip().lower()
        if self.gpio_backend not in ('real', 'mock'):
            log.err('startup', 'invalid GPIO_BACKEND, using real',
                    value=self.gpio_backend)
            self.gpio_backend = 'real'

        self.max_zone_seconds = self.get_int('Safety', 'MAX_ZONE_SECONDS', 3600)
        self.max_program_seconds = self.get_int('Safety', 'MAX_PROGRAM_SECONDS', 7200)

        self.rain_source = self.get_text('Rain', 'SOURCE', 'openmeteo').strip().lower()
        if self.rain_source not in ('hardware', 'openmeteo', 'manual', 'hybrid', 'disabled'):
            log.err('rain_update', 'invalid rain source, using openmeteo',
                    value=self.rain_source)
            self.rain_source = 'openmeteo'
        self.hardware_pulse_mm = self.get_float('Rain', 'HARDWARE_PULSE_MM', 0.2794)
        if self.hardware_pulse_mm <= 0:
            log.err('rain_update', 'invalid hardware pulse size, using default',
                    value=self.hardware_pulse_mm)
            self.hardware_pulse_mm = 0.2794

        self.db_server = self.get_text('SQL', 'DB_SERVER', '127.0.0.1')
        self.db_port = self.get_text('SQL', 'DB_PORT', '3306')
        self.db_user = self.get_text('SQL', 'DB_USER', 'irigatie_user')
        self.db_pass = self.get_text('SQL', 'DB_PASS', '')
        self.db_name = self.get_text('SQL', 'DB_NAME', 'irigatie')

        self.socket_path = self.get_text(
            'Control Socket', 'SOCKET_PATH', '/run/irigatie/control.sock')
        self.socket_mode = self.get_mode('Control Socket', 'SOCKET_MODE', 0o660)
        self.socket_owner = self.empty_to_none(
            self.get_text('Control Socket', 'SOCKET_OWNER', None))
        self.socket_group = self.empty_to_none(
            self.get_text('Control Socket', 'SOCKET_GROUP', None))

        self.debug_enabled = self.get_bool('Deeebug', 'Deeebug', False)
        self.debug = self.debug_enabled or bool(debug)

    def get_int(self, section, option, default=None):
        value = self._read(section, option, as_int=True)
        return default if value is None else value

    def get_text(self, section, option, default=None):
        value = self._read(section, option, as_int=False)
        return default if value is None else value

    def get_float(self, section, option, default=None):
        value = self._read(section, option, as_float=True)
        return default if value is None else value

    def get_bool(self, section, option, default=None):
        value = self._read(section, option, as_bool=True)
        return default if value is None else value

    def get_mode(self, section, option, default=None):
        value = self._read(section, option, as_int=False)
        if value is None:
            return default
        try:
            return int(str(value), 8)
        except ValueError:
            self._debug_error('Valoarea ' + option + ' nu este un mod octal valid!!!')
            log.err('startup', 'invalid octal mode', option=option)
            return default

    def _read(self, section, option, as_int=False, as_float=False, as_bool=False):
        parser = configparser.ConfigParser()
        try:
            with open(self.path) as config_file:
                parser.read_file(config_file)
        except IOError:
            self._debug_error('Fisierul ' + self.path + ' nu exista!!!')
            log.err('startup', 'config file missing', path=self.path)
            return None

        try:
            if as_int:
                value = parser.getint(section, option)
            elif as_float:
                value = parser.getfloat(section, option)
            elif as_bool:
                value = parser.getboolean(section, option)
            else:
                value = parser.get(section, option)
            if 'pass' in option.lower():
                log.debug(self.debug, 'startup', 'config value loaded',
                          option=option, value='********')
            else:
                log.debug(self.debug, 'startup', 'config value loaded',
                          option=option, value=value)
            return value
        except configparser.NoSectionError:
            self._debug_error('Sectiunea ' + section + ' nu exista!!!')
            log.err('startup', 'config section missing', section=section)
            return None
        except configparser.NoOptionError:
            self._debug_error('Valoarea ' + option + ' nu exista!!!')
            log.err('startup', 'config option missing',
                    section=section, option=option)
            return None

    def _debug_error(self, message):
        log.debug(self.debug, 'startup', message,
                  timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))

    def empty_to_none(self, value):
        if value is None:
            return None
        value = value.strip()
        return None if value == '' else value


def load_config(path='irigatie.conf', debug=False):
    return IrigatieConfig(path, debug)
