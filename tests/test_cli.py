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


if __name__ == "__main__":
    unittest.main()
