#!/usr/bin/python3
# -*- coding: utf-8 -*-
import configparser
import datetime
import os

import log


class ConfigError(Exception):
    pass


class IrigatieConfig:
    def __init__(self, path='irigatie.conf', debug=False):
        self.path = path
        self.debug = debug
        self.parser = self.read_parser(path)

        self.r_traf = self.get_int('ConectGPIO', 'R_TRAF', required=True)
        self.r_iri1 = self.get_int('ConectGPIO', 'R_IRI1', required=True)
        self.r_iri2 = self.get_int('ConectGPIO', 'R_IRI2', required=True)
        self.r_iri3 = self.get_int('ConectGPIO', 'R_IRI3', required=True)
        self.r_iri4 = self.get_int('ConectGPIO', 'R_IRI4', required=True)
        self.s_rain = self.get_int('ConectGPIO', 'S_RAIN', required=True)
        self.l_red = self.get_int('ConectGPIO', 'L_RED', required=True)
        self.l_green = self.get_int('ConectGPIO', 'L_GREEN', required=True)
        self.l_blue = self.get_int('ConectGPIO', 'L_BLUE', required=True)
        self.b_but1 = self.get_int('ConectGPIO', 'B_BUT1', required=True)
        self.b_but2 = self.get_int('ConectGPIO', 'B_BUT2', required=True)
        self.b_but3 = self.get_int('ConectGPIO', 'B_BUT3', required=True)
        self.b_but4 = self.get_int('ConectGPIO', 'B_BUT4', required=True)

        self.p_traf = self.get_text('Hardware Control', 'P_TRAF', required=True).strip()
        self.rain_on = self.get_int('Hardware Control', 'RAIN_ON', required=True)
        if self.p_traf not in ('Auto', 'On', 'Off'):
            raise ConfigError('[Hardware Control] P_TRAF must be Auto, On, or Off')
        if self.rain_on not in (0, 1):
            raise ConfigError('[Hardware Control] RAIN_ON must be 0 or 1')
        self.gpio_backend = self.get_text('Hardware Control', 'GPIO_BACKEND', required=True).strip().lower()
        if self.gpio_backend not in ('real', 'mock'):
            raise ConfigError('Invalid [Hardware Control] GPIO_BACKEND: %s' %
                              self.gpio_backend)

        self.max_zone_seconds = self.get_int('Safety', 'MAX_ZONE_SECONDS', required=True)
        self.max_program_seconds = self.get_int('Safety', 'MAX_PROGRAM_SECONDS', required=True)
        if self.max_zone_seconds <= 0:
            raise ConfigError('[Safety] MAX_ZONE_SECONDS must be greater than zero')
        if self.max_program_seconds <= 0:
            raise ConfigError('[Safety] MAX_PROGRAM_SECONDS must be greater than zero')

        self.rain_source = self.get_text('Rain', 'SOURCE', required=True).strip().lower()
        if self.rain_source not in ('hardware', 'openmeteo', 'manual', 'hybrid', 'disabled'):
            raise ConfigError('Invalid [Rain] SOURCE: %s' % self.rain_source)
        self.hardware_pulse_mm = self.get_float('Rain', 'HARDWARE_PULSE_MM', required=True)
        if self.hardware_pulse_mm <= 0:
            raise ConfigError('[Rain] HARDWARE_PULSE_MM must be greater than zero')
        self.hybrid_hardware_factor = self.get_float(
            'Rain', 'HYBRID_HARDWARE_FACTOR', default=0.0)
        self.hybrid_openmeteo_factor = self.get_float(
            'Rain', 'HYBRID_OPENMETEO_FACTOR', default=1.0)
        self.hybrid_manual_factor = self.get_float(
            'Rain', 'HYBRID_MANUAL_FACTOR', default=1.0)
        self.validate_rain_factor('HYBRID_HARDWARE_FACTOR',
                                  self.hybrid_hardware_factor)
        self.validate_rain_factor('HYBRID_OPENMETEO_FACTOR',
                                  self.hybrid_openmeteo_factor)
        self.validate_rain_factor('HYBRID_MANUAL_FACTOR',
                                  self.hybrid_manual_factor)

        self.db_server = self.get_text('SQL', 'DB_SERVER', required=True)
        self.db_port = self.get_int('SQL', 'DB_PORT', required=True)
        self.db_user = self.get_text('SQL', 'DB_USER', required=True)
        self.db_pass = self.get_text('SQL', 'DB_PASS', required=True)
        self.db_name = self.get_text('SQL', 'DB_NAME', required=True)

        self.socket_path = self.get_text(
            'Control Socket', 'SOCKET_PATH', required=True)
        self.socket_mode = self.get_mode('Control Socket', 'SOCKET_MODE', required=True)
        self.socket_owner = self.empty_to_none(
            self.get_text('Control Socket', 'SOCKET_OWNER', None))
        self.socket_group = self.empty_to_none(
            self.get_text('Control Socket', 'SOCKET_GROUP', None))

        self.debug_enabled = self.get_bool('Deeebug', 'Deeebug', False)
        self.debug = self.debug_enabled or bool(debug)

        self.validate()

    def read_parser(self, path):
        if not os.path.exists(path):
            raise ConfigError('Config file not found: %s' % path)
        parser = configparser.ConfigParser()
        try:
            with open(path) as config_file:
                parser.read_file(config_file)
        except configparser.Error as exc:
            raise ConfigError('Could not parse config file %s: %s' %
                              (path, exc))
        return parser

    def get_int(self, section, option, default=None, required=False):
        value = self._read(section, option, as_int=True, required=required)
        return default if value is None else value

    def get_text(self, section, option, default=None, required=False):
        value = self._read(section, option, as_int=False, required=required)
        return default if value is None else value

    def get_float(self, section, option, default=None, required=False):
        value = self._read(section, option, as_float=True, required=required)
        return default if value is None else value

    def get_bool(self, section, option, default=None, required=False):
        value = self._read(section, option, as_bool=True, required=required)
        return default if value is None else value

    def get_mode(self, section, option, default=None, required=False):
        value = self._read(section, option, as_int=False, required=required)
        if value is None:
            return default
        try:
            return int(str(value), 8)
        except ValueError:
            raise ConfigError('Invalid octal mode [%s] %s: %s' %
                              (section, option, value))

    def _read(self, section, option, as_int=False, as_float=False, as_bool=False,
              required=False):
        try:
            if as_int:
                value = self.parser.getint(section, option)
            elif as_float:
                value = self.parser.getfloat(section, option)
            elif as_bool:
                value = self.parser.getboolean(section, option)
            else:
                value = self.parser.get(section, option)
            if 'pass' in option.lower():
                log.debug(self.debug, 'startup', 'config value loaded',
                          option=option, value='********')
            else:
                log.debug(self.debug, 'startup', 'config value loaded',
                          option=option, value=value)
            return value
        except configparser.NoSectionError:
            if required:
                raise ConfigError('Missing required config section [%s]' % section)
            return None
        except configparser.NoOptionError:
            if required:
                raise ConfigError('Missing required config option [%s] %s' %
                                  (section, option))
            return None
        except ValueError as exc:
            raise ConfigError('Invalid config value [%s] %s: %s' %
                              (section, option, exc))

    def _debug_error(self, message):
        log.debug(self.debug, 'startup', message,
                  timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))

    def empty_to_none(self, value):
        if value is None:
            return None
        value = value.strip()
        return None if value == '' else value

    def validate(self):
        self.validate_gpio_pins()
        if self.socket_mode != 0o660:
            raise ConfigError('[Control Socket] SOCKET_MODE must be 0660')
        if not self.socket_path.startswith('/'):
            raise ConfigError('[Control Socket] SOCKET_PATH must be absolute')

    def validate_rain_factor(self, name, value):
        if value < 0:
            raise ConfigError('[Rain] %s must be non-negative' % name)
        if value > 1:
            raise ConfigError('[Rain] %s must be less than or equal to 1' %
                              name)

    def validate_gpio_pins(self):
        pins = {
            'R_TRAF': self.r_traf,
            'R_IRI1': self.r_iri1,
            'R_IRI2': self.r_iri2,
            'R_IRI3': self.r_iri3,
            'R_IRI4': self.r_iri4,
            'S_RAIN': self.s_rain,
            'L_RED': self.l_red,
            'L_GREEN': self.l_green,
            'L_BLUE': self.l_blue,
            'B_BUT1': self.b_but1,
            'B_BUT2': self.b_but2,
            'B_BUT3': self.b_but3,
            'B_BUT4': self.b_but4,
        }
        for name, pin in pins.items():
            if pin < 0:
                raise ConfigError('[ConectGPIO] %s must be non-negative' % name)
        seen = {}
        for name, pin in pins.items():
            if pin in seen:
                raise ConfigError('[ConectGPIO] %s and %s use duplicate GPIO %s' %
                                  (seen[pin], name, pin))
            seen[pin] = name

    def log_effective_config(self):
        log.info('startup', 'effective GPIO pin mapping',
                 r_traf=self.r_traf,
                 r_iri1=self.r_iri1,
                 r_iri2=self.r_iri2,
                 r_iri3=self.r_iri3,
                 r_iri4=self.r_iri4,
                 s_rain=self.s_rain,
                 l_red=self.l_red,
                 l_green=self.l_green,
                 l_blue=self.l_blue,
                 b_but1=self.b_but1,
                 b_but2=self.b_but2,
                 b_but3=self.b_but3,
                 b_but4=self.b_but4)
        log.info('rain_update', 'effective rain source',
                 source=self.rain_source,
                 hardware_pulse_mm=self.hardware_pulse_mm,
                 hybrid_hardware_factor=self.hybrid_hardware_factor,
                 hybrid_openmeteo_factor=self.hybrid_openmeteo_factor,
                 hybrid_manual_factor=self.hybrid_manual_factor)
        log.info('startup', 'effective DB target',
                 host=self.db_server,
                 port=self.db_port,
                 user=self.db_user,
                 database=self.db_name)
        log.info('startup', 'effective control socket',
                 path=self.socket_path,
                 mode='0%o' % self.socket_mode,
                 owner=self.socket_owner,
                 group=self.socket_group)


def load_config(path='irigatie.conf', debug=False):
    return IrigatieConfig(path, debug)
