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


if __name__ == "__main__":
    unittest.main()
