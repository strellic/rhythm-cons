import asyncio
import rotaryio
import keypad
import usb_hid
import digitalio
from hid_gamepad import Gamepad
from adafruit_hid.keyboard import Keyboard
from adafruit_hid.keyboard_layout_us import KeyboardLayoutUS
from adafruit_hid.keycode import Keycode
from adafruit_hid.mouse import Mouse
import neopixel
from adafruit_led_animation.animation.comet import Comet
import time

from setup import BTN_MAPPING, ENCODER_MAPPING, ENCODER_PULSE, LED_PIN, NUM_PIXELS, PIXEL_BRIGHTNESS, TOGGLE_PIN, CONTROLS, LED_TOGGLE_PIN

mode = 0
leds = True

pixels = neopixel.NeoPixel(LED_PIN, NUM_PIXELS, brightness=PIXEL_BRIGHTNESS, auto_write=False)
for i in range(NUM_PIXELS):
    pixels[i] = (0,0,0)
pixels.show()

gp = Gamepad(usb_hid.devices)
keyboard = Keyboard(usb_hid.devices)
keyboard_layout = KeyboardLayoutUS(keyboard)
mouse = Mouse(usb_hid.devices)

def setup_led(pin):
    io = digitalio.DigitalInOut(pin)
    io.direction = digitalio.Direction.OUTPUT
    return io

btn_pins = [b[0] for b in BTN_MAPPING]
btn_leds = [setup_led(b[1]) for b in BTN_MAPPING]
btn_states = {k: False for k in btn_pins}
keys = keypad.Keys(btn_pins, value_when_pressed=False, pull=True) 
async def read_buttons():
    while True:
        if event := keys.events.get():
            pin = btn_pins[event.key_number]
            if event.pressed != btn_states[pin]:
                handler = gp.press_buttons if event.pressed else gp.release_buttons
                if leds:
                    btn_leds[event.key_number].value = event.pressed
                handler(CONTROLS[mode].MAPPING[event.key_number])
            btn_states[pin] = event.pressed
        await asyncio.sleep(0)

encoders = { (a,b): rotaryio.IncrementalEncoder(a, b) for a,b in ENCODER_MAPPING }
encoder_axes = {"x": 0, "y": 0}
prev_encoder_values = [0 for _ in range(len(ENCODER_MAPPING))]
curr_encoder_values = [0 for _ in range(len(ENCODER_MAPPING))]
encoder_dir = [0 for _ in range(len(ENCODER_MAPPING))]

async def read_encoders():
    while True:
        for i, p in enumerate(ENCODER_MAPPING):
            pos = encoders[p].position
            
            if abs(pos - prev_encoder_values[i]) <= CONTROLS[mode].ENCODER_DEADZONE:
                continue

            delta = (pos - prev_encoder_values[i]) * CONTROLS[mode].ENCODER_MULTIPLIER
            
            curr_encoder_values[i] += delta
            while curr_encoder_values[i] < 0:
                curr_encoder_values[i] = ENCODER_PULSE + curr_encoder_values[i]
            curr_encoder_values[i] %= ENCODER_PULSE

            next_val = int((curr_encoder_values[i] / ENCODER_PULSE) * 255) - 127
            if encoder_axes[["x", "y"][i]] != next_val:
                encoder_dir[i] = 1 if pos > prev_encoder_values[i] else -1
            
            prev_encoder_values[i] = pos
            encoder_axes[["x", "y"][i]] = next_val
        gp.move_joysticks(**encoder_axes)
        await asyncio.sleep(CONTROLS[mode].ENCODER_SLEEP_TIME)

comet = Comet(pixels, 0.05, (255, 255, 255), tail_length=NUM_PIXELS, ring=True)
last_movetime = [0, 0]
last_movedir = [0, 0]
both_directions = False
async def led_strip():
    global both_directions
    while True:
        if not leds or (encoder_dir[0] == 0 and encoder_dir[1] == 0 and time.monotonic_ns() - max(last_movetime) > 5e+8):
            encoder_dir[0] = 0
            encoder_dir[1] = 0
            for i in range(NUM_PIXELS):
                pixels[i] = (0,0,0)
            pixels.show()
            both_directions = False
            await asyncio.sleep(0.05)
            continue
        
        if encoder_dir[0] != 0:
            last_movetime[0] = time.monotonic_ns()
            last_movedir[0] = encoder_dir[0]
        if encoder_dir[1] != 0:
            last_movetime[1] = time.monotonic_ns()
            last_movedir[1] = encoder_dir[1]
        
        if encoder_dir[0] != 0 and encoder_dir[1] != 0 or both_directions: # both lasers
            both_directions = True
            comet.color = (114, 104, 168)
            last_moved_dir = last_movetime.index(max(last_movetime))
            comet.reverse = last_movedir[last_moved_dir] == -1
        elif encoder_dir[0] != 0 and encoder_dir[1] == 0: # left laser
            comet.color = (28, 200, 255)
            comet.reverse = encoder_dir[0] == -1
        elif encoder_dir[1] != 0 and encoder_dir[0] == 0: # right laser
            comet.color = (200, 8, 80)
            comet.reverse = encoder_dir[1] == -1
            
        comet.animate()
        encoder_dir[0] = 0
        encoder_dir[1] = 0
        await asyncio.sleep(0.05)

options = keypad.Keys([TOGGLE_PIN, LED_TOGGLE_PIN], value_when_pressed=False, pull=True) 
async def read_options():
    global mode
    global leds
    while True:
        if event := options.events.get():
            if event.pressed:
                if event.key_number == 0:
                    mode += 1
                    mode %= len(CONTROLS)
                elif event.key_number == 1:
                    leds = not leds
        await asyncio.sleep(0)

async def main():
    await asyncio.gather(
        asyncio.create_task(read_buttons()),
        asyncio.create_task(read_encoders()),
        asyncio.create_task(led_strip()),
        asyncio.create_task(read_options()),
    )

asyncio.run(main())



