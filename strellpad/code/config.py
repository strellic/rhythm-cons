from adafruit_hid.keycode import Keycode
import neopixel
import board
import json
import os

default_data = {
    "active_profile": 0,
    "profiles": [
        {
            "name": "base",
            "calibration": [[0, 0] for _ in range(4)],
            "color": [[255, 255, 255] for _ in range(4 + 1)],
            "rapid_trigger": True,
            "continuous_rapid_trigger": True,
            "rt_area": 0.05,
            "actuation": 0.2,
            "keys": [["Z"], ["X"], ["C"], ["V"], ["LEFT_ARROW"], ["RIGHT_ARROW"]],
            "enc_keys": [[("ENTER", 0)], [("ESCAPE", 0.5)]],
            "key_brightness": 1,
            "edge_brightness": 0.25,
            "edge_anim": ["rainbow", [0.1, 5, 1]],
            "reactive_edge": False,
            "reactive_time": 2,
            "enc_hold_time": 0.5,
        }
    ],
    "usb_drive": False
}

class Config:
    def __init__(self, data):
        for key in data.keys():
            setattr(self, key, data[key])
    def __repr__(self):
        return json.dumps(self.__dict__)

try:
    os.stat("config.json")
except Exception as e:
    print("no config found, generating!")
    with open("config.json", "w") as f:
        f.write(json.dumps(default_data))
        
data = None
config_data = None
active_profile = 0

def save():
    with open("config.json", "w") as f:
        config_data["profiles"][active_profile] = data.__dict__
        f.write(json.dumps(config_data))

def load():
    global data
    global config_data
    global active_profile
    with open("config.json", "r") as f:
        config_data = json.loads(f.read())
        active_profile = config_data["active_profile"]
        data = Config(config_data["profiles"][active_profile])

def change_profile(v):
    global data
    global config_data
    global active_profile
    active_profile = v
    config_data["active_profile"] = v
    with open("config.json", "w") as f:
        f.write(json.dumps(config_data))
    data = Config(config_data["profiles"][active_profile])

load()

from adafruit_led_animation.helper import PixelMap
pixels = neopixel.NeoPixel(board.GP14, 11, brightness=1, auto_write=False)
for i in range(11):
    pixels[i] = (0,0,0)
pixels.show()

neopixel.NeoPixel(board.NEOPIXEL, 1, brightness=0, auto_write=True)[0] = (0,0,0)

key_pixels = PixelMap(pixels, [3, 4, 6, 7], individual_pixels=True)
edge_pixels = PixelMap(pixels, [0, 1, 2, 5, 8, 9, 10], individual_pixels=True)

class SolidAnim:
    def __init__(self, pixels, color):
        self.pixels = pixels
        self.color = color
    def animate(self, _):
        for i in range(len(self.pixels)):
            self.pixels[i] = self.color

class NoneAnim:
    def __init__(self, pixels):
        self.pixels = pixels
    def animate(self, _):
        for i in range(len(self.pixels)):
            self.pixels[i] = (0, 0, 0)

from adafruit_led_animation.animation.blink import Blink
from adafruit_led_animation.animation.chase import Chase
from adafruit_led_animation.animation.comet import Comet
from adafruit_led_animation.animation.pulse import Pulse
from adafruit_led_animation.animation.rainbow import Rainbow
from adafruit_led_animation.animation.rainbowchase import RainbowChase
from adafruit_led_animation.animation.rainbowcomet import RainbowComet
anim_map = {
    "none": NoneAnim,
    "blink": Blink,
    "solid": SolidAnim,
    "chase": Chase,
    "comet": Comet,
    "pulse": Pulse,
    "rainbow": Rainbow,
    "rainbowchase": RainbowChase,
    "rainbowcomet": RainbowComet
}

# name, default, min, max, step
anim_args_map = {
    "none":    [ edge_pixels ],
    "blink":   [ edge_pixels, ("speed (s)", 0.1, 0.1, 10, 0.1), "COLOR" ],
    "solid":   [ edge_pixels, "COLOR" ],
    "chase":   [ edge_pixels, ("speed (s)", 0.1, 0.1, 10, 0.1), "COLOR", ("size", 2, 1, 10, 1), ("spacing", 3, 0, 10, 1), ("reverse", 0, 0, 1, 1) ],
    "comet":   [ edge_pixels, ("speed (s)", 0.1, 0.1, 10, 0.1), "COLOR", 0x000000, ("tail_length", 3, 1, 10, 1), ("reverse", 0, 0, 1, 1), ("bounce", 0, 0, 1, 1) ],
    "pulse":   [ edge_pixels, ("speed (s)", 0.1, 0.1, 10, 0.1), "COLOR", ("period", 5, 1, 20, 1), ("breath", 0.0, 0.0, 10.0, 0.1), ("min_intensity", 0, 0, 1, 0.1), ("max_intensity", 1, 0, 1, 0.1) ],
    "rainbow": [ edge_pixels, ("speed (s)", 0.1, 0.1, 10, 0.1), ("period", 5, 1, 20, 1), ("step", 1, 1, 10, 1), "", True ],
    "rainbowchase": [ edge_pixels, ("speed (s)", 0.1, 0.1, 10, 0.1), ("size", 2, 1, 10, 1), ("spacing", 3, 0, 10, 1), ("reverse", 0, 0, 1, 1), ("step", 8, 1, 10, 1) ],
    "rainbowcomet": [ edge_pixels, ("speed (s)", 0.1, 0.1, 10, 0.1), ("tail_length", 2, 1, 10, 1), ("reverse", 0, 0, 1, 1), ("bounce", 0, 0, 1, 1), 0, ("step", 0, 1, 10, 1) ]
}

def load_anim(name, values):
    args = list(anim_args_map[name])
    values = list(values)
    for i, arg in enumerate(args):
        if isinstance(arg, tuple):
            args[i] = args[i][1] if len(values) == 0 else values.pop(0)
        if isinstance(arg, str) and arg == "COLOR":
            args[i] = data.color[4]
    return anim_map[name](*args)

edge_anim = load_anim(*data.edge_anim)

