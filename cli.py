#!/usr/bin/env python3
"""
cli.py — LaptopKey Master CLI & On/Off Switch

Commands:
  python cli.py on          Turn ON LaptopKey in background
  python cli.py off         Turn OFF LaptopKey cleanly
  python cli.py switch      Toggle ON/OFF switch
  python cli.py status      Show current status and connection
  python cli.py logs        Show recent log output
  python cli.py check       Check Bluetooth adapter capabilities
  python cli.py restart     Restart the service
"""
import argparse
import asyncio
import ctypes
from ctypes import wintypes
import os
import subprocess
import sys
import time

# Ensure Windows console handles UTF-8 / emojis gracefully
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Directory and file paths
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
MAIN_PY = os.path.join(ROOT_DIR, "src", "main.py")
PID_FILE = os.path.join(ROOT_DIR, ".laptopkey.pid")
STOP_FILE = os.path.join(ROOT_DIR, ".laptopkey.stop")
LOG_FILE = os.path.join(ROOT_DIR, "laptopkey.log")


# =====================================================================
# Windows Process Helpers (using ctypes, no external psutil required)
# =====================================================================

def is_pid_running(pid: int) -> bool:
    """Check if process with given PID exists and is currently active."""
    if pid <= 0:
        return False
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    SYNCHRONIZE = 0x00100000
    handle = ctypes.windll.kernel32.OpenProcess(
        PROCESS_QUERY_LIMITED_INFORMATION | SYNCHRONIZE, False, pid
    )
    if not handle:
        return False
    exit_code = wintypes.DWORD()
    ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code))
    ctypes.windll.kernel32.CloseHandle(handle)
    return exit_code.value == 259  # 259 = STILL_ACTIVE


def get_current_pid() -> int | None:
    """Read PID from PID_FILE if it exists and process is alive."""
    if not os.path.exists(PID_FILE):
        return None
    try:
        with open(PID_FILE, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return None
            pid = int(content)
            if is_pid_running(pid):
                return pid
            else:
                # Stale PID file
                try:
                    os.remove(PID_FILE)
                except Exception:
                    pass
                return None
    except Exception:
        return None


def terminate_pid(pid: int):
    """Force terminate process if it fails to exit gracefully."""
    PROCESS_TERMINATE = 0x0001
    handle = ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE, False, pid)
    if handle:
        ctypes.windll.kernel32.TerminateProcess(handle, 1)
        ctypes.windll.kernel32.CloseHandle(handle)


# =====================================================================
# Commands
# =====================================================================

