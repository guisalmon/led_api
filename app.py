import math
import threading
import time
import faulthandler
import clock

import RPi.GPIO as GPIO
from gpiozero import Button
import numpy as np
import pyaudio
from flask import Flask, jsonify, request
from rpi_ws281x import *

app = Flask(__name__)

LED_PIN = 12  # GPIO pin connected to the pixels (18 uses PWM!).
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
LED_COUNT = LED_EQ_COUNT + LED_CONTROL_COUNT + LED_LIGHT_COUNT + LED_LIGHT_2_COUNT  # Number of LED pixels.
# Create NeoPixel object with appropriate configuration.
STRIP = Adafruit_NeoPixel(LED_COUNT, LED_PIN, LED_FREQ_HZ, LED_DMA, LED_INVERT, LED_BRIGHTNESS, LED_CHANNEL)

ON = False
STATES = ['dark', 'white', 'gradient', 'equalizer', 'color1', 'color2', 'noise_start', 'noise_end', "waiting", "volume_test"]
state = 'dark'
ambient = False

brightnessEq = 63
color1 = Color(175, 0, 255)
color2 = Color(255, 0, 4)
color1Red = (color1 & (255 << 16)) >> 16
color1Green = (color1 & (255 << 8)) >> 8
color1Blue = color1 & 255
color2Red = (color2 & (255 << 16)) >> 16
color2Green = (color2 & (255 << 8)) >> 8
color2Blue = color2 & 255
incrementRed = (color1Red - color2Red) / LED_STRIPES_LENGTH
incrementGreen = (color1Green - color2Green) / LED_STRIPES_LENGTH
incrementBlue = (color1Blue - color2Blue) / LED_STRIPES_LENGTH
colorGradient = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

POWER_PIN = 16
SOUND_PIN = 20
VOL1_PIN = 5
VOL2_PIN = 6

GPIO.setmode(GPIO.BCM)
GPIO.setup(POWER_PIN, GPIO.OUT)
GPIO.setup(SOUND_PIN, GPIO.OUT)
GPIO.setup(VOL1_PIN, GPIO.IN)
GPIO.setup(VOL2_PIN, GPIO.IN)

# mic sensitivity correction and bit conversion
# mic_sens_dBV = -47.0  # mic sensitivity in dBV + any gain
# mic_sens_dBV = -25.0  # mic sensitivity in dBV + any gain
# mic_sens_dBV = 0  # mic sensitivity in dBV + any gain
mic_sens_dBV = -10  # mic sensitivity in dBV + any gain
mic_sens_corr = np.power(10.0, mic_sens_dBV / 20.0)  # calculate mic sensitivity conversion factor

freqMin = 20
freqMax = 8000
form_1 = pyaudio.paInt16  # 16-bit resolution
chans = 1  # 1 channel
samp_rate = 44100  # 44.1kHz sampling rate
chunk = 512  # 2^12 samples for buffer
dev_index = 1  # device index found by p.get_device_info_by_index(ii)
meansMax = 0.5
meansMin = 0
# meansCorrection = [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]
# meansCorrection = [0.00343, 0.00352, 0.0013, 0.00108, 0.000623, 0.000253, 0.000174, 0.0000929, 0.0000563, 0.0000409,
#                   0.0000347, 0.0000283]
fftCorrection = [0.0] * (int(chunk / 2))
meanMinLvls = [10.0] * LED_STRIPES_COUNT
meanMaxLvls = [-10.0] * LED_STRIPES_COUNT
AUDIO_LVLS_MEM_SIZE = 1024
autoMinMax = True

audioMeanlvls = [[0.0] * LED_STRIPES_COUNT] * AUDIO_LVLS_MEM_SIZE
audioMeanlvlsIndex = 0


class AudioSampler(threading.Thread):
    def __init__(self, sampler):
        threading.Thread.__init__(self)
        self.daemon = True
        self.runnable = sampler

    def run(self):
        self.runnable()


class VolumeTest(threading.Thread):
    def __init__(self, test):
        threading.Thread.__init__(self)
        self.daemon = True
        self.runnable = test

    def run(self):
        self.runnable()


class Clock(threading.Thread):
    def __init__(self, clock):
        threading.Thread.__init__(self)
        self.daemon = True
        self.runnable = clock

    def run(self):
        self.runnable()


def hex_to_rgb(value):
    # print(value)
    value = value.lstrip('#')
    # print(value)
    rgb = list(int(value[i:i + 2], 16) for i in (0, 2, 4))
    # print(rgb[0], " ", rgb[1], " ", rgb[2])
    return rgb


def rgb_to_hex(r, g, b):
    return '#{:02x}{:02x}{:02x}'.format(r, g, b)


def updateColor():
    for i in range(LED_STRIPES_LENGTH):
        # print("index ", i)
        getColorBetweenBounds(i)


