import supervisor
import storage
import json

storage.remount("/", readonly=False)
supervisor.set_usb_identification("strellic", "strellpad", 0x727, 0x727)

with open("config.json", "r") as f:
    config = json.loads(f.read())

if config["usb_drive"]:
    config["usb_drive"] = False
    with open("config.json", "w") as f:
        f.write(json.dumps(config))
    storage.enable_usb_drive()
else:
    storage.disable_usb_drive()