import board
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

# Edit these values as desired
# controller mappings
BTN_MAPPING = {
    board.GP11: 1, # START
    board.GP14: 2, # BTN A
    board.GP13: 3, # BTN B
    board.GP12: 4, # BTN C
    board.GP2: 5, # BTN D
    board.GP15: 6, # FX L
    board.GP5: 7, # FX R
}
ENCODER_MAPPING = {
    (board.GP17, board.GP16): "x",
    (board.GP19, board.GP18): "y",
}
# encoder / knob options
ENCODER_READ_INTERVAL = 1 / 45
ENCODER_SPEED_RANGE = 200
ENCODER_DEAD_ZONE = 1
# Do not change anything below this line

btn_inv_mapping = {v:k for k,v in BTN_MAPPING.items()}
kb_btn_mapping = {
    btn_inv_mapping[1]: Keycode.ENTER, # START
    btn_inv_mapping[2]: Keycode.D, # BTN A
    btn_inv_mapping[3]: Keycode.F, # BTN B
    btn_inv_mapping[4]: Keycode.J, # BTN C
    btn_inv_mapping[5]: Keycode.K, # BTN D
    btn_inv_mapping[6]: Keycode.C, # FX L
    btn_inv_mapping[7]: Keycode.M, # FX R,
}
start_btn = btn_inv_mapping[1]

gp = Gamepad(usb_hid.devices)
keyboard = Keyboard(usb_hid.devices)
keyboard_layout = KeyboardLayoutUS(keyboard)
mouse = Mouse(usb_hid.devices)

def range_map(x, in_min, in_max, out_min, out_max):
    return (x - in_min) * (out_max - out_min) // (in_max - in_min) + out_min
def wrap_clamp(value, min_value, max_value):
    return (value - min_value) % (max_value - min_value + 1) + min_value

btn_pins = list(BTN_MAPPING.keys())
btn_states = {k: False for k in btn_pins}
keys = keypad.Keys(btn_pins, value_when_pressed=True, pull=True) 
async def read_buttons(mode_kbm):
    while True:
        if event := keys.events.get():
            pin = btn_pins[event.key_number]
            if event.pressed != btn_states[pin]:
                if mode_kbm:
                    handler = keyboard.press if event.pressed else keyboard.release
                    handler(kb_btn_mapping[pin])
                else:
                    handler = gp.press_buttons if event.pressed else gp.release_buttons
                    handler(BTN_MAPPING[pin])
            btn_states[pin] = event.pressed
        await asyncio.sleep(0)

encoder_pins = list(ENCODER_MAPPING.keys())
encoders = { (a,b): rotaryio.IncrementalEncoder(a, b) for a,b in encoder_pins }
encoder_states = { s: 0 for s in encoder_pins }
encoder_axes = { a: 0 for a in list(ENCODER_MAPPING.values()) }
async def read_encoders(mode_kbm):
    while True:
        if mode_kbm:
            encoder_axes.clear()

        for p in encoder_pins:
            pos = encoders[p].position

            if pos != encoder_states[p]:
                delta = pos - encoder_states[p]
                if abs(delta) > ENCODER_DEAD_ZONE:
                    delta = min(max(pos - encoder_states[p], -ENCODER_SPEED_RANGE), ENCODER_SPEED_RANGE)
                    delta = range_map(delta, -ENCODER_SPEED_RANGE, ENCODER_SPEED_RANGE, -127, 127)
                    if mode_kbm:
                        encoder_axes[ENCODER_MAPPING[p]] = delta
                    else:
                        encoder_axes[ENCODER_MAPPING[p]] = wrap_clamp(encoder_axes[ENCODER_MAPPING[p]] + delta, -127, 127)
            encoder_states[p] = pos
        if mode_kbm:
            mouse.move(encoder_axes.get("x", 0), encoder_axes.get("y", 0), 0)
        else:
            gp.move_joysticks(**encoder_axes)
        await asyncio.sleep(ENCODER_READ_INTERVAL)

async def main():
    start_event = keys.events.get()
    mode_kbm = start_event and start_event.key_number == btn_pins.index(start_btn)
    await asyncio.gather(
        asyncio.create_task(read_buttons(mode_kbm)),
        asyncio.create_task(read_encoders(mode_kbm))
    )

asyncio.run(main())