def powerOn():
    global ON
    GPIO.output(POWER_PIN, GPIO.LOW)
    time.sleep(50 / 1000)
    setPixelColor(LED_EQ_COUNT, color1, 16)
    STRIP.show()
    ON = True


def powerOff():
    global ON
    setPixelColor(LED_EQ_COUNT, Color(0, 0, 0), 16)
    STRIP.show()
    time.sleep(50 / 1000)
    GPIO.output(POWER_PIN, GPIO.HIGH)
    ON = False


def setPixelColor(index, color, brightnessOverride):
    colorRed = (color & (255 << 16)) >> 16
    colorGreen = (color & (255 << 8)) >> 8
    colorBlue = color & 255
    colorRed = (colorRed / 255) * brightnessOverride
    colorGreen = (colorGreen / 255) * brightnessOverride
    colorBlue = (colorBlue / 255) * brightnessOverride
    color = (int(colorRed) << 16) + (int(colorGreen) << 8) + int(colorBlue)
    # print(index, " : ", colorRed, " ", colorGreen, " ", colorBlue)
    STRIP.setPixelColor(index, color)


def getColorBetweenBounds(colorIndex):
    colorGradient[colorIndex] = (int(color2Red + colorIndex * incrementRed) << 16) + (
                int(color2Green + colorIndex * incrementGreen) << 8) + int(color2Blue + colorIndex * incrementBlue)


def lightStripe(stripeIndex, length=LED_STRIPES_LENGTH):
    if stripeIndex < LED_EQ_COUNT / LED_STRIPES_LENGTH:
        if (stripeIndex % 2) == 0:
            for i in range(1, LED_STRIPES_LENGTH + 1):
                if (i <= length) & (i > 0):
                    setPixelColor(stripeIndex * LED_STRIPES_LENGTH + (i - 1),
                                  colorGradient[i - 1],
                                  (brightnessEq / LED_STRIPES_LENGTH ** 2) *
                                      (LED_STRIPES_LENGTH - (length - i)) * length)

                elif i > length:
                    setPixelColor(stripeIndex * LED_STRIPES_LENGTH + (i - 1), Color(0, 0, 0),
                                  brightnessEq)
        else:
            for i in range(1, LED_STRIPES_LENGTH + 1):
                if (i <= length) & (i > 0):
                    setPixelColor(stripeIndex * LED_STRIPES_LENGTH + 10 - i,
                                  colorGradient[i - 1],
                                  (brightnessEq / LED_STRIPES_LENGTH ** 2) *
                                      (LED_STRIPES_LENGTH - (length - i)) * length)
                elif i > length:
                    setPixelColor(stripeIndex * LED_STRIPES_LENGTH + 10 - i, Color(0, 0, 0),
                                  brightnessEq)


# Define functions which animate LEDs in various ways.
def colorWipe(color):
    for i in range(LED_EQ_COUNT):
        setPixelColor(i, color, brightnessEq)
    STRIP.show()


def noiseAcquisition():
    global fftCorrection
    audio = pyaudio.PyAudio()
    stream = audio.open(format=form_1, rate=samp_rate, channels=chans, input_device_index=dev_index, input=True,
                        frames_per_buffer=chunk)

    fft_avg = np.empty((int(chunk / 2), 0)).tolist()
    fftCorrection = [0] * (int(chunk / 2))

    while state == 'noise_start':
        # record data chunk
        stream.start_stream()
        data = np.fromstring(stream.read(chunk), dtype=np.int16)
        stream.stop_stream()

        # (USB=5V, so 15 bits are used (the 16th for negatives)) and the manufacturer microphone sensitivity corrections
        data = ((data / np.power(2.0, 15)) * 5.25) * mic_sens_corr

        # compute FFT parameters
        fft_data = (np.abs(np.fft.fft(data))[0:int(np.floor(chunk / 2))]) / chunk
        fft_data[1:] = 2 * fft_data[1:]

        for i in range(len(fft_data)):
            fft_avg[i].append(fft_data[i])

    for i in range(len(fft_avg)):
        fftCorrection[i] = np.median(fft_avg[i]) * 2

    stream.close()
    audio.terminate()


