#!/usr/bin/env python3
"""
switch.py — Instant AirKeys ON / OFF Switch

Usage:
  python scripts/switch.py              Flip the ON/OFF switch immediately
  python scripts/switch.py -i           Open the interactive visual switch
"""
import os
import sys

# Ensure root dir is in sys.path so cli module can be imported
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from cli import cmd_switch

class Args:
    interactive = "-i" in sys.argv or "--interactive" in sys.argv

if __name__ == "__main__":
    sys.exit(cmd_switch(Args()))
