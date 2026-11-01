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

    def test_control_character_mapping(self):
        # When Ctrl is held in Windows, pynput produces ASCII control characters (1-26)
        # Ctrl+C is \x03, Ctrl+V is \x16, Ctrl+A is \x01, Ctrl+Z is \x1a
        for char_code, letter in [(1, "a"), (3, "c"), (22, "v"), (24, "x"), (26, "z")]:
            with self.subTest(letter=letter):
                key = MagicMock()
                key.char = chr(char_code)
                mod, sc = pynput_key_to_scancode(key)
                self.assertIsNone(mod)
                self.assertEqual(sc, SCAN[letter])

    def test_vk_fallback_mapping(self):
        # On key release or with unprintable characters, char might be None while vk is present
        key = MagicMock()
        key.char = None
        key.vk = 67  # 'C'
        mod, sc = pynput_key_to_scancode(key)
        self.assertIsNone(mod)
        self.assertEqual(sc, SCAN["c"])


class TestShortcuts(unittest.TestCase):
    def test_parse_common_shortcuts(self):
        from hid_report import parse_shortcut, MOD_LEFT_CTRL, MOD_LEFT_SHIFT, MOD_LEFT_ALT, MOD_LEFT_GUI

        mod, sc = parse_shortcut("ctrl+c")
        self.assertEqual(mod, MOD_LEFT_CTRL)
        self.assertEqual(sc, SCAN["c"])

        mod, sc = parse_shortcut("ctrl+v")
        self.assertEqual(mod, MOD_LEFT_CTRL)
        self.assertEqual(sc, SCAN["v"])

        mod, sc = parse_shortcut("Ctrl + Shift + Z")
        self.assertEqual(mod, MOD_LEFT_CTRL | MOD_LEFT_SHIFT)
        self.assertEqual(sc, SCAN["z"])

        mod, sc = parse_shortcut("alt+tab")
        self.assertEqual(mod, MOD_LEFT_ALT)
        self.assertEqual(sc, SCAN["tab"])

        mod, sc = parse_shortcut("win+d")
        self.assertEqual(mod, MOD_LEFT_GUI)
        self.assertEqual(sc, SCAN["d"])

    def test_shortcut_aliases(self):
        from hid_report import parse_shortcut, MOD_LEFT_CTRL

        for alias, target_key in [("copy", "c"), ("paste", "v"), ("cut", "x"), ("select_all", "a"), ("undo", "z")]:
            with self.subTest(alias=alias):
                mod, sc = parse_shortcut(alias)
                self.assertEqual(mod, MOD_LEFT_CTRL)
                self.assertEqual(sc, SCAN[target_key])

    def test_build_shortcut_reports(self):
        from hid_report import build_shortcut_reports, MOD_LEFT_CTRL

        press, release = build_shortcut_reports("ctrl+c")
        self.assertEqual(len(press), 8)
        self.assertEqual(press[0], MOD_LEFT_CTRL)
        self.assertEqual(press[2], SCAN["c"])

        self.assertEqual(len(release), 8)
        self.assertEqual(release, b"\x00" * 8)

    def test_invalid_shortcuts_raise_value_error(self):
        from hid_report import parse_shortcut

        with self.assertRaises(ValueError):
            parse_shortcut("")

        with self.assertRaises(ValueError):
            parse_shortcut("ctrl")  # only modifier, no key

        with self.assertRaises(ValueError):
            parse_shortcut("ctrl+c+v")  # multiple keys

        with self.assertRaises(ValueError):
            parse_shortcut("ctrl+nonexistentkey123")