def cmd_on(args=None):
    """Turn ON LaptopKey."""
    pid = get_current_pid()
    if pid is not None:
        print()
        print("  🟢 LaptopKey is ALREADY RUNNING!")
        print(f"     PID:      {pid}")
        print("     Status:   Broadcasting BLE Keyboard (LaptopKey)")
        print("     To turn OFF: python cli.py off   (or run scripts/switch.bat)")
        print()
        return 0

    # Clean up any leftover stop files
    if os.path.exists(STOP_FILE):
        try:
            os.remove(STOP_FILE)
        except Exception:
            pass

    foreground = getattr(args, "foreground", False)

    if foreground:
        print()
        print("  🟢 Starting LaptopKey in FOREGROUND mode...")
        print("     (Press Ctrl+C or Scroll Lock to exit)")
        print()
        try:
            subprocess.run([sys.executable, MAIN_PY], cwd=ROOT_DIR)
        except KeyboardInterrupt:
            print("\n  Stopped.")
        return 0

    # Background / Daemon mode: use pythonw if available, else python with detached flags
    python_dir = os.path.dirname(sys.executable)
    pythonw = os.path.join(python_dir, "pythonw.exe")
    executable = pythonw if os.path.exists(pythonw) else sys.executable

    # Windows process creation flags for detached background process
    DETACHED_PROCESS = 0x00000008
    CREATE_NEW_PROCESS_GROUP = 0x00000200
    CREATE_NO_WINDOW = 0x08000000

    print()
    print("  ⏳ Starting LaptopKey service in background...")
    try:
        log_f = open(LOG_FILE, "a", encoding="utf-8", errors="replace")
        proc = subprocess.Popen(
            [sys.executable, MAIN_PY],
            cwd=ROOT_DIR,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
            close_fds=True,
            stdout=log_f,
            stderr=log_f,
            stdin=subprocess.DEVNULL,
        )
    except Exception as e:
        print(f"  ❌ Error starting process: {e}")
        return 1

    # Wait up to 3 seconds for PID file confirmation
    confirmed_pid = None
    for _ in range(15):
        time.sleep(0.2)
        confirmed_pid = get_current_pid()
        if confirmed_pid is not None:
            break

    if confirmed_pid is not None:
        print("  ╔════════════════════════════════════════════════════════════════╗")
        print("  ║                   🟢 LAPTOPKEY IS NOW ON                       ║")
        print("  ╠════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Process PID:   {confirmed_pid:<46} ║")
        print("  ║  BLE Broadcast: LaptopKey (Ready to Pair on Phone)            ║")
        print("  ║  Pairing:       Settings -> Bluetooth -> Pair 'LaptopKey'      ║")
        print("  ║  Mute Switch:   Press [F12] anytime to pause/resume forwarding ║")
        print("  ║  Turn OFF:      python cli.py off   (or run scripts/switch.bat)║")
        print("  ╚════════════════════════════════════════════════════════════════╝")
        print()
        return 0
    else:
        # Check if proc exited immediately
        if proc.poll() is not None:
            print(f"  ❌ LaptopKey failed to start. (Exit code: {proc.returncode})")
            print(f"     Check logs with: python cli.py logs")
        else:
            print(f"  ⚠️ Process started (PID: {proc.pid}), waiting for initialization...")
        print()
        return 1


def cmd_off(args=None):
    """Turn OFF LaptopKey cleanly."""
    pid = get_current_pid()
    if pid is None:
        print()
        print("  🔴 LaptopKey is ALREADY OFF (Not running).")
        print()
        return 0

    print()
    print(f"  ⏳ Sending graceful stop signal to LaptopKey (PID: {pid})...")
    
    # Write stop sentinel file
    try:
        with open(STOP_FILE, "w", encoding="utf-8") as f:
            f.write("stop")
    except Exception as e:
        print(f"  ⚠️ Could not write stop sentinel: {e}")

    # Wait up to 3.5 seconds for graceful shutdown
    stopped = False
    for _ in range(18):
        time.sleep(0.2)
        if not is_pid_running(pid):
            stopped = True
            break

    if not stopped:
        print(f"  ⚠️ Process did not exit within timeout. Terminating PID {pid}...")
        terminate_pid(pid)
        time.sleep(0.3)

    # Clean up PID and STOP files
    for path in (PID_FILE, STOP_FILE):
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    print("  ╔════════════════════════════════════════════════════════════════╗")
    print("  ║                   🔴 LAPTOPKEY IS NOW OFF                      ║")
    print("  ╠════════════════════════════════════════════════════════════════╣")
    print("  ║  Status:         STOPPED & DISCONNECTED                        ║")
    print("  ║  BLE Broadcast:  Disabled                                      ║")
    print("  ║  Turn ON:        python cli.py on   (or run scripts/switch.bat)║")
    print("  ╚════════════════════════════════════════════════════════════════╝")
    print()
    return 0


def cmd_switch(args=None):
    """Toggle the ON/OFF switch."""
    interactive = getattr(args, "interactive", False)

    if interactive:
        return _interactive_switch()

    pid = get_current_pid()
    print()
    print("  ================================================================")
    print("                     [ LAPTOPKEY POWER SWITCH ]                  ")
    print("  ================================================================")
    if pid is not None:
        print(f"  Current State:  🟢 ON  (PID: {pid})")
        print("  Action:         Flipping switch to OFF...")
        cmd_off()
    else:
        print("  Current State:  🔴 OFF")
        print("  Action:         Flipping switch to ON...")
        cmd_on()
    return 0


