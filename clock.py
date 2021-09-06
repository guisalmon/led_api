import RPi_I2C_driver
from time import sleep
from datetime import datetime


charset = [
    [0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0X00],
    [0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0x1F, 0X1F],
    [0x1F, 0x1F, 0x1F, 0x1F, 0x00, 0x00, 0x00, 0x00],
    [0x00, 0x00, 0x00, 0x00, 0x1F, 0x1F, 0x1F, 0X1F],
    [0x0F, 0x0F, 0x0F, 0x0F, 0x0F, 0x0F, 0x0F, 0x0F],
    [0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E, 0x1E],
    [0x00, 0x00, 0x00, 0x03, 0x03, 0x03, 0x03, 0x03],
    [0x00, 0x00, 0x00, 0x18, 0x18, 0x18, 0x18, 0x18]
]

digitset = [
    [4, 2, 2, 5, 4, 0, 0, 5, 4, 0, 0, 5, 4, 3, 3, 5],
    [0, 0, 5, 0, 0, 0, 5, 0, 0, 0, 5, 0, 0, 0, 5, 0],
    [4, 2, 2, 5, 0, 0, 0, 5, 0, 3, 2, 0, 4, 3, 3, 5],
    [4, 2, 2, 5, 0, 3, 3, 5, 0, 0, 0, 5, 4, 3, 3, 5],
    [4, 0, 0, 5, 4, 3, 3, 5, 0, 0, 0, 5, 0, 0, 0, 5],
    [4, 2, 2, 5, 4, 3, 3, 0, 0, 0, 0, 5, 4, 3, 3, 5],
    [4, 2, 2, 5, 4, 3, 3, 0, 4, 0, 0, 5, 4, 3, 3, 5],
    [4, 2, 2, 5, 0, 0, 0, 5, 0, 0, 0, 5, 0, 0, 0, 5],
    [4, 2, 2, 5, 4, 3, 3, 5, 4, 0, 0, 5, 4, 3, 3, 5],
    [4, 2, 2, 5, 4, 3, 3, 5, 0, 0, 0, 5, 4, 3, 3, 5]
]

digitset_bold = [
    [1, 1, 1, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 1, 1, 1],
    [0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0],
    [1, 1, 1, 1, 3, 3, 1, 1, 1, 1, 2, 2, 1, 1, 1, 1],
    [1, 1, 1, 1, 3, 3, 1, 1, 2, 2, 1, 1, 1, 1, 1, 1],
    [1, 1, 0, 1, 1, 1, 3, 1, 2, 2, 2, 1, 0, 0, 0, 1],
    [1, 1, 1, 1, 1, 1, 3, 3, 2, 2, 1, 1, 1, 1, 1, 1],
    [1, 1, 0, 0, 1, 1, 3, 3, 1, 1, 2, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1],
    [1, 1, 1, 1, 1, 3, 3, 1, 1, 2, 2, 1, 1, 1, 1, 1],
    [1, 1, 1, 1, 1, 3, 1, 1, 2, 2, 1, 1, 0, 0, 1, 1]
]

h = "00"
m = "00"
d = "00"
p = True
month = "00"
y = "0000"

lcd = RPi_I2C_driver.Lcd()
lcd.lcd_clear()
lcd.lcd_load_custom_chars(charset)
backlight = True
lcd.backlight(1)


def position(index):
    pos = 0
    if index == 0:
        pos = 2
    elif index == 1:
        pos = 6
    elif index == 2:
        pos = 12
    elif index == 3:
        pos = 16
    return pos


def write_number(number, index):
    pos = position(index)

    for i in range(16):
        lcd.lcd_display_string_pos(chr(digitset[number][i]), int(i/4) + 1, pos + (i % 4))


def toggle_clock_backlight():
    global backlight
    if backlight:
        backlight = False
    else:
        backlight = True


def get_backlight():
    return backlight

def clock():
    global h
    global m
    global d
    global p
    global month
    global y
    while 1:
        if backlight == 1:
            now = datetime.now()
            ht = now.strftime("%H")
            mt = now.strftime("%M")
            pt = int(now.strftime("%S")) % 2 == 0
            dt = now.strftime("%d")
            month_t = now.strftime("%m")
            yt = now.strftime("%Y")
            if h != ht:
                write_number(int(ht[0]), 0)
                write_number(int(ht[1]), 1)
                h = ht
            if m != mt:
                write_number(int(mt[0]), 2)
                write_number(int(mt[1]), 3)
                m = mt
            if d != dt:
                lcd.lcd_display_string_pos(dt, 1, 0)
                d = dt
            if month != month_t:
                lcd.lcd_display_string_pos(month_t, 2, 0)
                month = month_t
            if y != yt:
                lcd.lcd_display_string_pos(yt[0:2], 3, 0)
                lcd.lcd_display_string_pos(yt[2:4], 4, 0)
                y = yt
            if p != pt:
                if pt:
                    lcd.lcd_display_string_pos(chr(6), 2, 10)
                    lcd.lcd_display_string_pos(chr(7), 2, 11)
                    lcd.lcd_display_string_pos(chr(6), 4, 10)
                    lcd.lcd_display_string_pos(chr(7), 4, 11)
                else:
                    lcd.lcd_display_string_pos(chr(0), 2, 10)
                    lcd.lcd_display_string_pos(chr(0), 2, 11)
                    lcd.lcd_display_string_pos(chr(0), 4, 10)
                    lcd.lcd_display_string_pos(chr(0), 4, 11)
                p = pt
            sleep(0.1)
        else:
            lcd.backlight(0)
