import analogio
import rotaryio
import asyncio
import keypad
import board
import time
import json

from hid_gamepad import Gamepad
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keycode import Keycode
from adafruit_hid.consumer_control import ConsumerControl
from adafruit_hid.consumer_control_code import ConsumerControlCode
import usb_hid
import usb_cdc

keyboard = Keyboard(usb_hid.devices)
consumer_control = ConsumerControl(usb_hid.devices)
gp = Gamepad(usb_hid.devices)

import screen
import config

he_pins = [analogio.AnalogIn(p) for p in [board.GP26, board.GP27, board.GP28, board.GP29]]
keys = keypad.Keys([board.GP15, board.GP2, board.GP3, board.GP4, board.GP5], value_when_pressed=False, pull=True) 
enc = rotaryio.IncrementalEncoder(board.GP13, board.GP12)

def key_press(i):
    if i < 4:
        config.key_pixels[i] = config.data.color[i]
    if config.data.mode == "keypad":
        for k in config.data.keys[i]:
            if hasattr(Keycode, k):
                keycode = getattr(Keycode, k)
                keyboard.press(keycode)
            else:
                cccode = getattr(ConsumerControlCode, k)
                consumer_control.press(cccode)
    elif config.data.mode == "gamepad":
        gp.press_buttons(i)
def key_release(i):
    if i < 4:
        config.key_pixels[i] = (0, 0, 0)
    if config.data.mode == "keypad":
        for k in config.data.keys[i]:
            if hasattr(Keycode, k):
                keycode = getattr(Keycode, k)
                keyboard.release(keycode)
            else:
                # there can be only one active consumer control key at a time
                consumer_control.release()
    elif config.data.mode == "gamepad":
        gp.release_buttons(i)
def key_send(i):
    if config.data.mode == "keypad":
        for k in config.data.keys[i]:
            if hasattr(Keycode, k):
                keycode = getattr(Keycode, k)
                keyboard.send(keycode)
            else:
                cccode = getattr(ConsumerControlCode, k)
                consumer_control.send(cccode)
    elif config.data.mode == "gamepad":
        gp.click_buttons(i)
async def key_enc_hold(i):
    keys = config.data.enc_keys[i][:]
    keys = sorted(keys, key=lambda k: k[1])
    running_total = 0
    for k in keys:
        if hasattr(Keycode, k[0]):
            if k[1] == 0:
                keyboard.send(getattr(Keycode, k[0]))
            else:
                keyboard.press(getattr(Keycode, k[0]))
        else:
            if k[1] == 0:
                consumer_control.send(getattr(ConsumerControlCode, k[0]))
            else:
                consumer_control.press(getattr(ConsumerControlCode, k[0]))
    for k in [k for k in keys if k[1] != 0]:
        delay = k[1] - running_total
        await asyncio.sleep(delay)
        if hasattr(Keycode, k[0]):
            keyboard.release(getattr(Keycode, k[0])) 
        else:
            consumer_control.release()
        running_total += k[1]

key_state = [False for _ in he_pins]
he_state = [False for _ in he_pins]
up_peaks = [0 for _ in he_pins]
down_peaks = [float('inf') for _ in he_pins]
he_values = [0 for _ in he_pins]
last_reactive_trigger = 0
async def read_he():
    global prev_vals
    global last_reactive_trigger
    global he_values
    while True:
        he_values = [p.value for p in he_pins]
        if screen.display.screen.name != "play":
            screen.on_analog(he_values)
            await asyncio.sleep(0.05)
            continue
        for i, v in enumerate(he_values):
            base, pressed = config.data.calibration[i]
            if base == 0 or pressed == 0:
                continue
            change = (v - pressed) / (base - pressed)
            if config.data.rapid_trigger:
                if not he_state[i]:
                    if change < 1 - config.data.actuation:
                        he_state[i] = True
                        key_state[i] = True
                        key_press(i)
                    continue
                
                if (config.data.continuous_rapid_trigger and change > 0.97) or (not config.data.continuous_rapid_trigger and change > 1 - config.data.actuation):
                    he_state[i] = False
                    key_state[i] = False
                    up_peaks[i] = 0
                    down_peaks[i] = float('inf')
                    key_release(i)
                    continue
                
                up_peaks[i] = max(up_peaks[i], v)
                down_peaks[i] = min(down_peaks[i], v)
                
                up_peak_change = (up_peaks[i] * (1 - config.data.rt_area) - pressed) / (base - pressed)
                down_peak_change = (down_peaks[i] * (1 + config.data.rt_area) - pressed) / (base - pressed)
                
                if key_state[i] and change > down_peak_change:
                    key_state[i] = False
                    key_release(i)
                    up_peaks[i] = v
                elif not key_state[i] and change < up_peak_change:
                    key_state[i] = True
                    key_press(i)
                    down_peaks[i] = v
            else:
                if not key_state[i]:
                    if change < 1 - config.data.actuation:
                        key_state[i] = True
                        key_press(i)
                else:
                    if change > 1 - config.data.actuation:
                        key_state[i] = False
                        key_release(i)
            if key_state[i]:
                last_reactive_trigger = time.monotonic()
        await asyncio.sleep(0)

