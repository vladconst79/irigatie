#!/usr/bin/python3
# -*- coding: utf-8 -*-
import datetime
import time

import log

try:
    import gpiozero
except ImportError:
    gpiozero = None


class MockRelay:
    def __init__(self, name, pin):
        self.name = name
        self.pin = pin
        self.is_active = False

    def on(self):
        self.is_active = True
        log.info('relay_safety', 'mock relay on', name=self.name, gpio=self.pin)

    def off(self):
        self.is_active = False
        log.info('relay_safety', 'mock relay off', name=self.name, gpio=self.pin)

    def close(self):
        log.info('relay_safety', 'mock relay close', name=self.name, gpio=self.pin)


class MockLed:
    def __init__(self, red, green, blue):
        self.red_pin = red
        self.green_pin = green
        self.blue_pin = blue
        self._color = (0, 0, 0)

    @property
    def color(self):
        return self._color

    @color.setter
    def color(self, value):
        self._color = value
        log.info('startup', 'mock LED set', rgb=value)

    @property
    def red(self):
        return self._color[0]

    @property
    def green(self):
        return self._color[1]

    @property
    def blue(self):
        return self._color[2]

    def off(self):
        self.color = (0, 0, 0)

    def close(self):
        log.info('shutdown', 'mock LED close',
                 red_gpio=self.red_pin, green_gpio=self.green_pin,
                 blue_gpio=self.blue_pin)


class MockInput:
    def __init__(self, name, pin):
        self.name = name
        self.pin = pin
        self.when_activated = None

    def close(self):
        log.info('shutdown', 'mock input close', name=self.name, gpio=self.pin)


