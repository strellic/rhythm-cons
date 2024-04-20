import analogio
import rotaryio
import asyncio
import keypad
import board
import time

from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
import usb_hid
keyboard = Keyboard(usb_hid.devices)

import screen
import config

he_pins = [analogio.AnalogIn(p) for p in [board.GP26, board.GP27, board.GP28, board.GP29]]
keys = keypad.Keys([board.GP15, board.GP2, board.GP3, board.GP4, board.GP5], value_when_pressed=False, pull=True) 
enc = rotaryio.IncrementalEncoder(board.GP13, board.GP12)

def keyboard_press(keys):
    for k in keys:
        keycode = getattr(Keycode, k)
        keyboard.press(keycode)
def keyboard_send(keys):
    for k in keys:
        keycode = getattr(Keycode, k)
        keyboard.send(keycode)
def keyboard_release(keys):
    for k in keys:
        keycode = getattr(Keycode, k)
        keyboard.release(keycode)
async def keyboard_hold(keys):
    keys = keys[:]
    keys = sorted(keys, key=lambda k: k[1])
    running_total = 0
    for k in keys:
        if k[1] == 0:
            keyboard.send(getattr(Keycode, k[0]))
        else:
            keyboard.press(getattr(Keycode, k[0]))
    for k in [k for k in keys if k[1] != 0]:
        delay = k[1] - running_total
        await asyncio.sleep(delay)
        keyboard.release(getattr(Keycode, k[0])) 
        running_total += k[1]

key_state = [False for _ in he_pins]
he_state = [False for _ in he_pins]
up_peaks = [0 for _ in he_pins]
down_peaks = [float('inf') for _ in he_pins]
last_reactive_trigger = 0
async def read_he():
    global prev_vals
    global last_reactive_trigger
    while True:
        values = [p.value for p in he_pins]
        if screen.display.screen.name != "play":
            screen.on_analog(values)
            await asyncio.sleep(0.05)
            continue
        for i, v in enumerate(values):
            base, pressed = config.data.calibration[i]
            if base == 0 or pressed == 0:
                continue
            change = (v - pressed) / (base - pressed)
            if config.data.rapid_trigger:
                if not he_state[i]:
                    if change < 1 - config.data.actuation:
                        he_state[i] = True
                        key_state[i] = True
                        config.key_pixels[i] = config.data.color[i]
                        keyboard_press(config.data.keys[i])
                    continue
                
                if (config.data.continuous_rapid_trigger and change > 0.97) or (not config.data.continuous_rapid_trigger and change > 1 - config.data.actuation):
                    he_state[i] = False
                    key_state[i] = False
                    up_peaks[i] = 0
                    down_peaks[i] = float('inf')
                    config.key_pixels[i] = [0, 0, 0]
                    keyboard_release(config.data.keys[i])
                    continue
                
                up_peaks[i] = max(up_peaks[i], v)
                down_peaks[i] = min(down_peaks[i], v)
                
                up_peak_change = (up_peaks[i] * (1 - config.data.rt_area) - pressed) / (base - pressed)
                down_peak_change = (down_peaks[i] * (1 + config.data.rt_area) - pressed) / (base - pressed)
                
                if key_state[i] and change > down_peak_change:
                    key_state[i] = False
                    keyboard_release(config.data.keys[i])
                    config.key_pixels[i] = [0, 0, 0]
                    up_peaks[i] = v
                elif not key_state[i] and change < up_peak_change:
                    key_state[i] = True
                    keyboard_press(config.data.keys[i])
                    config.key_pixels[i] = config.data.color[i]
                    down_peaks[i] = v
            else:
                if not key_state[i]:
                    if change < 1 - config.data.actuation:
                        key_state[i] = True
                        keyboard_press(config.data.keys[i])
                        config.key_pixels[i] = config.data.color[i]
                else:
                    if change > 1 - config.data.actuation:
                        key_state[i] = False
                        keyboard_release(config.data.keys[i])
                        config.key_pixels[i] = [0,0,0]
            if key_state[i]:
                last_reactive_trigger = time.monotonic()
        await asyncio.sleep(0)

last_enc_press = 0
is_holding = False
async def read_sw():
    global last_enc_press
    global is_holding
    global last_reactive_trigger
    while True:
        if screen.display.screen.name == "play" and time.monotonic() - last_enc_press > config.data.enc_hold_time and is_holding:
            is_holding = False
            await keyboard_hold(config.data.enc_keys[1])
        if event := keys.events.get():
            if event.pressed:
                initial_screen = screen.display.screen.name
                screen.on_press(event.key_number)
                if event.key_number == 0 and screen.display.screen.name == "play":
                    last_enc_press = time.monotonic()
                    is_holding = True
                if initial_screen == "play" and screen.display.screen.name != "play":
                    # we switched from play screen, reset all lights
                    for i in range(11):
                        config.pixels[i] = [0,0,0]
                    config.pixels.show()
            else:
                if screen.display.screen.name == "play" and event.key_number == 0:
                    is_holding = False
                    if time.monotonic() - last_enc_press < config.data.enc_hold_time:
                        await keyboard_hold(config.data.enc_keys[0])
        await asyncio.sleep(0)

last_position = None
async def read_enc():
    global last_position
    global last_reactive_trigger
    while True:
        position = enc.position
        if last_position != None and position != last_position:
            screen.on_rotate(position > last_position)
            last_reactive_trigger = time.monotonic()
            if screen.display.screen.name == "play":
                keyboard_send(config.data.keys[5] if position > last_position else config.data.keys[4])
        last_position = position
        await asyncio.sleep(0.1)

async def edge_leds():
    while True:
        if screen.display.screen.name == "edge_lights_configure":
            screen.display.screen.update_anim()
            for i in range(len(config.edge_pixels)):
                config.edge_pixels[i] = [int(v * config.data.edge_brightness) for v in config.edge_pixels[i]]
            config.edge_pixels.show()
        elif screen.display.screen.name == "play":
            if not config.data.reactive_edge or time.monotonic() - max(last_enc_press, last_reactive_trigger) <= config.data.reactive_time:
                config.edge_anim.animate(False)
                for i in range(len(config.edge_pixels)):
                    config.edge_pixels[i] = [int(v * config.data.edge_brightness) for v in config.edge_pixels[i]]
            else:
                for i in range(len(config.edge_pixels)):
                    config.edge_pixels[i] = (0, 0, 0)
                config.edge_pixels.show()
        await asyncio.sleep(0.1)

async def key_leds():
    while True:
        if screen.display.screen.name == "play":
            prev_colors = config.key_pixels[:]
            for i in range(len(config.key_pixels)):
                config.key_pixels[i] = [int(v * config.data.key_brightness) for v in config.key_pixels[i]]
            config.key_pixels.show()
            for i in range(len(config.key_pixels)):
                config.key_pixels[i] = prev_colors[i]
        await asyncio.sleep(0.01)

async def main():
    await asyncio.gather(
        asyncio.create_task(read_he()),
        asyncio.create_task(read_sw()),
        asyncio.create_task(read_enc()),
        asyncio.create_task(screen.run()),
        asyncio.create_task(edge_leds()),
        asyncio.create_task(key_leds())
    )

asyncio.run(main())

