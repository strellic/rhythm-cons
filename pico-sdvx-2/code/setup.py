import board

# button pin, led pin
BTN_MAPPING = [
    (board.GP18, board.GP19),
    (board.GP2, board.GP3),
    (board.GP4, board.GP5),
    (board.GP14, board.GP15),
    (board.GP16, board.GP17),
    (board.GP6, board.GP7),
    (board.GP8, board.GP9)
]

ENCODER_MAPPING = [
    (board.GP1, board.GP0),
    (board.GP21, board.GP20)
]

LED_PIN = board.GP28
NUM_PIXELS = 10
PIXEL_BRIGHTNESS = 0.2

ENCODER_PPR = 24
ENCODER_PULSE = 4 * ENCODER_PPR

class SDVXControls:
    MAPPING = [
        9,
        1,
        2,
        3,
        4,
        5,
        6,  
    ]
    ENCODER_MULTIPLIER = 1
    ENCODER_DEADZONE = 0
    ENCODER_SLEEP_TIME = 0

class USCControls:
    MAPPING = [
        1,
        2,
        3,
        4,
        5,
        6,
        7
    ]
    ENCODER_MULTIPLIER = 3
    ENCODER_DEADZONE = 1
    ENCODER_SLEEP_TIME = 1/128

TOGGLE_PIN = board.GP13
CONTROLS = [
    SDVXControls,
    USCControls
]

LED_TOGGLE_PIN = board.GP12