class GpioHardware:
    def __init__(self, config, on_rain, on_button, debug=False):
        self.config = config
        self.on_rain = on_rain
        self.on_button = on_button
        self.debug = debug
        self.backend = config.gpio_backend

        log.info('startup', 'GPIO backend selected', backend=self.backend)
        if self.backend == 'real' and gpiozero is None:
            raise RuntimeError('GPIO_BACKEND=real requires gpiozero')

        self.releu_traf = self._relay('traf', config.r_traf)
        self.zone_relays = {
            1: self._relay('irigatie 1', config.r_iri1),
            2: self._relay('irigatie 2', config.r_iri2),
            3: self._relay('irigatie 3', config.r_iri3),
            4: self._relay('irigatie 4', config.r_iri4),
        }
        self.zone_gpio_pins = {
            1: config.r_iri1,
            2: config.r_iri2,
            3: config.r_iri3,
            4: config.r_iri4,
        }
        self.led = self._led(config.l_red, config.l_green, config.l_blue)
        self.senzor_ploaie = self._rain_sensor(config.s_rain)
        self.buttons = self._buttons(config)

    def _button_handler(self, zone_id):
        def callback():
            self.on_button(zone_id)
        return callback

    def _relay(self, name, pin):
        if self.backend == 'mock':
            return MockRelay(name, pin)
        return gpiozero.DigitalOutputDevice(pin)

    def _led(self, red, green, blue):
        if self.backend == 'mock':
            return MockLed(red, green, blue)
        return gpiozero.RGBLED(red=red, green=green, blue=blue, pwm=True)

    def _rain_sensor(self, pin):
        if self.backend == 'mock':
            log.info('startup', 'mock rain sensor setup skipped', gpio=pin)
            return MockInput('senzor de ploaie', pin)
        sensor = gpiozero.DigitalInputDevice(pin, pull_up=True)
        sensor.when_activated = self.on_rain
        return sensor

    def _buttons(self, config):
        if self.backend == 'mock':
            log.info('startup', 'mock button setup skipped')
            return {}
        buttons = {
            1: gpiozero.Button(config.b_but1, bounce_time=0.2, pull_up=True),
            2: gpiozero.Button(config.b_but2, bounce_time=0.2, pull_up=True),
            3: gpiozero.Button(config.b_but3, bounce_time=0.2, pull_up=True),
            4: gpiozero.Button(config.b_but4, bounce_time=0.2, pull_up=True),
        }
        for zone_id, button in buttons.items():
            button.when_pressed = self._button_handler(zone_id)
        return buttons

    def get_zone_relay(self, zone_id):
        return self.zone_relays.get(zone_id, False)

    def relay_states(self):
        return {
            'transformer': self.relay_state(self.releu_traf),
            'zones': {
                str(zone_id): self.relay_state(relay)
                for zone_id, relay in sorted(self.zone_relays.items())
            },
        }

    def relay_state(self, relay):
        active = getattr(relay, 'is_active', None)
        value = getattr(relay, 'value', None)
        return {
            'active': bool(active) if active is not None else None,
            'value': value,
        }

    def set_led(self, color):
        self.led.color = color

    def led_off(self):
        self.led.off()

    def transformer_on(self):
        self.releu_traf.on()

    def transformer_off(self):
        self.releu_traf.off()

    def initialize_transformer_mode(self):
        if self.config.p_traf == 'On':
            log.info('startup', 'transformer mode initialized', mode='always_on')
            self._debug(': Releul de traf este in mod Always ON', '\033[0;33m')
            self.releu_traf.on()
        elif self.config.p_traf == 'Off':
            log.info('startup', 'transformer mode initialized', mode='off')
            self._debug(': Releul de traf este in mod OFF', '\033[0;33m')
        else:
            log.info('startup', 'transformer mode initialized', mode='auto')
            self._debug(': Releul de traf este in mod AUTO', '\033[0;33m')

    def restore_transformer_mode(self):
        if self.config.p_traf == 'On':
            log.info('relay_safety', 'restore transformer always-on mode')
            self.releu_traf.on()

    def force_relays_off(self, reason):
        relays = [('traf', self.releu_traf)]
        for zone_id, relay in sorted(self.zone_relays.items()):
            relays.append(('irigatie %s' % zone_id, relay))
        for name, relay in relays:
            relay.off()
            log.info('relay_safety', 'forced relay off', name=name, reason=reason)

    def run_zone(self, zone_id, zone_name, duration_seconds, sleep_fn):
        relay = self.zone_relays[zone_id]
        self._debug(': Deschide traseul ' + zone_name + '...', '\033[0;36m')
        log.info('watering_start', 'relay opened',
                 zone_id=zone_id, zone_name=zone_name)
        relay.on()
        try:
            self._debug(': Uda timp de ' + str(duration_seconds) + ' secunde', '\033[0;36m')
            log.info('watering_start', 'zone sleep started',
                     zone_id=zone_id, duration_seconds=duration_seconds)
            return sleep_fn(duration_seconds)
        finally:
            self._debug(': Inchide traseul ' + zone_name + '...', '\033[0;36m')
            log.info('watering_stop', 'relay closed',
                     zone_id=zone_id, zone_name=zone_name)
            relay.off()

    def status_led_loop(self, stop_event, interval):
        while not stop_event.is_set():
            self.led.color = (abs(self.led.red - 0.3), abs(self.led.green - 0.3), abs(self.led.blue - 0.3))
            time.sleep(0.5)
            event_is_set = stop_event.wait(interval)
            if event_is_set:
                log.err('shutdown', 'status LED loop interrupted')
                self._debug(': Main thread intrerupt!', '\033[41m')
                self.led.off()
                self._debug(': Reseteaza GPIO' + str(self.config.l_red) + ', ' + str(self.config.l_green) + ', ' + str(self.config.l_blue) + ', LED RGB', '\033[41m')
                self.led.close()
            else:
                self.led.color = (not self.led.red, not self.led.green, not self.led.blue)
                time.sleep(0.5)

    def close(self):
        self._close_input('senzor de ploaie', self.config.s_rain, self.senzor_ploaie)
        for zone_id, button in sorted(self.buttons.items()):
            pin = getattr(self.config, 'b_but%s' % zone_id)
            self._close_input('buton ' + str(zone_id), pin, button)
        self._debug(': Reseteaza GPIO' + str(self.config.r_traf) + ', releu traf', '\033[41m')
        self.releu_traf.close()
        for zone_id, relay in sorted(self.zone_relays.items()):
            self._debug(': Reseteaza GPIO' + str(self.zone_gpio_pins[zone_id]) + ', releu irigatie ' + str(zone_id), '\033[41m')
            relay.close()

    def _close_input(self, label, pin, device):
        self._debug(': Reseteaza GPIO' + str(pin) + ', ' + label, '\033[41m')
        device.close()

    def _debug(self, message, color):
        log.debug(self.debug, 'startup', message,
                  timestamp=datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f"))
