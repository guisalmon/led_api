#!/usr/bin/env python3
import RPi.GPIO as GPIO
from gpiozero import Button
import numpy as np
import pyaudio
from flask import Flask, jsonify, request
from rpi_ws281x import *
import time
import threading
import clock
import film_light

BIT1_PIN = 27
BIT2_PIN = 22   # violet
BIT3_PIN = 23   # rose
BIT4_PIN = 24
POWER_PIN = 16
SOUND_PIN = 20

GPIO.setmode(GPIO.BCM)
GPIO.setup(BIT1_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(BIT2_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(BIT3_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(BIT4_PIN, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)
GPIO.setup(POWER_PIN, GPIO.OUT)
GPIO.setup(SOUND_PIN, GPIO.OUT)

STRIP = film_light.init_strip()

on = False


class Clock(threading.Thread):
    def __init__(self, clock):
        threading.Thread.__init__(self)
        self.daemon = True
        self.runnable = clock

    def run(self):
        self.runnable()


def toggle(bit):
    print('{}'.format(bit))


def toggle_clock_backlight():
    clock.toggle_clock_backlight()


def toggle_film_light():
    film_light.toggle_light(STRIP)


def toggle_sound():
    GPIO.output(SOUND_PIN, GPIO.LOW)
    time.sleep(50 / 1000)
    GPIO.output(SOUND_PIN, GPIO.HIGH)


def toggle_power():
    global on
    if on:
        GPIO.output(POWER_PIN, GPIO.HIGH)
        on = False
    else:
        GPIO.output(POWER_PIN, GPIO.LOW)
        on = True


if __name__ == '__main__':
    print("Up and running!")
    clock_thread = Clock(clock.clock)
    clock_thread.start()

    GPIO.add_event_detect(BIT1_PIN, GPIO.RISING, callback=lambda x: toggle_clock_backlight(), bouncetime=500)
    GPIO.add_event_detect(BIT2_PIN, GPIO.RISING, callback=lambda x: toggle_film_light(), bouncetime=500)
    GPIO.add_event_detect(BIT3_PIN, GPIO.RISING, callback=lambda x: toggle_power(), bouncetime=500)
    GPIO.add_event_detect(BIT4_PIN, GPIO.RISING, callback=lambda x: toggle_sound(), bouncetime=500)

    GPIO.output(SOUND_PIN, GPIO.HIGH)
    GPIO.output(POWER_PIN, GPIO.HIGH)

    while True:
        time.sleep(1)
