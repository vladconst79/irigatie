#!/usr/bin/python3
# -*- coding: utf-8 -*-

import configparser
import syslog

import gpiozero
import log


CONF_FILE = 'irigatie.conf'


def read_pin(config, option, default):
    try:
        return config.getint('ConectGPIO', option)
    except configparser.Error:
        return default


def main():
    syslog.openlog('irigatie-relays-off')

    config = configparser.ConfigParser()
    config.read(CONF_FILE)

    relay_pins = [
        ('transformer', read_pin(config, 'R_TRAF', 18)),
        ('zone 1', read_pin(config, 'R_IRI1', 21)),
        ('zone 2', read_pin(config, 'R_IRI2', 20)),
        ('zone 3', read_pin(config, 'R_IRI3', 16)),
        ('zone 4', read_pin(config, 'R_IRI4', 12)),
    ]

    relays = []
    try:
        for name, pin in relay_pins:
            relay = gpiozero.DigitalOutputDevice(pin)
            relays.append((name, pin, relay))
            relay.off()
            log.info('relay_safety', 'boot relay forced off',
                     name=name, gpio=pin)
    finally:
        for name, pin, relay in relays:
            relay.close()

    return 0


if __name__ == '__main__':
    raise SystemExit(main())
