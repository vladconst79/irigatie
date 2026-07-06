#!/usr/bin/python3
# -*- coding: utf-8 -*-
import configparser
import datetime
import syslog


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
            syslog.syslog(syslog.LOG_ERR, 'GPIO_BACKEND invalid: ' + self.gpio_backend + ', using real')
            self.gpio_backend = 'real'

        self.max_zone_seconds = self.get_int('Safety', 'MAX_ZONE_SECONDS', 3600)
        self.max_program_seconds = self.get_int('Safety', 'MAX_PROGRAM_SECONDS', 7200)

        self.db_server = self.get_text('SQL', 'DB_SERVER', '127.0.0.1')
        self.db_port = self.get_text('SQL', 'DB_PORT', '3306')
        self.db_user = self.get_text('SQL', 'DB_USER', 'irigatie_user')
        self.db_pass = self.get_text('SQL', 'DB_PASS', '')
        self.db_name = self.get_text('SQL', 'DB_NAME', 'irigatie')

    def get_int(self, section, option, default=None):
        value = self._read(section, option, as_int=True)
        return default if value is None else value

    def get_text(self, section, option, default=None):
        value = self._read(section, option, as_int=False)
        return default if value is None else value

    def _read(self, section, option, as_int):
        parser = configparser.ConfigParser()
        try:
            with open(self.path) as config_file:
                parser.read_file(config_file)
        except IOError:
            self._debug_error('Fisierul ' + self.path + ' nu exista!!!')
            syslog.syslog(syslog.LOG_ERR, 'Fisierul ' + self.path + ' nu exista!!!')
            return None

        try:
            value = parser.getint(section, option) if as_int else parser.get(section, option)
            if 'pass' in option.lower():
                syslog.syslog(option + ' = ********')
            else:
                syslog.syslog(option + ' = ' + str(value))
            if self.debug:
                print(str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': ' + option + ' = ' + str(value))
            return value
        except configparser.NoSectionError:
            self._debug_error('Sectiunea ' + section + ' nu exista!!!')
            syslog.syslog(syslog.LOG_ERR, 'Sectiunea ' + section + ' nu exista!!!')
            return None
        except configparser.NoOptionError:
            self._debug_error('Valoarea ' + option + ' nu exista!!!')
            syslog.syslog(syslog.LOG_ERR, 'Valoarea ' + option + ' nu exista!!!')
            return None

    def _debug_error(self, message):
        if self.debug:
            print('\033[41m' + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + ': ' + message + '\033[0m')


def load_config(path='irigatie.conf', debug=False):
    return IrigatieConfig(path, debug)
