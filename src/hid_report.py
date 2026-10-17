"""
hid_report.py — HID Report Generation for BLE Keyboard

Provides:
  - Standard USB HID keyboard report descriptor (8-byte boot protocol)
  - Key-to-scancode mapping
  - Report construction for key-down and key-up events
"""

# Standard HID Report Descriptor for a Boot Keyboard
# 8-byte report: [modifier, reserved, key1, key2, key3, key4, key5, key6]
KEYBOARD_REPORT_MAP = bytes([
    0x05, 0x01,        # Usage Page (Generic Desktop)
    0x09, 0x06,        # Usage (Keyboard)
    0xA1, 0x01,        # Collection (Application)

    # Modifier byte (8 bits for Ctrl/Shift/Alt/GUI, left & right)
    0x05, 0x07,        #   Usage Page (Keyboard/Keypad)
    0x19, 0xE0,        #   Usage Minimum (Left Control)
    0x29, 0xE7,        #   Usage Maximum (Right GUI)
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x01,        #   Logical Maximum (1)
    0x95, 0x08,        #   Report Count (8)
    0x75, 0x01,        #   Report Size (1)
    0x81, 0x02,        #   Input (Data, Variable, Absolute) — Modifier byte

    # Reserved byte
    0x95, 0x01,        #   Report Count (1)
    0x75, 0x08,        #   Report Size (8)
    0x81, 0x03,        #   Input (Constant) — Reserved byte

    # Keycodes (6 keys)
    0x95, 0x06,        #   Report Count (6)
    0x75, 0x08,        #   Report Size (8)
    0x15, 0x00,        #   Logical Minimum (0)
    0x25, 0x65,        #   Logical Maximum (101)
    0x05, 0x07,        #   Usage Page (Keyboard/Keypad)
    0x19, 0x00,        #   Usage Minimum (0)
    0x29, 0x65,        #   Usage Maximum (101)
    0x81, 0x00,        #   Input (Data, Array) — Key array (6 slots)

    0xC0,              # End Collection
])

# Report length (excluding report ID, which is not used in single-report HOGP)
REPORT_LENGTH = 8

# --- Modifier bit masks (byte 0 of report) ---
MOD_NONE        = 0x00
MOD_LEFT_CTRL   = 0x01
MOD_LEFT_SHIFT  = 0x02
MOD_LEFT_ALT    = 0x04
MOD_LEFT_GUI    = 0x08
MOD_RIGHT_CTRL  = 0x10
MOD_RIGHT_SHIFT = 0x20
MOD_RIGHT_ALT   = 0x40
MOD_RIGHT_GUI   = 0x80

# --- USB HID Scancodes (Usage Page 0x07) ---
# Reference: USB HID Usage Tables, Section 10 (Keyboard/Keypad Page)
SCAN = {
    'a': 0x04, 'b': 0x05, 'c': 0x06, 'd': 0x07,
    'e': 0x08, 'f': 0x09, 'g': 0x0A, 'h': 0x0B,
    'i': 0x0C, 'j': 0x0D, 'k': 0x0E, 'l': 0x0F,
    'm': 0x10, 'n': 0x11, 'o': 0x12, 'p': 0x13,
    'q': 0x14, 'r': 0x15, 's': 0x16, 't': 0x17,
    'u': 0x18, 'v': 0x19, 'w': 0x1A, 'x': 0x1B,
    'y': 0x1C, 'z': 0x1D,
    '1': 0x1E, '2': 0x1F, '3': 0x20, '4': 0x21,
    '5': 0x22, '6': 0x23, '7': 0x24, '8': 0x25,
    '9': 0x26, '0': 0x27,
    'enter':     0x28,
    'escape':    0x29,
    'backspace': 0x2A,
    'tab':       0x2B,
    'space':     0x2C,
    '-': 0x2D, '=': 0x2E, '[': 0x2F, ']': 0x30,
    '\\': 0x31, ';': 0x33, "'": 0x34, '`': 0x35,
    ',': 0x36, '.': 0x37, '/': 0x38,
    'f1': 0x3A, 'f2': 0x3B, 'f3': 0x3C, 'f4': 0x3D,
    'f5': 0x3E, 'f6': 0x3F, 'f7': 0x40, 'f8': 0x41,
    'f9': 0x42, 'f10': 0x43, 'f11': 0x44, 'f12': 0x45,
    'right': 0x4F, 'left': 0x50, 'down': 0x51, 'up': 0x52,
    'delete': 0x4C, 'home': 0x4A, 'end': 0x4D,
    'page_up': 0x4B, 'page_down': 0x4E,
    'caps_lock': 0x39, 'insert': 0x49,
}

