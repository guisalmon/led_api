from flask import Flask, render_template, jsonify
import time
import RPi.GPIO as GPIO
from rpi_ws281x import *
import pyaudio
import numpy as np
import math
import threading

app = Flask(__name__)

LED_PIN = 18  # GPIO pin connected to the pixels (18 uses PWM!).
LED_FREQ_HZ = 800000  # LED signal frequency in hertz (usually 800khz)
LED_DMA = 10  # DMA channel to use for generating signal (try 10)
LED_BRIGHTNESS = 127  # Set to 0 for darkest and 255 for brightest
LED_INVERT = False  # True to invert the signal (when using NPN transistor
LED_CHANNEL = 0  # set to '1' for GPIOs 13, 19, 41, 45 or 53
LED_STRIPES_LENGTH = 10
LED_STRIPES_COUNT = 12
LED_COUNT = LED_STRIPES_LENGTH * LED_STRIPES_COUNT  # Number of LED pixels.
# Create NeoPixel object with appropriate configuration.
STRIP = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)

STATES = ['dark', 'white', 'gradient', 'equalizer', 'color1', 'color2']
state = 'dark'

color1 = Color(244, 0, 121)
color2 = Color(86, 137, 231)
color1Red = (color1 & (255 << 16)) >> 16
color1Green = (color1 & (255 << 8)) >> 8
color1Blue = color1 & 255
color2Red = (color2 & (255 << 16)) >> 16
color2Green = (color2 & (255 << 8)) >> 8
color2Blue = color2 & 255
incrementRed = (color1Red - color2Red) / LED_STRIPES_LENGTH
incrementGreen = (color1Green - color2Green) / LED_STRIPES_LENGTH
incrementBlue = (color1Blue - color2Blue) / LED_STRIPES_LENGTH

POWER_PIN = 4
SOUND_PIN = 17

GPIO.setmode(GPIO.BCM)
GPIO.setup(POWER_PIN, GPIO.OUT)
GPIO.setup(SOUND_PIN, GPIO.OUT)

form_1 = pyaudio.paInt16  # 16-bit resolution
chans = 1  # 1 channel
samp_rate = 44100  # 44.1kHz sampling rate
chunk = 8192  # 2^12 samples for buffer
dev_index = 0  # device index found by p.get_device_info_by_index(ii)


class AudioSampler(threading.Thread):
    def __init__(self, sampler):
        threading.Thread.__init__(self)
        self.daemon = True
        self.runnable = sampler

    def run(self):
        self.runnable()


def hex_to_rgb(value):
    value = value.lstrip('#')
    return list(int(value[i:i + 2], 16) for i in (0, 2, 4))


def powerOn():
    GPIO.output(POWER_PIN, GPIO.LOW)


def powerOff():
    GPIO.output(POWER_PIN, GPIO.HIGH)


def getColorBetweenBounds(colorIndex):
    return Color(int(color2Red + colorIndex * incrementRed), int(color2Green + colorIndex * incrementGreen),
                 int(color1Blue + colorIndex * incrementBlue))


def lightStripe(strip, stripeIndex, length=LED_STRIPES_LENGTH):
    if stripeIndex < LED_COUNT / LED_STRIPES_LENGTH:
        if (stripeIndex % 2) == 0:
            for i in range(LED_STRIPES_LENGTH):
                if i <= length:
                    strip.setPixelColor(stripeIndex * LED_STRIPES_LENGTH + i, getColorBetweenBounds(i))
                else:
                    strip.setPixelColor(stripeIndex * LED_STRIPES_LENGTH + i, Color(0, 0, 0))
        else:
            for i in range(LED_STRIPES_LENGTH):
                if i <= length:
                    strip.setPixelColor(stripeIndex * LED_STRIPES_LENGTH + 9 - i, getColorBetweenBounds(i))
                else:
                    strip.setPixelColor(stripeIndex * LED_STRIPES_LENGTH + 9 - i, Color(0, 0, 0))