def _interactive_switch():
    """Interactive visual switch dashboard in terminal."""
    print("\nStarting Interactive Switch Dashboard (Press Ctrl+C to exit)...")
    try:
        while True:
            pid = get_current_pid()
            state_str = "🟢 [  ON  ]" if pid is not None else "🔴 [  OFF ]"
            status_text = f"RUNNING (PID: {pid})" if pid is not None else "STOPPED"
            
            os.system("cls" if os.name == "nt" else "clear")
            print()
            print("  ╔══════════════════════════════════════════════════════════════╗")
            print("  ║               LAPTOPKEY INTERACTIVE SWITCH                   ║")
            print("  ╠══════════════════════════════════════════════════════════════╣")
            print(f"  ║   SWITCH:   {state_str}           STATUS: {status_text:<15} ║")
            print("  ╠══════════════════════════════════════════════════════════════╣")
            print("  ║   Options:                                                   ║")
            print("  ║     [1] Flip Switch (Toggle ON / OFF)                        ║")
            print("  ║     [2] View Status & Logs                                   ║")
            print("  ║     [3] Check Bluetooth Adapter                              ║")
            print("  ║     [0] Exit Switch Menu                                     ║")
            print("  ╚══════════════════════════════════════════════════════════════╝")
            print()
            choice = input("  Select option [1, 2, 3, 0] (or press Enter to Toggle): ").strip()
            
            if choice == "0":
                print("  Exiting switch dashboard.")
                break
            elif choice in ("1", ""):
                if pid is not None:
                    cmd_off()
                else:
                    cmd_on()
                time.sleep(1.2)
            elif choice == "2":
                cmd_status()
                input("\n  Press Enter to return to menu...")
            elif choice == "3":
                cmd_check()
                input("\n  Press Enter to return to menu...")
            else:
                pass
    except KeyboardInterrupt:
        print("\n  Exited.")
    return 0


def cmd_status(args=None):
    """Display current system and service status."""
    pid = get_current_pid()
    print()
    print("  ================================================================")
    print("                       LAPTOPKEY STATUS                           ")
    print("  ================================================================")
    if pid is not None:
        print(f"  Service State:   🟢 RUNNING (PID: {pid})")
        print("  Bluetooth Role:  BLE Peripheral Keyboard (HOGP)")
        print("  Advertised Name: LaptopKey")
        print("  Typing Control:  [F12] toggles typing forwarding to phone")
        print("  Stop Switch:     python cli.py off  (or run scripts/switch.bat)")
    else:
        print("  Service State:   🔴 STOPPED (Not running)")
        print("  Start Switch:    python cli.py on   (or run scripts/switch.bat)")

    # Log tail
    if os.path.exists(LOG_FILE):
        try:
            with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()
                print("\n  Recent Logs (Last 5 lines):")
                print("  " + "-" * 60)
                for line in lines[-5:]:
                    print(f"    {line.strip()}")
        except Exception:
            pass
    print("  ================================================================")
    print()
    return 0


def cmd_logs(args=None):
    """View recent logs."""
    lines_count = getattr(args, "lines", 30)
    if not os.path.exists(LOG_FILE):
        print("\n  No log file found yet (laptopkey.log).\n")
        return 0

    print()
    print(f"  Recent Logs ({LOG_FILE}) — Last {lines_count} lines:")
    print("  " + "=" * 64)
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            for line in lines[-lines_count:]:
                print("  " + line.rstrip())
    except Exception as e:
        print(f"  Error reading log file: {e}")
    print("  " + "=" * 64)
    print()
    return 0


