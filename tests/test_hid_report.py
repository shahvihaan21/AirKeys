"""
Unit tests for hid_report.py
Tests:
  - Modifier bit manipulation
  - Scancode key tracking & 6-key rollover limit
  - Report structure (8 bytes: modifier, reserved 0x00, 6 keys)
  - Release-all behavior
  - Key translation for characters and special keys
"""
import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))

from hid_report import (
    HidReportBuilder,
    pynput_key_to_scancode,
    SCAN,
    MOD_NONE,
    MOD_LEFT_SHIFT,
    MOD_LEFT_CTRL,
    MOD_RIGHT_ALT,
    SHIFTED_CHARACTERS,
)


class TestHidReportBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = HidReportBuilder()

    def test_initial_state(self):
        report = self.builder._build()
        self.assertEqual(len(report), 8)
        self.assertEqual(report, b"\x00" * 8)

    def test_single_key_press_and_release(self):
        # Press 'a' (scancode 0x04)
        rep = self.builder.press_key(SCAN["a"])
        self.assertEqual(rep, b"\x00\x00\x04\x00\x00\x00\x00\x00")

        # Release 'a'
        rep_rel = self.builder.release_key(SCAN["a"])
        self.assertEqual(rep_rel, b"\x00" * 8)

    def test_multiple_keys_and_rollover(self):
        # Press keys 1 through 6
        for ch in ["1", "2", "3", "4", "5", "6"]:
            self.builder.press_key(SCAN[ch])

        rep = self.builder._build()
        expected = bytes([0x00, 0x00, SCAN["1"], SCAN["2"], SCAN["3"], SCAN["4"], SCAN["5"], SCAN["6"]])
        self.assertEqual(rep, expected)

        # Press 7th key ('7') -> oldest ('1') should roll over
        rep7 = self.builder.press_key(SCAN["7"])
        expected7 = bytes([0x00, 0x00, SCAN["2"], SCAN["3"], SCAN["4"], SCAN["5"], SCAN["6"], SCAN["7"]])
        self.assertEqual(rep7, expected7)

    def test_modifiers(self):
        # Press Shift
        rep = self.builder.press_modifier(MOD_LEFT_SHIFT)
        self.assertEqual(rep[0], MOD_LEFT_SHIFT)

        # Press Ctrl too
        rep = self.builder.press_modifier(MOD_LEFT_CTRL)
        self.assertEqual(rep[0], MOD_LEFT_SHIFT | MOD_LEFT_CTRL)

        # Release Shift
        rep = self.builder.release_modifier(MOD_LEFT_SHIFT)
        self.assertEqual(rep[0], MOD_LEFT_CTRL)

        # Release all
        rep = self.builder.release_all()
        self.assertEqual(rep, b"\x00" * 8)


class TestKeyTranslation(unittest.TestCase):
    def test_char_key(self):
        mock_key = MagicMock()
        mock_key.char = "h"
        mod, sc = pynput_key_to_scancode(mock_key)
        self.assertIsNone(mod)
        self.assertEqual(sc, SCAN["h"])

    def test_uppercase_char_key(self):
        mock_key = MagicMock()
        mock_key.char = "H"
        mod, sc = pynput_key_to_scancode(mock_key)
        self.assertEqual(mod, MOD_LEFT_SHIFT)
        self.assertEqual(sc, SCAN["h"])

    def test_shifted_symbols_use_us_key_position_and_shift(self):
        for character, unshifted in SHIFTED_CHARACTERS.items():
            with self.subTest(character=character):
                key = MagicMock()
                key.char = character
                modifier, scancode = pynput_key_to_scancode(key)
                self.assertEqual(modifier, MOD_LEFT_SHIFT)
                self.assertEqual(scancode, SCAN[unshifted])

    def test_digits_and_unshifted_punctuation_do_not_add_shift(self):
        for character in "0123456789-=[]\\;',./`":
            with self.subTest(character=character):
                key = MagicMock()
                key.char = character
                self.assertEqual(pynput_key_to_scancode(key), (None, SCAN[character]))

    def test_unsupported_character_is_safely_ignored(self):
        key = MagicMock()
        key.char = "€"
        self.assertEqual(pynput_key_to_scancode(key), (None, None))

    def test_temporary_shift_does_not_clear_physical_modifier(self):
        builder = HidReportBuilder()
        builder.press_modifier(MOD_LEFT_CTRL)
        report = builder.press_key(SCAN["1"], MOD_LEFT_SHIFT)
        self.assertEqual(report[0], MOD_LEFT_CTRL | MOD_LEFT_SHIFT)
        self.assertEqual(builder.release_key(SCAN["1"])[0], MOD_LEFT_CTRL)

    def test_modifier_key(self):
        from pynput.keyboard import Key
        mod, sc = pynput_key_to_scancode(Key.shift)
        self.assertEqual(mod, MOD_LEFT_SHIFT)
        self.assertIsNone(sc)

    def test_special_key(self):
        from pynput.keyboard import Key
        mod, sc = pynput_key_to_scancode(Key.enter)
        self.assertIsNone(mod)
        self.assertEqual(sc, SCAN["enter"])


if __name__ == "__main__":
    unittest.main()