def audioSampling():
    faulthandler.enable()
    global meanMinLvls
    global means_buffer_index
    global audioMeanlvlsIndex
    global audioMeanlvls

    audio = pyaudio.PyAudio()
    stream = audio.open(format=form_1, rate=samp_rate, channels=chans, input_device_index=dev_index, input=True,
                        frames_per_buffer=chunk)

    meanMinLvls = [10.0] * LED_STRIPES_COUNT

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
            if (freq > freqMin) & (freq < freqMax):
                log10Array.append(math.log10(freq))
                audioLvlsArray.append(
                    (fft_data[freq_index] - fftCorrection[freq_index]) * 1000)
            freq_index += 1

        freq_increments = (log10Array[len(log10Array) - 1] - log10Array[0]) / 12
        freqs = [[], [], [], [], [], [], [], [], [], [], [], []]
        freq_index = 0
        for freqLog in log10Array:
            column = int((freqLog - log10Array[0]) / freq_increments)
            if column > 11:
                column = 11
            freqs[column].append(audioLvlsArray[freq_index])
            freq_index += 1

        means = [0.0] * LED_STRIPES_COUNT
        meansRange = [0.0] * LED_STRIPES_COUNT
        index = 0

        for lvls in freqs:
            meanLvl = np.mean(lvls)
            means[index] = meanLvl
            if (meanLvl < meanMinLvls[index]) & autoMinMax:
                meanMinLvls[index] = meanLvl
            elif (meanLvl > meanMaxLvls[index]) & autoMinMax:
                meanMaxLvls[index] = meanLvl
            meansRange[index] = meanMaxLvls[index] - meanMinLvls[index]
            lvl = int((means[index] - meanMinLvls[index]) / (meansRange[index] / (LED_STRIPES_LENGTH + 1)))
            if lvl < 0:
                lvl = 0
            elif lvl > LED_STRIPES_LENGTH:
                lvl = LED_STRIPES_LENGTH
            lightStripe(index, lvl)
            index += 1

        if audioMeanlvlsIndex == AUDIO_LVLS_MEM_SIZE:
            audioMeanlvlsIndex = 0
        audioMeanlvls[audioMeanlvlsIndex] = means
        audioMeanlvlsIndex += 1

        STRIP.show()
        # print("stop")

    # f = open('MinMax_{}'.format(datetime.now().strftime("%d-%m-%Y_%H:%M:%S")), "a")
    # for i in range(LED_STRIPES_COUNT):
    #    f.write('{index} - min: {min} - max: {max}'.format(index=i, min=meanMinLvls[i], max=meanMaxLvls[i]))
    # f.close()
    stream.close()
    audio.terminate()


def jsonConfig():
    return jsonify(
        {"freqMin": freqMin, "freqMax": freqMax, "meansMax": meansMax, "meansMin": meansMin,
         "fftCorrection": fftCorrection, "color1": rgb_to_hex(color1Red, color1Green, color1Blue),
         "color2": rgb_to_hex(color2Red, color2Green, color2Blue), "brightness": brightnessEq,
         "meanMaxLvls": meanMaxLvls, "meanMinLvls": meanMinLvls, "autoMinMax": autoMinMax, "source": dev_index,
         "on": ON, "ambient": ambient, "state": state, "clock_backlight": clock.backlight}
    )


@app.route('/eq/on')
def eqOn():
    powerOn()
    time.sleep(1)
    light("equalizer")
    time.sleep(1)
    return jsonConfig()


@app.route('/eq/off')
def eqOff():
    light("dark")
    time.sleep(1)
    powerOff()
    time.sleep(1)
    return jsonConfig()


@app.route('/ambient/on')
def ambientOn():
    global ambient
    for i in range(LED_EQ_COUNT + 3, LED_COUNT):
        STRIP.setPixelColor(i, Color(255, 255, 255))
    STRIP.show()
    ambient = True
    return jsonConfig()


@app.route('/ambient/off')
def ambientOff():
    global ambient
    for i in range(LED_EQ_COUNT + 3, LED_COUNT):
        STRIP.setPixelColor(i, Color(0, 0, 0))
    STRIP.show()
    ambient = False
    return jsonConfig()


@app.route('/source/toggle')
def toggleSource():
    global dev_index
    global state
    prevState = state
    state = "wait"
    if dev_index == 0:
        dev_index = 1
    elif dev_index == 1:
        dev_index = 0
    light(prevState)
    return jsonConfig()


@app.route('/sensibility/+')
def increaseSensibility():
    global meanMaxLvls
    for i in range(len(meanMaxLvls)):
        meanMaxLvls[i] = meanMaxLvls[i] / 2
    return jsonConfig()


@app.route('/sensibility/reset')
def resetSensibility():
    global meanMaxLvls
    meanMaxLvls = [-10.0] * LED_STRIPES_COUNT
    return jsonConfig()


@app.route('/config', methods=['GET'])
def config():
    return jsonConfig()


@app.route('/levels/toggle')
def toggleAutoMinMax():
    global autoMinMax
    autoMinMax = not autoMinMax
    return jsonConfig()