# pynput Key enum name → our key name (for special keys)
PYNPUT_SPECIAL_MAP = {
    'Key.enter':      'enter',
    'Key.backspace':  'backspace',
    'Key.space':      'space',
    'Key.tab':        'tab',
    'Key.escape':     'escape' ,
    'Key.delete':     'delete',
    'Key.up':         'up',
    'Key.down':       'down',
    'Key.left':       'left',
    'Key.right':      'right',
    'Key.home':       'home',
    'Key.end':        'end',
    'Key.page_up':    'page_up',
    'Key.page_down':  'page_down',
    'Key.caps_lock':  'caps_lock',
    'Key.insert':     'insert',
    'Key.f1':  'f1',  'Key.f2':  'f2',  'Key.f3':  'f3',  'Key.f4':  'f4',
    'Key.f5':  'f5',  'Key.f6':  'f6',  'Key.f7':  'f7',  'Key.f8':  'f8',
    'Key.f9':  'f9',  'Key.f10': 'f10', 'Key.f11': 'f11', 'Key.f12': 'f12',
}

# pynput Key enum name → modifier bit
PYNPUT_MODIFIER_MAP = {
    'Key.shift':       MOD_LEFT_SHIFT,
    'Key.shift_l':     MOD_LEFT_SHIFT,
    'Key.shift_r':     MOD_RIGHT_SHIFT,
    'Key.ctrl':        MOD_LEFT_CTRL,
    'Key.ctrl_l':      MOD_LEFT_CTRL,
    'Key.ctrl_r':      MOD_RIGHT_CTRL,
    'Key.alt':         MOD_LEFT_ALT,
    'Key.alt_l':       MOD_LEFT_ALT,
    'Key.alt_r':       MOD_RIGHT_ALT,
    'Key.alt_gr':      MOD_RIGHT_ALT,
    'Key.cmd':         MOD_LEFT_GUI,
    'Key.cmd_l':       MOD_LEFT_GUI,
    'Key.cmd_r':       MOD_RIGHT_GUI,
}


class HidReportBuilder:
    """
    Tracks currently pressed keys and modifiers, and builds
    standard 8-byte HID keyboard reports.
    """

    def __init__(self):
        self._modifiers: int = MOD_NONE
        self._keys: list[int] = []  # up to 6 scancodes

    def press_modifier(self, mod_bit: int) -> bytes:
        """Add a modifier and return the updated report."""
        self._modifiers |= mod_bit
        return self._build()

    def release_modifier(self, mod_bit: int) -> bytes:
        """Remove a modifier and return the updated report."""
        self._modifiers &= ~mod_bit
        return self._build()

    def press_key(self, scancode: int) -> bytes:
        """Add a scancode and return the updated report."""
        if scancode not in self._keys:
            if len(self._keys) >= 6:
                self._keys.pop(0)  # roll over — drop oldest
            self._keys.append(scancode)
        return self._build()

    def release_key(self, scancode: int) -> bytes:
        """Remove a scancode and return the updated report."""
        if scancode in self._keys:
            self._keys.remove(scancode)
        return self._build()

    def release_all(self) -> bytes:
        """Release everything."""
        self._modifiers = MOD_NONE
        self._keys.clear()
        return self._build()

    def _build(self) -> bytes:
        """Build the 8-byte report: [modifier, 0x00, key1..key6]."""
        report = bytearray(REPORT_LENGTH)
        report[0] = self._modifiers
        report[1] = 0x00  # reserved
        for i, sc in enumerate(self._keys[:6]):
            report[2 + i] = sc
        return bytes(report)


def pynput_key_to_scancode(key) -> tuple[int | None, int | None]:
    """
    Convert a pynput key event to (modifier_bit, scancode).
    Returns (modifier_bit, None) for modifier keys.
    Returns (None, scancode) for regular keys.
    Returns (None, None) for unmapped keys.
    """
    key_str = str(key)

    # Check if it's a modifier
    mod = PYNPUT_MODIFIER_MAP.get(key_str)
    if mod is not None:
        return (mod, None)

    # Check if it's a special key
    special = PYNPUT_SPECIAL_MAP.get(key_str)
    if special is not None:
        sc = SCAN.get(special)
        return (None, sc)

    # Check if it's a character key (pynput wraps chars in quotes)
    try:
        char = key.char
        if char is not None:
            sc = SCAN.get(char.lower())
            return (None, sc)
    except AttributeError:
        pass

    return (None, None)