last_enc_press = 0
is_holding = False
dpad_deadtime = 0.25
last_dpad_press = 0
async def read_sw():
    global last_enc_press
    global is_holding
    global last_reactive_trigger
    global last_dpad_press
    while True:
        if screen.display.screen.name == "play" and config.data.mode == "keypad" and time.monotonic() - last_enc_press > config.data.enc_hold_time and is_holding:
            is_holding = False
            await key_enc_hold(1)
        if event := keys.events.get():
            if event.pressed:
                if event.key_number != 0 and time.monotonic() - last_dpad_press < dpad_deadtime:
                    continue
                last_dpad_press = time.monotonic()
                initial_screen = screen.display.screen.name
                screen.on_press(event.key_number)
                if event.key_number == 0 and screen.display.screen.name == "play":
                    is_holding = True
                    if config.data.mode == "keypad":
                        last_enc_press = time.monotonic()
                    elif config.data.mode == "gamepad":
                        key_press(4)
                if initial_screen == "play" and screen.display.screen.name != "play":
                    # we switched from play screen, reset all lights
                    for i in range(len(config.key_pixels)):
                        config.key_pixels[i] = [0,0,0]
                    config.key_pixels.show()
                    for i in range(len(config.edge_pixels)):
                        config.edge_pixels[i] = [0,0,0]
                    config.edge_pixels.show()
            else:
                if screen.display.screen.name == "play" and event.key_number == 0:
                    is_holding = False
                    if config.data.mode == "keypad":
                        if time.monotonic() - last_enc_press < config.data.enc_hold_time:
                            await key_enc_hold(0)
                    elif config.data.mode == "gamepad":
                        key_release(4)
        await asyncio.sleep(0)

last_position = None
ENCODER_PULSE = 96 * 2
curr_encoder_value = 0
curr_gp_value = 0
async def read_enc():
    global last_position
    global last_reactive_trigger
    global curr_encoder_value
    global curr_gp_value
    while True:
        position = enc.position
        if last_position != None and position != last_position:
            screen.on_rotate(
                position < last_position,
                abs(position - last_position)
            )
            last_reactive_trigger = time.monotonic()

            delta = (position - last_position)
            curr_encoder_value += delta
            while curr_encoder_value < 0:
                curr_encoder_value = ENCODER_PULSE + curr_encoder_value
            curr_encoder_value %= ENCODER_PULSE
            curr_gp_value = 255 - int((curr_encoder_value / ENCODER_PULSE) * 255)

            if screen.display.screen.name == "play":
                if config.data.mode == "keypad":
                    key_send(5 if position < last_position else 4)
                elif config.data.mode == "gamepad":
                    gp.move_encoder(curr_gp_value)
        last_position = position
        await asyncio.sleep(0.1)

async def edge_leds():
    while True:
        config.edge_pixels.brightness = config.data.edge_brightness
        if screen.display.screen.name == "edge_lights_configure":
            screen.display.screen.update_anim()
        elif screen.display.screen.name == "play":
            if not config.data.reactive_edge or time.monotonic() - max(last_enc_press, last_reactive_trigger) <= config.data.reactive_time:
                config.edge_anim.animate()
            else:
                for i in range(len(config.edge_pixels)):
                    config.edge_pixels[i] = (0, 0, 0)
                config.edge_pixels.show()
        await asyncio.sleep(0.01)

async def key_leds():
    while True:
        if screen.display.screen.name == "play":
            prev_colors = config.key_pixels[:]
            config.key_pixels.brightness = config.data.key_brightness
            config.key_pixels.show()
            for i in range(len(config.key_pixels)):
                config.key_pixels[i] = prev_colors[i]
        await asyncio.sleep(0.01)

async def handle_serial():
    global curr_gp_value
    while True:
        try:
            if usb_cdc.console.in_waiting > 0:
                data = usb_cdc.console.readline().decode()
                if not data:
                    continue
                data = json.loads(data)

                try:
                    id = data["id"]
                except:
                    usb_cdc.console.reset_input_buffer()
                    continue

                def write(data):
                    payload = (id + json.dumps(data) + id).encode()
                    usb_cdc.console.write(payload)
                    usb_cdc.console.flush()
                    usb_cdc.console.reset_input_buffer()

                try:
                    method = data["method"]
                except:
                    write({"error": "missing method"})
                    continue
            
                if method == "PING":
                    write({"data": "PONG"})
                elif method == "EXEC":
                    write({"data": exec(data["code"])})
                elif method == "GET_CONFIG":
                    write({"data": config.config_data})
                elif method == "SET_CONFIG":
                    with open("config.json", "w") as f:
                        f.write(json.dumps(data["config"]))
                    config.load()
                    write({"data": "LOADED"})
                elif method == "READ":
                    write({
                        "data": {
                            "keys": key_state + [is_holding],
                            "encoder": curr_gp_value,
                            "he": he_values
                        }
                    })
        except:
            pass
        await asyncio.sleep(0.1)

async def main():
    await asyncio.gather(
        asyncio.create_task(read_he()),
        asyncio.create_task(read_sw()),
        asyncio.create_task(read_enc()),
        asyncio.create_task(screen.run()),
        asyncio.create_task(edge_leds()),
        asyncio.create_task(key_leds()),
        asyncio.create_task(handle_serial())
    )

asyncio.run(main())