def cmd_check(args=None):
    """Verify Bluetooth hardware capabilities for BLE HID."""
    print()
    print("  Checking Bluetooth Adapter & BLE Peripheral Capabilities...")
    print("  " + "-" * 60)

    async def _probe():
        try:
            from winrt.windows.devices.bluetooth import BluetoothAdapter
            adapter = await BluetoothAdapter.get_default_async()
            if adapter is None:
                print("  ❌ No Bluetooth adapter found.")
                return False

            print(f"  ✓ Bluetooth Adapter: Found (Address: {adapter.bluetooth_address:#014x})")
            
            peri = adapter.is_peripheral_role_supported
            print(f"  {'✓' if peri else '❌'} BLE Peripheral Role: {'Supported' if peri else 'Not Supported'}")
            
            offload = adapter.is_advertisement_offload_supported
            print(f"  {'✓' if offload else '⚠️'} BLE Advertisement Offload: {'Supported' if offload else 'Not Supported'}")

            # Check GattServiceProvider for HOGP
            import uuid as _uuid
            from winrt.windows.devices.bluetooth.genericattributeprofile import GattServiceProvider
            hid_uuid = _uuid.UUID("00001812-0000-1000-8000-00805f9b34fb")
            res = await GattServiceProvider.create_async(hid_uuid)
            gatt_ok = res.service_provider is not None
            print(f"  {'✓' if gatt_ok else '❌'} GattServiceProvider HOGP: {'Supported' if gatt_ok else 'Failed'}")
            
            print("  " + "-" * 60)
            if peri and gatt_ok:
                print("  🎉 Your laptop fully supports LaptopKey BLE HID!")
            else:
                print("  ⚠️ Hardware or driver limitations detected.")
            print()
            return True
        except Exception as e:
            print(f"  ❌ Check failed with error: {e}\n")
            return False

    asyncio.run(_probe())
    return 0


def cmd_restart(args=None):
    """Restart LaptopKey."""
    print("\n  Restarting LaptopKey...")
    cmd_off(args)
    time.sleep(1)
    return cmd_on(args)


# =====================================================================
# Main Parser
# =====================================================================

def main():
    parser = argparse.ArgumentParser(
        description="LaptopKey — Turn your laptop keyboard into a wireless Bluetooth keyboard for mobile devices.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py on          Turn ON in background
  python cli.py off         Turn OFF cleanly
  python cli.py switch      Toggle ON/OFF switch
  python cli.py status      View current status
  python cli.py logs        View recent log entries
  python cli.py check       Check Bluetooth adapter
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # on
    parser_on = subparsers.add_parser("on", aliases=["start"], help="Turn ON LaptopKey")
    parser_on.add_argument("-f", "--foreground", action="store_true", help="Run attached in the foreground")

    # off
    subparsers.add_parser("off", aliases=["stop"], help="Turn OFF LaptopKey")

    # switch / toggle
    parser_switch = subparsers.add_parser("switch", aliases=["toggle"], help="Toggle ON/OFF switch")
    parser_switch.add_argument("-i", "--interactive", action="store_true", help="Open interactive switch menu")

    # status
    subparsers.add_parser("status", aliases=["st"], help="Show current service status")

    # logs
    parser_logs = subparsers.add_parser("logs", aliases=["log"], help="Show recent log output")
    parser_logs.add_argument("-n", "--lines", type=int, default=30, help="Number of log lines to show (default: 30)")

    # check
    subparsers.add_parser("check", help="Check Bluetooth hardware compatibility")

    # restart
    subparsers.add_parser("restart", help="Restart LaptopKey")

    args = parser.parse_args()

    command = args.command
    if command in ("on", "start"):
        sys.exit(cmd_on(args))
    elif command in ("off", "stop"):
        sys.exit(cmd_off(args))
    elif command in ("switch", "toggle"):
        sys.exit(cmd_switch(args))
    elif command in ("status", "st"):
        sys.exit(cmd_status(args))
    elif command in ("logs", "log"):
        sys.exit(cmd_logs(args))
    elif command == "check":
        sys.exit(cmd_check(args))
    elif command == "restart":
        sys.exit(cmd_restart(args))
    else:
        # Default with no arguments: show status and quick toggle option
        pid = get_current_pid()
        state = "🟢 ON (Running)" if pid is not None else "🔴 OFF (Stopped)"
        print()
        print("  ================================================================")
        print("                        LAPTOPKEY CLI                           ")
        print("  ================================================================")
        print(f"  Current Switch State: {state}")
        print()
        print("  Available Commands:")
        print("    python cli.py switch       <-- Flip the ON / OFF switch")
        print("    python cli.py on           <-- Turn ON")
        print("    python cli.py off          <-- Turn OFF")
        print("    python cli.py status       <-- View detailed status")
        print("    python cli.py logs         <-- View recent logs")
        print("    python cli.py check        <-- Check Bluetooth hardware")
        print("  ================================================================")
        print()
        sys.exit(0)


if __name__ == "__main__":
    main()