# Define functions which animate LEDs in various ways.
def colorWipe(strip, color, wait_ms=50):
    """Wipe color across display a pixel at a time."""
    for i in range(strip.numPixels()):
        strip.setPixelColor(i, color)
        strip.show()
        time.sleep(wait_ms / 1000.0)


def audioSampling():
    audio = pyaudio.PyAudio()
    stream = audio.open(format=form_1, rate=samp_rate, channels=chans, input_device_index=dev_index, input=True,
                        frames_per_buffer=chunk)

    # mic sensitivity correction and bit conversion
    mic_sens_dBV = -47.0  # mic sensitivity in dBV + any gain
    mic_sens_corr = np.power(10.0, mic_sens_dBV / 20.0)  # calculate mic sensitivity conversion factor

    meansMax = 0.007

    while state == 'equalizer':
        # record data chunk
        stream.start_stream()
        data = np.fromstring(stream.read(chunk), dtype=np.int16)
        stream.stop_stream()

        # (USB=5V, so 15 bits are used (the 16th for negatives)) and the manufacturer microphone sensitivity corrections
        data = ((data / np.power(2.0, 15)) * 5.25) * mic_sens_corr

        # compute FFT parameters
        f_vec = samp_rate * np.arange(chunk / 2) / chunk  # frequency vector based on window size and sample rate
        fft_data = (np.abs(np.fft.fft(data))[0:int(np.floor(chunk / 2))]) / chunk
        fft_data[1:] = 2 * fft_data[1:]

        log10Array = []
        audioLvlsArray = []
        freq_index = 0
        for freq in f_vec:
            if (freq > 20) & (freq < 20000):
                log10Array.append(math.log10(freq))
                audioLvlsArray.append(fft_data[freq_index] * 1000)
            freq_index += 1

        freq_increments = (log10Array[len(log10Array) - 1] - log10Array[0]) / 12
        freq1 = []
        freq2 = []
        freq3 = []
        freq4 = []
        freq5 = []
        freq6 = []
        freq7 = []
        freq8 = []
        freq9 = []
        freq10 = []
        freq11 = []
        freq12 = []
        freq_index = 0
        # print("start")
        for freqLog in log10Array:
            v = (freqLog - log10Array[0]) / freq_increments
            # print(audioLvlsArray[freq_index])
            if v <= 1:
                freq1.append(audioLvlsArray[freq_index])
            elif v <= 2:
                freq2.append(audioLvlsArray[freq_index])
            elif v <= 3:
                freq3.append(audioLvlsArray[freq_index])
            elif v <= 4:
                freq4.append(audioLvlsArray[freq_index])
            elif v <= 5:
                freq5.append(audioLvlsArray[freq_index])
            elif v <= 6:
                freq6.append(audioLvlsArray[freq_index])
            elif v <= 7:
                freq7.append(audioLvlsArray[freq_index])
            elif v <= 8:
                freq8.append(audioLvlsArray[freq_index])
            elif v <= 9:
                freq9.append(audioLvlsArray[freq_index])
            elif v <= 10:
                freq10.append(audioLvlsArray[freq_index])
            elif v <= 11:
                freq11.append(audioLvlsArray[freq_index])
            elif v <= 12:
                freq12.append(audioLvlsArray[freq_index])

            freq_index += 1
        # print("stop")

        means = [np.mean(freq1) - 0.00343, np.mean(freq2) - 0.00352, np.mean(freq3) - 0.0013,
                 np.mean(freq4) - 0.00108, np.mean(freq5) - 0.000623, np.mean(freq6) - 0.000253,
                 np.mean(freq7) - 0.000174, np.mean(freq8) - 0.0000929, np.mean(freq9) - 0.0000563,
                 np.mean(freq10) - 0.0000409, np.mean(freq11) - 0.0000347, np.mean(freq12) - 0.0000283]
        # meansMin = np.min(means)
        meansMin = 0
        meansRange = meansMax - meansMin
        meansRangeInc = meansRange / LED_STRIPES_LENGTH

        # print("start")
        for i in range(LED_STRIPES_COUNT):
            lvl = int((means[i] - meansMin) / meansRangeInc)
            if lvl < 0:
                lvl = 0
            elif lvl > 9:
                lvl = 9
            lightStripe(STRIP, i, lvl)
        STRIP.show()
        # print("stop")

    stream.close()
    audio.terminate()