class TestKeyMappingsAndSpecialKeys(unittest.TestCase):
    def test_caps_lock_and_insert(self):
        mock_caps = MagicMock()
        mock_caps.__str__.return_value = "Key.caps_lock"
        mock_caps.char = None
        mock_caps.vk = None
        mod, sc = pynput_key_to_scancode(mock_caps)
        self.assertIsNone(mod)
        self.assertEqual(sc, 0x39)

        mock_ins = MagicMock()
        mock_ins.__str__.return_value = "Key.insert"
        mock_ins.char = None
        mock_ins.vk = None
        mod, sc = pynput_key_to_scancode(mock_ins)
        self.assertIsNone(mod)
        self.assertEqual(sc, 0x49)

    def test_additional_special_keys(self):
        special_expectations = {
            "Key.print_screen": 0x46,
            "Key.scroll_lock": 0x47,
            "Key.pause": 0x48,
            "Key.num_lock": 0x53,
            "Key.menu": 0x65,
        }
        for key_name, expected_sc in special_expectations.items():
            with self.subTest(key=key_name):
                mock_key = MagicMock()
                mock_key.__str__.return_value = key_name
                mock_key.char = None
                mock_key.vk = None
                mod, sc = pynput_key_to_scancode(mock_key)
                self.assertIsNone(mod)
                self.assertEqual(sc, expected_sc)

    def test_numpad_virtual_keys(self):
        # VK_NUMPAD0 (0x60) through VK_NUMPAD9 (0x69)
        for i in range(10):
            mock_key = MagicMock()
            mock_key.__str__.return_value = f"<96+{i}>"
            mock_key.char = None
            mock_key.vk = 0x60 + i
            mod, sc = pynput_key_to_scancode(mock_key)
            self.assertIsNone(mod)
            self.assertEqual(sc, SCAN[str(i)])

        # VK_SUBTRACT (0x6D)
        mock_minus = MagicMock()
        mock_minus.__str__.return_value = "<109>"
        mock_minus.char = None
        mock_minus.vk = 0x6D
        mod, sc = pynput_key_to_scancode(mock_minus)
        self.assertIsNone(mod)
        self.assertEqual(sc, SCAN["-"])

    def test_parse_shortcut_insert(self):
        from hid_report import parse_shortcut, MOD_LEFT_CTRL
        mod, sc = parse_shortcut("ctrl+insert")
        self.assertEqual(mod, MOD_LEFT_CTRL)
        self.assertEqual(sc, 0x49)


class TestTextToHidReports(unittest.TestCase):
    def test_char_to_hid_report_alphanumeric(self):
        from hid_report import char_to_hid_report

        # Lowercase 'h'
        press, release = char_to_hid_report("h")
        self.assertEqual(press[0], 0x00)
        self.assertEqual(press[2], SCAN["h"])
        self.assertEqual(release, b"\x00" * 8)

        # Uppercase 'H' (adds Left Shift)
        press, release = char_to_hid_report("H")
        self.assertEqual(press[0], MOD_LEFT_SHIFT)
        self.assertEqual(press[2], SCAN["h"])
        self.assertEqual(release, b"\x00" * 8)

        # Digit '5'
        press, release = char_to_hid_report("5")
        self.assertEqual(press[0], 0x00)
        self.assertEqual(press[2], SCAN["5"])
        self.assertEqual(release, b"\x00" * 8)

    def test_char_to_hid_report_shifted_symbols(self):
        from hid_report import char_to_hid_report

        press, release = char_to_hid_report("!")
        self.assertEqual(press[0], MOD_LEFT_SHIFT)
        self.assertEqual(press[2], SCAN["1"])
        self.assertEqual(release, b"\x00" * 8)

    def test_char_to_hid_report_whitespace(self):
        from hid_report import char_to_hid_report

        press, _ = char_to_hid_report(" ")
        self.assertEqual(press[2], SCAN["space"])

        press, _ = char_to_hid_report("\n")
        self.assertEqual(press[2], SCAN["enter"])

        press, _ = char_to_hid_report("\t")
        self.assertEqual(press[2], SCAN["tab"])

    def test_char_to_hid_report_invalid(self):
        from hid_report import char_to_hid_report

        self.assertIsNone(char_to_hid_report(""))
        self.assertIsNone(char_to_hid_report("ab"))
        self.assertIsNone(char_to_hid_report("😀"))

    def test_text_to_hid_reports(self):
        from hid_report import text_to_hid_reports

        pairs = text_to_hid_reports("Hi 1\n")
        # 5 characters: 'H', 'i', ' ', '1', '\n'
        self.assertEqual(len(pairs), 5)

        # Check 'H'
        press_h, rel_h = pairs[0]
        self.assertEqual(press_h[0], MOD_LEFT_SHIFT)
        self.assertEqual(press_h[2], SCAN["h"])
        self.assertEqual(rel_h, b"\x00" * 8)

        # Check 'i'
        press_i, _ = pairs[1]
        self.assertEqual(press_i[0], 0x00)
        self.assertEqual(press_i[2], SCAN["i"])

        # Check CRLF normalized
        pairs_crlf = text_to_hid_reports("A\r\nB")
        self.assertEqual(len(pairs_crlf), 3)  # 'A', '\n', 'B'



if __name__ == "__main__":
    unittest.main()

