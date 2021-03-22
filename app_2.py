import math
import threading
import time
import faulthandler

import RPi.GPIO as GPIO
import numpy as np
import pyaudio
from flask import Flask, jsonify, request
from rpi_ws281x import *

app = Flask(__name__)

LED_PIN = 18  # GPIO pin connected to the pixels (18 uses PWM!).
POWER_PIN = 4
SOUND_PIN = 17
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10  # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 255  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False  # True to invert the signal (when using NPN transistor
LED_CHANNEL = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53
LED_STRIPES_LENGTH = 10
LED_STRIPES_COUNT = 12
LED_CONTROL_COUNT = 2
LED_LIGHT_COUNT = 20
LED_LIGHT_2_COUNT = 8
LED_EQ_COUNT = LED_STRIPES_LENGTH * LED_STRIPES_COUNT
LED_COUNT = LED_EQ_COUNT  # + LED_CONTROL_COUNT + LED_LIGHT_COUNT + LED_LIGHT_2_COUNT  # Number of LED pixels.
LED_COLOR_LIST_SIZE = LED_EQ_COUNT + LED_CONTROL_COUNT + LED_LIGHT_COUNT + LED_LIGHT_2_COUNT  # Number of LED pixels.
# Create NeoPixel object with appropriate configuration.
STRIP = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)

brightness_eq = 63
color1_red = 175
color1_green = 0
color1_blue = 255
color2_red = 255
color2_green = 0
color2_blue = 4
increment_red = (color1_red - color2_red) / LED_STRIPES_LENGTH
increment_green = (color1_green - color2_green) / LED_STRIPES_LENGTH
increment_blue = (color1_blue - color2_blue) / LED_STRIPES_LENGTH
color_gradient = [[0, 0, 0]] * LED_STRIPES_LENGTH
led_color_list = [0] * LED_COLOR_LIST_SIZE

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(POWER_PIN, GPIO.OUT)
GPIO.setup(SOUND_PIN, GPIO.OUT)

# mic sensitivity correction and bit conversion
# mic_sens_dBV = -47.0  # mic sensitivity in dBV + any gain
# mic_sens_dBV = -25.0  # mic sensitivity in dBV + any gain
# mic_sens_dBV = 0  # mic sensitivity in dBV + any gain
mic_sens_dBV = -10  # mic sensitivity in dBV + any gain
mic_sens_corr = np.power(10.0, mic_sens_dBV / 20.0)  # calculate mic sensitivity conversion factor

min_freq = 20
max_freq = 8000
form_1 = pyaudio.paInt16  # 16-bit resolution
chans = 1  # 1 channel
samp_rate = 44100  # 44.1kHz sampling rate
chunk = 512  # 2^12 samples for buffer
dev_index = 1  # device index found by p.get_device_info_by_index(ii)
fft_correction = [0.0] * (int(chunk / 2))
min_mean_lvls = [10.0] * LED_STRIPES_COUNT
max_mean_lvls = [-10.0] * LED_STRIPES_COUNT
AUDIO_LVLS_MEM_SIZE = 1024
auto_min_max = False

audio_mean_lvls = [[0.0] * LED_STRIPES_COUNT] * AUDIO_LVLS_MEM_SIZE
audio_mean_lvls_index = 0


def hex_to_rgb(value):
    value = value.lstrip('#')
    rgb = list(int(value[i:i + 2], 16) for i in (0, 2, 4))
    return rgb


def rgb_to_hex(r, g, b):
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)


def power_on():
    GPIO.output(POWER_PIN, GPIO.LOW)


def power_off():
    GPIO.output(POWER_PIN, GPIO.HIGH)


def color(r, g, b):
    return (r << 16) + (g << 8) + b


def get_color_between_bounds(color_index):
    color_gradient[color_index][0] = int(color2_red + color_index * increment_red)
    color_gradient[color_index][1] = int(color2_green + color_index * increment_green)
    color_gradient[color_index][2] = int(color2_blue + color_index * increment_blue)


def update_gradient():
    for i in range(LED_STRIPES_LENGTH):
        get_color_between_bounds(i)


def set_pixel_color(index, r, g, b, brightness_override):
    led_color_list[index] = color(int((r / 255) * brightness_override),
                                  int((g / 255) * brightness_override),
                                  int((b / 255) * brightness_override))


def show():
    for i in range(LED_COUNT):
        STRIP.setPixelColor(i, led_color_list[i])
    STRIP.show()


def light_stripe(stripe_index, length=LED_STRIPES_LENGTH):
    if stripe_index < LED_EQ_COUNT / LED_STRIPES_LENGTH:
        if (stripe_index % 2) == 0:
            for i in range(1, LED_STRIPES_LENGTH + 1):
                if i <= length:
                    set_pixel_color(stripe_index * LED_STRIPES_LENGTH + (i - 1),
                                    color_gradient[i - 1][0], color_gradient[i - 1][1], color_gradient[i - 1][2],
                                    (brightness_eq / LED_STRIPES_LENGTH ** 2) *
                                    (LED_STRIPES_LENGTH - (length - i)) * length)
                elif i > length:
                    set_pixel_color(stripe_index * LED_STRIPES_LENGTH + (i - 1), 0, 0, 0, 0)
        else:
            for i in range(1, LED_STRIPES_LENGTH + 1):
                if i <= length:
                    set_pixel_color(stripe_index * LED_STRIPES_LENGTH + 10 - i,
                                    color_gradient[i - 1][0], color_gradient[i - 1][1], color_gradient[i - 1][2],
                                    (brightness_eq / LED_STRIPES_LENGTH ** 2) *
                                    (LED_STRIPES_LENGTH - (length - i)) * length)
                elif i > length:
                    set_pixel_color(stripe_index * LED_STRIPES_LENGTH + 10 - i, 0, 0, 0, 0)


def uniform_color(r, g, b):
    # print(r, g, b, " color ", color(r, g, b))
    for i in range(LED_EQ_COUNT):
        set_pixel_color(i, r, g, b, brightness_eq)
    show()


def json_config():
    return jsonify(
        {"freqMin": min_freq, "freqMax": max_freq, "fftCorrection": fft_correction,
         "color1": rgb_to_hex(color1_red, color1_green, color1_blue),
         "color2": rgb_to_hex(color2_red, color2_green, color2_blue), "brightness": brightness_eq,
         "meanMaxLvls": max_mean_lvls, "meanMinLvls": min_mean_lvls, "autoMinMax": auto_min_max, "source": dev_index}
    )


@app.route('/toggle/sound')
def toggle_sound():
    GPIO.output(SOUND_PIN, GPIO.LOW)
    time.sleep(50 / 1000)
    GPIO.output(SOUND_PIN, GPIO.HIGH)
    return jsonify(sound='toggle')


@app.route('/power/<state>')
def power(state):
    if state == 'on':
        power_on()
    elif state == 'off':
        power_off()
    return jsonify(power="state")


@app.route('/<light_on>')
def light(light_on):
    if light_on == 'dark':
        uniform_color(0, 0, 0)
    elif light_on == 'gradient':
        for i in range(LED_STRIPES_COUNT):
            light_stripe(i)
        show()
    elif light_on == 'color1':
        uniform_color(color1_red, color1_green, color1_blue)
    elif light_on == 'color2':
        uniform_color(color2_red, color2_green, color2_blue)
    return jsonify(state=light_on)


if __name__ == '__main__':
    STRIP.begin()
    update_gradient()

try:
    app.run(debug=False, host='0.0.0.0')

except KeyboardInterrupt:
    uniform_color(0, 0, 0)
    power_off()
    GPIO.cleanup()