@app.route('/toggle/sound')
def toggleSound():
    GPIO.output(SOUND_PIN, GPIO.LOW)
    time.sleep(50 / 1000)
    GPIO.output(SOUND_PIN, GPIO.HIGH)
    return jsonify(sound='toggle')


@app.route('/color1/<color>')
def updateColor1(color):
    global color1
    global color1Red
    global color1Green
    global color1Blue
    global state
    global incrementRed
    global incrementGreen
    global incrementBlue
    rgb1 = hex_to_rgb(color)
    color1Red = rgb1[0]
    color1Green = rgb1[1]
    color1Blue = rgb1[2]
    color1 = Color(color1Red, color1Green, color1Blue)
    incrementRed = (color1Red - color2Red) / LED_STRIPES_LENGTH
    incrementGreen = (color1Green - color2Green) / LED_STRIPES_LENGTH
    incrementBlue = (color1Blue - color2Blue) / LED_STRIPES_LENGTH
    prevState = state
    state = "waiting"
    light(prevState)
    return color


@app.route('/color2/<color>')
def updateColor2(color):
    global color2
    global color2Red
    global color2Green
    global color2Blue
    global state
    global incrementRed
    global incrementGreen
    global incrementBlue
    rgb2 = hex_to_rgb(color)
    color2Red = rgb2[0]
    color2Green = rgb2[1]
    color2Blue = rgb2[2]
    color2 = Color(color2Red, color2Green, color2Blue)
    incrementRed = (color1Red - color2Red) / LED_STRIPES_LENGTH
    incrementGreen = (color1Green - color2Green) / LED_STRIPES_LENGTH
    incrementBlue = (color1Blue - color2Blue) / LED_STRIPES_LENGTH
    prevState = state
    state = "waiting"
    light(prevState)
    return color


@app.route('/brightness/<increment>')
def brightness(increment):
    global LED_BRIGHTNESS
    if increment == '+':
        LED_BRIGHTNESS = LED_BRIGHTNESS + 10
        if LED_BRIGHTNESS > 255:
            LED_BRIGHTNESS = 255
    elif increment == '-':
        LED_BRIGHTNESS = LED_BRIGHTNESS - 10
        if LED_BRIGHTNESS < 0:
            LED_BRIGHTNESS = 0
    STRIP.setBrightness(LED_BRIGHTNESS)
    STRIP.show()
    return jsonify(brightness=LED_BRIGHTNESS)


@app.route('/power/<state>')
def power(state):
    if state == 'on':
        powerOn()
    elif state == 'off':
        powerOff()
    return jsonify(power="state")


@app.route('/<lightOn>')
def light(lightOn):
    global state

    if (lightOn in STATES) & (lightOn != state):
        state = lightOn
        if lightOn == 'dark':
            colorWipe(STRIP, Color(0, 0, 0))

        elif lightOn == 'white':
            colorWipe(STRIP, Color(255, 255, 255))

        elif lightOn == 'gradient':
            for i in range(LED_STRIPES_COUNT):
                lightStripe(STRIP, i)

        elif lightOn == 'equalizer':
            samplerThread = AudioSampler(audioSampling)
            samplerThread.start()

        elif lightOn == 'color1':
            for i in range(LED_COUNT):
                STRIP.setPixelColor(i, color1)
            STRIP.show()

        elif lightOn == 'color2':
            for i in range(LED_COUNT):
                STRIP.setPixelColor(i, color2)
            STRIP.show()
    return jsonify(state=state)


if __name__ == '__main__':
    # Intialize the library (must be called once before other functions).
    STRIP.begin()

try:
    app.run(debug=False, host='0.0.0.0')

except KeyboardInterrupt:
    colorWipe(STRIP, Color(0, 0, 0), 10)
    powerOff()
    GPIO.cleanup()
