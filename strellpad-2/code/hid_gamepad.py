# SPDX-FileCopyrightText: 2018 Dan Halbert for Adafruit Industries
#
# SPDX-License-Identifier: MIT

"""
`Gamepad`
====================================================

* Author(s): Dan Halbert
"""

import struct
import time

from adafruit_hid import find_device

class Gamepad:
    """Emulate a generic gamepad controller with 5 buttons,
    numbered 0-4, and one encoder knob, controlling `x` values.

    The joystick values could be interpreted
    differently by the receiving program: those are just the names used here.
    The joystick values are in the range -127 to 127."""

    def __init__(self, devices):
        """Create a Gamepad object that will send USB gamepad HID reports.

        Devices can be a list of devices that includes a gamepad device or a gamepad device
        itself. A device is any object that implements ``send_report()``, ``usage_page`` and
        ``usage``.
        """
        self._gamepad_device = find_device(devices, usage_page=0x1, usage=0x04)

        # Reuse this bytearray to send mouse reports.
        # report[0] buttons 0-4
        # report[1] joystick 0 x: -127 to 127
        self._report = bytearray(2)

        # Remember the last report as well, so we can avoid sending
        # duplicate reports.
        self._last_report = bytearray(2)

        # Store settings separately before putting into report. Saves code
        # especially for buttons.
        self._buttons_state = 0
        self._encoder_pos = 0

        # Send an initial report to test if HID device is ready.
        # If not, wait a bit and try once more.
        try:
            self.reset_all()
        except OSError:
            time.sleep(1)
            self.reset_all()

    def press_buttons(self, *buttons):
        """Press and hold the given buttons."""
        for button in buttons:
            self._buttons_state |= 1 << self._validate_button_number(button)
        self._send()

    def release_buttons(self, *buttons):
        """Release the given buttons."""
        for button in buttons:
            self._buttons_state &= ~(1 << self._validate_button_number(button))
        self._send()

    def release_all_buttons(self):
        """Release all the buttons."""

        self._buttons_state = 0
        self._send()

    def click_buttons(self, *buttons):
        """Press and release the given buttons."""
        self.press_buttons(*buttons)
        self.release_buttons(*buttons)

    def move_encoder(self, pos=None):
        """Set and send the given encoder position."""
        if pos is not None:
            self._encoder_pos = self._validate_encoder_value(pos)
        self._send()

    def reset_all(self):
        """Release all buttons and set encoder value to zero."""
        self._buttons_state = 0
        self._encoder_pos = 0
        self._send(always=True)

    def _send(self, always=False):
        """Send a report with all the existing settings.
        If ``always`` is ``False`` (the default), send only if there have been changes.
        """
        struct.pack_into(
            "<BB",
            self._report,
            0,
            self._buttons_state,
            self._encoder_pos
        )

        if always or self._last_report != self._report:
            self._gamepad_device.send_report(self._report)
            # Remember what we sent, without allocating new storage.
            self._last_report[:] = self._report

    @staticmethod
    def _validate_button_number(button):
        if not 0 <= button <= 4:
            raise ValueError("Button number must in range 0 to 4")
        return button

    @staticmethod
    def _validate_encoder_value(value):
        if not 0 <= value <= 255:
            raise ValueError("Encoder value must be in range 0 to 255")
        return value