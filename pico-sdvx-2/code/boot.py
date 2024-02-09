import usb_hid

# This is only one example of a gamepad descriptor, and may not suit your needs.
GAMEPAD_REPORT_DESCRIPTOR = bytes((
0x05, 0x01,        # Usage Page (Generic Desktop Ctrls)
0x09, 0x04,        # Usage (Joystick)

0xA1, 0x01,        # Collection (Application)
  0x85, 0x04,        #   Report ID (4)
    # 9 buttons (a b c d, fx l, fx r, service, test, start */
  0x05, 0x09,        #   Usage Page (Button)
  0x19, 0x01,        #   Usage Minimum (0x01)
  0x29, 0x10,        #   Usage Maximum (0x09)
  0x15, 0x00,        #   Logical Minimum (0)
  0x25, 0x01,        #   Logical Maximum (1)
  0x95, 0x10,        #   Report Count (9)
  0x75, 0x01,        #   Report Size (1)
  0x81, 0x02,        #   Input (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position)
  
    # 2 knobs as analog axis */
  0x05, 0x01,        #   Usage Page (Generic Desktop Ctrls)
  0x09, 0x01,        #   Usage (Pointer)
  0x15, 0x00,        #   Logical Minimum (0)
  0x26, 0xFF, 0x00,  #   Logical Maximum (255)
  0x95, 0x02,        #   Report Count (2)
  0x75, 0x08,        #   Report Size (8)
  0xA1, 0x00,        #   Collection (Physical)
    0x09, 0x30,        #     Usage (X)
    0x09, 0x31,        #     Usage (Y)
    0x81, 0x02,        #     Input (Data,Var,Abs,No Wrap,Linear,Preferred State,No Null Position)
  0xC0,              #   End Collection (analog axis)
    0xC0,        # End Collection
))

gamepad = usb_hid.Device(
    report_descriptor=GAMEPAD_REPORT_DESCRIPTOR,
    usage_page=0x01,           # Generic Desktop Control
    usage=0x04,                # Gamepad
    report_ids=(4,),           # Descriptor uses report ID 4.
    in_report_lengths=(4,),    # This gamepad sends 6 bytes in its report.
    out_report_lengths=(0,),   # It does not receive any reports.
)

usb_hid.enable(
    (usb_hid.Device.KEYBOARD,
     usb_hid.Device.MOUSE,
     usb_hid.Device.CONSUMER_CONTROL,
     gamepad)
)