@app.route('/config', methods=['POST'])
def updateConfig():
    global freqMin
    global freqMax
    global meansMax
    global meansMin
    global fftCorrection
    global brightnessEq

    newConfig = request.get_json()

    freqMin = newConfig.get("freqMin")
    freqMax = newConfig.get("freqMax")
    meansMax = newConfig.get("meansMax")
    meansMin = newConfig.get("meansMin")
    fftCorrection = newConfig.get("fftCorrection")
    brightnessEq = newConfig.get("brightness")
    updateColor1(newConfig.get("color1"))
    updateColor2(newConfig.get("color2"))

    return jsonConfig()


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
    prevState = state
    state = "waiting"
    rgb1 = hex_to_rgb(color)
    color1Red = rgb1[0]
    color1Green = rgb1[1]
    color1Blue = rgb1[2]
    color1 = Color(color1Red, color1Green, color1Blue)
    incrementRed = (color1Red - color2Red) / LED_STRIPES_LENGTH
    incrementGreen = (color1Green - color2Green) / LED_STRIPES_LENGTH
    incrementBlue = (color1Blue - color2Blue) / LED_STRIPES_LENGTH
    updateColor()
    light(prevState)
    return jsonConfig()


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
    prevState = state
    state = "waiting"
    rgb2 = hex_to_rgb(color)
    color2Red = rgb2[0]
    color2Green = rgb2[1]
    color2Blue = rgb2[2]
    color2 = Color(color2Red, color2Green, color2Blue)
    incrementRed = (color1Red - color2Red) / LED_STRIPES_LENGTH
    incrementGreen = (color1Green - color2Green) / LED_STRIPES_LENGTH
    incrementBlue = (color1Blue - color2Blue) / LED_STRIPES_LENGTH
    updateColor()
    light(prevState)
    return jsonConfig()


@app.route('/brightness/<increment>')
def brightness(increment):
    global brightnessEq
    prevState = state
    light("waiting")
    if increment == '+':
        brightnessEq = brightnessEq + 10
        if brightnessEq > 255:
            brightnessEq = 255
    elif increment == '-':
        brightnessEq = brightnessEq - 10
        if brightnessEq < 0:
            brightnessEq = 0
    else:
        brightnessEq = int(increment)
    light(prevState)
    return jsonConfig()


@app.route('/levels/stripes')
def levels():
    return jsonify(memSize=AUDIO_LVLS_MEM_SIZE, audioLvls=audioMeanlvls)


@app.route('/power/<stateReq>')
def power(stateReq):
    if stateReq == 'on':
        powerOn()
    elif stateReq == 'off':
        powerOff()
    return jsonConfig()


@app.route('/clock/backlight')
def toggle_clock_backlight():
    clock.toggle_clock_backlight()
    return jsonConfig()


def volume_test():
    while state == "volume_test":
        if GPIO.input(VOL1_PIN) == 0:
            print("vol 1")
        if GPIO.input(VOL2_PIN) == 0:
            print("vol 2")
        time.sleep(5)


@app.route('/<lightOn>')
def light(lightOn):
    global state

    if (lightOn in STATES) & (lightOn != state):
        state = lightOn
        if lightOn == 'dark':
            colorWipe(Color(0, 0, 0))

        elif lightOn == 'white':
            colorWipe(Color(255, 255, 255))

        elif lightOn == 'gradient':
            for i in range(LED_STRIPES_COUNT):
                lightStripe(i)
            STRIP.show()

        elif lightOn == 'equalizer':
            samplerThread = AudioSampler(audioSampling)
            samplerThread.start()

        elif lightOn == 'volume_test':
            volumeTest = VolumeTest(volume_test)
            volumeTest.start()

        elif lightOn == 'color1':
            for i in range(LED_EQ_COUNT):
                setPixelColor(i, color1, brightnessEq)
            STRIP.show()

        elif lightOn == 'color2':
            for i in range(LED_EQ_COUNT):
                setPixelColor(i, color2, brightnessEq)
            STRIP.show()

        elif lightOn == 'noise_start':
            samplerThread = AudioSampler(noiseAcquisition)
            samplerThread.start()

    return jsonify(state=state)


def printVol(index):
    print("Vol "+index)


if __name__ == '__main__':
    # Intialize the library (must be called once before other functions).
    STRIP.begin()
    updateColor()
    p = pyaudio.PyAudio()
    for i in range(p.get_device_count()):
        print(p.get_device_info_by_index(i))
    setPixelColor(LED_EQ_COUNT + 1, color2, 16)
    STRIP.show()
    clock_thread = Clock(clock.clock)
    clock_thread.start()

    vol1 = Button(VOL1_PIN)
    vol2 = Button(VOL2_PIN)
    vol1.when_pressed = printVol("1")
    vol2.when_pressed = printVol("2")

try:
    app.run(debug=False, host='0.0.0.0')

except KeyboardInterrupt:
    colorWipe(Color(0, 0, 0))
    powerOff()
    GPIO.cleanup()
