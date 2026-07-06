#!/usr/bin/python3
# -*- coding: utf-8 -*-
import datetime
import syslog
import time

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
        syslog.syslog(syslog.LOG_INFO, 'MOCK GPIO ON %s GPIO%s' % (self.name, self.pin))

    def off(self):
        self.is_active = False
        syslog.syslog(syslog.LOG_INFO, 'MOCK GPIO OFF %s GPIO%s' % (self.name, self.pin))

    def close(self):
        syslog.syslog(syslog.LOG_INFO, 'MOCK GPIO CLOSE %s GPIO%s' % (self.name, self.pin))


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
        syslog.syslog(syslog.LOG_INFO, 'MOCK GPIO LED RGB%s' % (value,))

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
        syslog.syslog(syslog.LOG_INFO, 'MOCK GPIO CLOSE RGB LED GPIO%s,%s,%s' % (self.red_pin, self.green_pin, self.blue_pin))


class MockInput:
    def __init__(self, name, pin):
        self.name = name
        self.pin = pin
        self.when_activated = None

    def close(self):
        syslog.syslog(syslog.LOG_INFO, 'MOCK GPIO CLOSE %s GPIO%s' % (self.name, self.pin))


class GpioHardware:
    def __init__(self, config, on_rain, on_button, debug=False):
        self.config = config
        self.on_rain = on_rain
        self.on_button = on_button
        self.debug = debug
        self.backend = config.gpio_backend

        syslog.syslog(syslog.LOG_INFO, 'GPIO backend: ' + self.backend)
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
            syslog.syslog(syslog.LOG_INFO, 'MOCK GPIO skip rain sensor setup GPIO%s' % pin)
            return MockInput('senzor de ploaie', pin)
        sensor = gpiozero.DigitalInputDevice(pin, pull_up=True)
        sensor.when_activated = self.on_rain
        return sensor

    def _buttons(self, config):
        if self.backend == 'mock':
            syslog.syslog(syslog.LOG_INFO, 'MOCK GPIO skip button setup')
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
            syslog.syslog(syslog.LOG_INFO, 'Releul de traf este in mod Always ON')
            self._debug(': Releul de traf este in mod Always ON', '\033[0;33m')
            self.releu_traf.on()
        else:
            syslog.syslog(syslog.LOG_INFO, 'Releul de traf este in mod AUTO')
            self._debug(': Releul de traf este in mod AUTO', '\033[0;33m')

    def restore_transformer_mode(self):
        if self.config.p_traf == 'On':
            syslog.syslog(syslog.LOG_INFO, 'Reporneste traful: mod Always ON')
            self.releu_traf.on()

    def force_relays_off(self, reason):
        relays = [('traf', self.releu_traf)]
        for zone_id, relay in sorted(self.zone_relays.items()):
            relays.append(('irigatie %s' % zone_id, relay))
        for name, relay in relays:
            relay.off()
            syslog.syslog(syslog.LOG_INFO, 'Opreste releu %s: %s' % (name, reason))

    def run_zone(self, zone_id, zone_name, duration_seconds, sleep_fn):
        relay = self.zone_relays[zone_id]
        self._debug(': Deschide traseul ' + zone_name + '...', '\033[0;36m')
        syslog.syslog('Deschide traseul ' + zone_name)
        relay.on()
        try:
            self._debug(': Uda timp de ' + str(duration_seconds) + ' secunde', '\033[0;36m')
            syslog.syslog('Uda timp de ' + str(duration_seconds) + ' secunde')
            sleep_fn(duration_seconds)
        finally:
            self._debug(': Inchide traseul ' + zone_name + '...', '\033[0;36m')
            syslog.syslog('Inchide traseul ' + zone_name)
            relay.off()

    def status_led_loop(self, stop_event, interval):
        while not stop_event.is_set():
            self.led.color = (abs(self.led.red - 0.3), abs(self.led.green - 0.3), abs(self.led.blue - 0.3))
            time.sleep(0.5)
            event_is_set = stop_event.wait(interval)
            if event_is_set:
                syslog.syslog(syslog.LOG_ERR, 'Main thread intrerupt')
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
        if self.debug:
            print(color + str(datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")) + message + '\033[0m')
