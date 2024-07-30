import supervisor
import storage
import usb_hid
import json
import os

storage.disable_usb_drive()
storage.remount("/", readonly=False)
supervisor.set_usb_identification("strellic", "strellpad", 0x727, 0x727)

GAMEPAD_REPORT_DESCRIPTOR = bytes((
    0x05, 0x01,        # Usage Page (Generic Desktop Ctrls)
    0x09, 0x04,        # Usage (Joystick)

    0xA1, 0x01,        # Collection (Application)
    0x85, 0x04,        #   Report ID (4)
    # 5 buttons (keys 1-4, knob)
    0x05, 0x09,        #   Usage Page (Button)
    0x19, 0x01,        #   Usage Minimum (0x01)
    0x29, 0x05,        #   Usage Maximum (0x06)
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x01,        #   Logical Maximum (1)
    0x95, 0x05,        #   Report Count (6)
    0x75, 0x01,        #   Report Size (1)
    0x81, 0x02,        #   Input (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position)

    # 1 knob as analog axis
    0x05, 0x01,        #   Usage Page (Generic Desktop Ctrls)
    0x09, 0x01,        #   Usage (Pointer)
    0x15, 0x00,        #   Logical Minimum (0)
    0x26, 0xFF, 0x00,  #   Logical Maximum (255)
    0x95, 0x01,        #   Report Count (1)
    0x75, 0x08,        #   Report Size (8)
    0xA1, 0x00,        #   Collection (Physical)
    0x09, 0x30,        #     Usage (X)
    0x81, 0x02,        #     Input (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position)
    0xC0,              #   End Collection (analog axis)
    0xC0,              # End Collection
))

gamepad = usb_hid.Device(
    report_descriptor=GAMEPAD_REPORT_DESCRIPTOR,
    usage_page=0x01,           # Generic Desktop Control
    usage=0x04,                # Gamepad
    report_ids=(4,),           # Descriptor uses report ID 4.
    in_report_lengths=(2,),    # 5 * 1 + 8 * 1 = 13 bits = 2 bytes
    out_report_lengths=(0,),   # It does not receive any reports.
)

usb_hid.enable((
    usb_hid.Device.KEYBOARD,
    usb_hid.Device.MOUSE,
    usb_hid.Device.CONSUMER_CONTROL,
    gamepad
))

with open("config.json", "r") as f:
    config = json.loads(f.read())

in_usb_mode = False

if config["usb_drive"]:
    config["usb_drive"] = False
    in_usb_mode = True

config["boot_cnt"] = config.get("boot_cnt", 0) + 1
if config["boot_cnt"] >= 4:
    m = storage.getmount("/")
    m.label = "SAFEMODE_SP"
    with open("SAFEMODE_README.txt", "w") as f:
        f.write("\n".join([
            "the device failed to boot multiple times, so it has been booted into safe mode.",
            "please edit the files on the device to fix the problem, then unplug and replug the device to continue the normal boot process.",
            "if using Thonny, repeatedly stop the backend on boot to connect to the device."
        ]))
    config["boot_cnt"] = 0
    config["usb_mode"] = False
    with open("config.json", "w") as f:
        f.write(json.dumps(config))
    storage.enable_usb_drive()
else:
    with open("config.json", "w") as f:
        f.write(json.dumps(config))

    try:
        os.remove("SAFEMODE_README.txt")
    except:
        pass

    if in_usb_mode:
        storage.remount("/", readonly=False)
        m = storage.getmount("/")
        m.label = "STRELLPAD"
        storage.remount("/", readonly=True)
        storage.enable_usb_drive()
    else:
        storage.disable_usb_drive()


