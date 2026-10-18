#!/usr/bin/env python3
"""
run.py — One-File Manager to Start and Stop AirKeys

Usage:
  python run.py                  Interactive Control Center (Press Enter to Toggle)
  python run.py start            Start AirKeys in background
  python run.py stop             Stop AirKeys cleanly
  python run.py toggle           Toggle ON / OFF immediately
  python run.py status           Show live service status and recent logs
  python run.py --fg             Run in foreground (Ctrl+C to stop)
"""
import os
import sys
import time

# Ensure root directory is in python path
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

import cli


class Args:
    def __init__(self, foreground=False, interactive=False):
        self.foreground = foreground
        self.interactive = interactive


def start(foreground=False):
    """Start AirKeys."""
    return cli.cmd_on(Args(foreground=foreground))


def stop():
    """Stop AirKeys."""
    return cli.cmd_off()


def status():
    """Show status."""
    return cli.cmd_status()


def toggle():
    """Toggle Start / Stop."""
    pid = cli.get_current_pid()
    if pid is not None:
        return stop()
    else:
        return start()


def interactive_menu():
    """Interactive loop to easily start, stop, or toggle."""
    while True:
        pid = cli.get_current_pid()
        is_running = pid is not None
        status_badge = f"🟢 RUNNING (PID: {pid})" if is_running else "🔴 STOPPED"
        action_label = "Turn OFF [Stop]" if is_running else "Turn ON [Start]"

        print("\n" + "=" * 54)
        print("               AirKeys Quick Manager")
        print("=" * 54)
        print(f"  Current Status: {status_badge}")
        print("-" * 54)
        print(f"  [Enter]  ->  {action_label} (Instant Toggle)")
        print(f"  [1]      ->  Start (Background)")
        print(f"  [2]      ->  Stop")
        print(f"  [3]      ->  Status & Recent Logs")
        print(f"  [4]      ->  Run in Foreground (Live debug)")
        print(f"  [0/q]    ->  Exit")
        print("=" * 54)

        try:
            choice = input(f"Select option [Enter to {action_label}]: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\nExiting.")
            break

        if choice in ("", "toggle", "t"):
            toggle()
            time.sleep(1.0)
        elif choice in ("1", "start", "on"):
            start()
            time.sleep(1.0)
        elif choice in ("2", "stop", "off"):
            stop()
            time.sleep(0.8)
        elif choice in ("3", "status", "s"):
            status()
            try:
                input("\nPress Enter to return to menu...")
            except (KeyboardInterrupt, EOFError):
                pass
        elif choice in ("4", "fg", "foreground"):
            start(foreground=True)
        elif choice in ("0", "q", "exit", "quit"):
            print("Bye!")
            break
        else:
            print("Invalid selection. Try again.")


def main():
    # Windows console UTF-8 support
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    args = sys.argv[1:]
    if not args:
        interactive_menu()
        return

    cmd = args[0].lower().strip("-")
    if cmd in ("start", "on"):
        sys.exit(start())
    elif cmd in ("stop", "off"):
        sys.exit(stop())
    elif cmd in ("toggle", "switch"):
        sys.exit(toggle())
    elif cmd in ("status", "info"):
        sys.exit(status())
    elif cmd in ("fg", "foreground", "run"):
        sys.exit(start(foreground=True))
    elif cmd in ("help", "h"):
        print(__doc__)
    else:
        print(f"Unknown command: '{args[0]}'\n")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
