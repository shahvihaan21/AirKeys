"""
Unit tests for cli.py helper routines and state management.
"""
import os
import unittest
from unittest.mock import patch

import cli


class TestCliHelpers(unittest.TestCase):
    def test_is_pid_running_current(self):
        """Current process PID should always be recognized as running."""
        current_pid = os.getpid()
        self.assertTrue(cli.is_pid_running(current_pid))

    def test_is_pid_running_invalid(self):
        """Invalid PIDs (negative, 0, or non-existent) should return False."""
        self.assertFalse(cli.is_pid_running(-1))
        self.assertFalse(cli.is_pid_running(0))
        self.assertFalse(cli.is_pid_running(9999999))

    def test_get_current_pid_no_file(self):
        """When no PID file exists, get_current_pid should return None."""
        with patch("os.path.exists", return_value=False):
            self.assertIsNone(cli.get_current_pid())

    def test_get_current_pid_airkeys(self):
        """Should detect running PID from .airkeys.pid."""
        current_pid = os.getpid()
        with patch("os.path.exists", side_effect=lambda p: p == cli.PID_FILE), \
             patch("builtins.open", unittest.mock.mock_open(read_data=str(current_pid))):
            self.assertEqual(cli.get_current_pid(), current_pid)

    def test_get_current_pid_legacy_fallback(self):
        """Should detect running PID from .laptopkey.pid if primary not found."""
        current_pid = os.getpid()
        with patch("os.path.exists", side_effect=lambda p: p == cli.LEGACY_PID_FILE), \
             patch("builtins.open", unittest.mock.mock_open(read_data=str(current_pid))):
            self.assertEqual(cli.get_current_pid(), current_pid)

    def test_cmd_on_stops_before_launch_when_environment_is_invalid(self):
        """A missing dependency should be reported before a background process starts."""
        with patch("cli.environment_problems", return_value=["Missing dependency: pynput."]), \
             patch("cli.subprocess.Popen") as popen:
            self.assertEqual(cli.cmd_on(), 2)
        popen.assert_not_called()

    def test_cmd_shortcut_when_service_not_running(self):
        """Should fail cleanly when AirKeys is not running."""
        with patch("cli.get_current_pid", return_value=None):
            args = unittest.mock.Mock(combo="ctrl+c")
            self.assertEqual(cli.cmd_shortcut(args), 1)

    def test_cmd_shortcut_writes_to_cmd_file_when_running(self):
        """Should write shortcut command to CMD_FILE when service is running."""
        mock_file = unittest.mock.mock_open()
        with patch("cli.get_current_pid", return_value=12345), \
             patch("builtins.open", mock_file):
            args = unittest.mock.Mock(combo="ctrl+v")
            self.assertEqual(cli.cmd_shortcut(args), 0)
        mock_file().write.assert_called_with("shortcut:ctrl+v\n")

    def test_cmd_shortcut_invalid_combo(self):
        """Invalid shortcut combo should return error code 1."""
        with patch("cli.get_current_pid", return_value=12345):
            args = unittest.mock.Mock(combo="invalid_key_combo_xyz")
            self.assertEqual(cli.cmd_shortcut(args), 1)

    def test_cmd_type_when_service_not_running(self):
        """Should fail cleanly when AirKeys is not running."""
        with patch("cli.get_current_pid", return_value=None):
            args = unittest.mock.Mock(text=["Hello"], clipboard=False)
            self.assertEqual(cli.cmd_type(args), 1)

    def test_cmd_type_writes_to_cmd_file_when_running(self):
        """Should write json-encoded text command to CMD_FILE when service is running."""
        mock_file = unittest.mock.mock_open()
        with patch("cli.get_current_pid", return_value=12345), \
             patch("builtins.open", mock_file):
            args = unittest.mock.Mock(text=["Hello", "world"], clipboard=False)
            self.assertEqual(cli.cmd_type(args), 0)
        mock_file().write.assert_called_with('text:"Hello world"\n')

    def test_cmd_type_with_clipboard(self):
        """Should read from clipboard and write to CMD_FILE."""
        mock_file = unittest.mock.mock_open()
        with patch("cli.get_current_pid", return_value=12345), \
             patch("cli.get_clipboard_text", return_value="pasted clipboard text"), \
             patch("builtins.open", mock_file):
            args = unittest.mock.Mock(text=None, clipboard=True)
            self.assertEqual(cli.cmd_type(args), 0)
        mock_file().write.assert_called_with('text:"pasted clipboard text"\n')

    def test_cmd_type_clipboard_empty(self):
        """Should fail cleanly when clipboard is empty."""
        with patch("cli.get_current_pid", return_value=12345), \
             patch("cli.get_clipboard_text", return_value=None):
            args = unittest.mock.Mock(text=None, clipboard=True)
            self.assertEqual(cli.cmd_type(args), 1)

    def test_cmd_type_no_args_shows_help(self):
        """Calling without text or clipboard should show help and return 0."""
        args = unittest.mock.Mock(text=None, clipboard=False)
        self.assertEqual(cli.cmd_type(args), 0)

    def test_get_clipboard_text_error_handling(self):
        """When ctypes throws an exception, get_clipboard_text should return None cleanly."""
        with patch("ctypes.windll.user32.OpenClipboard", side_effect=Exception("Lock error")):
            self.assertIsNone(cli.get_clipboard_text())


if __name__ == "__main__":
    unittest.main()

