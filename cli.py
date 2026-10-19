#!/usr/bin/env python3
"""
cli.py — AirKeys Master CLI & On/Off Switch

Commands:
  python cli.py on          Turn ON AirKeys in background
  python cli.py off         Turn OFF AirKeys cleanly
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
import importlib.util
import os
import platform
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
PID_FILE = os.path.join(ROOT_DIR, ".airkeys.pid")
LEGACY_PID_FILE = os.path.join(ROOT_DIR, ".laptopkey.pid")
STOP_FILE = os.path.join(ROOT_DIR, ".airkeys.stop")
LEGACY_STOP_FILE = os.path.join(ROOT_DIR, ".laptopkey.stop")
LOG_FILE = os.path.join(ROOT_DIR, "airkeys.log")
LEGACY_LOG_FILE = os.path.join(ROOT_DIR, "laptopkey.log")


def environment_problems() -> list[str]:
    """Return actionable prerequisites that prevent AirKeys from starting."""
    problems = []
    if sys.platform != "win32":
        problems.append("AirKeys requires Windows 10/11; this operating system is unsupported.")
    if sys.version_info < (3, 10):
        problems.append(f"Python 3.10 or newer is required (found {platform.python_version()}).")

    required_modules = {
        "pynput": "pynput",
        "winrt.windows.devices.bluetooth": "winrt-Windows.Devices.Bluetooth",
        "winrt.windows.devices.bluetooth.genericattributeprofile": (
            "winrt-Windows.Devices.Bluetooth.GenericAttributeProfile"
        ),
        "winrt.windows.storage.streams": "winrt-Windows.Storage.Streams",
    }
    for module, package in required_modules.items():
        if importlib.util.find_spec(module) is None:
            problems.append(f"Missing dependency: {package}. Run setup.bat or pip install -r requirements.txt.")
    return problems


def print_environment_problems(problems: list[str]) -> None:
    print("\n  AirKeys cannot start until these setup issues are fixed:")
    for problem in problems:
        print(f"  - {problem}")
    print("  Run setup.bat from the project folder, then run: python cli.py check\n")


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
    """Read PID from PID_FILE (or fallback LEGACY_PID_FILE) if process is alive."""
    for path in (PID_FILE, LEGACY_PID_FILE):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = f.read().strip()
                if not content:
                    continue
                pid = int(content)
                if is_pid_running(pid):
                    return pid
                else:
                    # Stale PID file
                    try:
                        os.remove(path)
                    except Exception:
                        pass
        except Exception:
            pass
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
    """Turn ON AirKeys."""
    problems = environment_problems()
    if problems:
        print_environment_problems(problems)
        return 2

    pid = get_current_pid()
    if pid is not None:
        print()
        print("  🟢 AirKeys is ALREADY RUNNING!")
        print(f"     PID:      {pid}")
        print("     Status:   Broadcasting BLE Keyboard (AirKeys)")
        print("     To turn OFF: python cli.py off   (or run scripts/switch.bat)")
        print()
        return 0

    # Clean up any leftover stop files
    for s_path in (STOP_FILE, LEGACY_STOP_FILE):
        if os.path.exists(s_path):
            try:
                os.remove(s_path)
            except Exception:
                pass

    foreground = getattr(args, "foreground", False)

    if foreground:
        print()
        print("  🟢 Starting AirKeys in FOREGROUND mode...")
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
    print("  ⏳ Starting AirKeys service in background...")
    try:
        log_f = open(LOG_FILE, "a", encoding="utf-8", errors="replace")
        proc = subprocess.Popen(
            [executable, MAIN_PY],
            cwd=ROOT_DIR,
            creationflags=DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP | CREATE_NO_WINDOW,
            close_fds=True,
            stdout=log_f,
            stderr=log_f,
            stdin=subprocess.DEVNULL,
        )
        log_f.close()
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
        machine_name = platform.node()
        print("  ╔════════════════════════════════════════════════════════════════╗")
        print("  ║                   🟢 AIRKEYS IS NOW ON                         ║")
        print("  ╠════════════════════════════════════════════════════════════════╣")
        print(f"  ║  Process PID:   {confirmed_pid:<46} ║")
        print(f"  ║  BLE Broadcast: AirKeys / {machine_name:<34} ║")
        print("  ║  Pairing:       Settings -> Bluetooth -> Pair 'AirKeys' / PC   ║")
        print("  ║  Mute Switch:   Press [F12] anytime to pause/resume forwarding ║")
        print("  ║  Turn OFF:      python cli.py off   (or run scripts/switch.bat)║")
        print("  ╚════════════════════════════════════════════════════════════════╝")
        print()
        return 0
    else:
        # Check if proc exited immediately
        if proc.poll() is not None:
            print(f"  ❌ AirKeys failed to start. (Exit code: {proc.returncode})")
            print(f"     Check logs with: python cli.py logs")
        else:
            print(f"  ⚠️ Process started (PID: {proc.pid}), waiting for initialization...")
        print()
        return 1


def cmd_off(args=None):
    """Turn OFF AirKeys cleanly."""
    pid = get_current_pid()
    if pid is None:
        print()
        print("  🔴 AirKeys is ALREADY OFF (Not running).")
        print()
        return 0

    print()
    print(f"  ⏳ Sending graceful stop signal to AirKeys (PID: {pid})...")
    
    # Write stop sentinel files
    for s_path in (STOP_FILE, LEGACY_STOP_FILE):
        try:
            with open(s_path, "w", encoding="utf-8") as f:
                f.write("stop")
        except Exception as e:
            print(f"  ⚠️ Could not write stop sentinel ({s_path}): {e}")

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
    for path in (PID_FILE, LEGACY_PID_FILE, STOP_FILE, LEGACY_STOP_FILE):
        if os.path.exists(path):
            try:
                os.remove(path)
            except Exception:
                pass

    print("  ╔════════════════════════════════════════════════════════════════╗")
    print("  ║                   🔴 AIRKEYS IS NOW OFF                        ║")
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
    print("                      [ AIRKEYS POWER SWITCH ]                   ")
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
            print("  ║                AIRKEYS INTERACTIVE SWITCH                    ║")
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
    machine_name = platform.node()
    print()
    print("  ================================================================")
    print("                        AIRKEYS STATUS                            ")
    print("  ================================================================")
    if pid is not None:
        print(f"  Service State:   🟢 RUNNING (PID: {pid})")
        print("  Bluetooth Role:  BLE Peripheral Keyboard (HOGP)")
        print(f"  Advertised Name: AirKeys / {machine_name}")
        print("  Typing Control:  [F12] toggles typing forwarding to phone")
        print("  Stop Switch:     python cli.py off  (or run scripts/switch.bat)")
    else:
        print("  Service State:   🔴 STOPPED (Not running)")
        print("  Start Switch:    python cli.py on   (or run scripts/switch.bat)")

    # Log tail (check current log file, or fallback to legacy)
    active_log = LOG_FILE if os.path.exists(LOG_FILE) else (LEGACY_LOG_FILE if os.path.exists(LEGACY_LOG_FILE) else None)
    if active_log:
        try:
            with open(active_log, "r", encoding="utf-8", errors="replace") as f:
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
    active_log = LOG_FILE if os.path.exists(LOG_FILE) else (LEGACY_LOG_FILE if os.path.exists(LEGACY_LOG_FILE) else None)
    if not active_log:
        print("\n  No log file found yet (airkeys.log).\n")
        return 0

    print()
    print(f"  Recent Logs ({active_log}) — Last {lines_count} lines:")
    print("  " + "=" * 64)
    try:
        with open(active_log, "r", encoding="utf-8", errors="replace") as f:
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

    problems = environment_problems()
    if problems:
        print_environment_problems(problems)
        return 2

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
                print("  🎉 Your laptop fully supports AirKeys BLE HID!")
            else:
                print("  ⚠️ Hardware or driver limitations detected.")
            print()
            return True
        except Exception as e:
            print(f"  ❌ Check failed with error: {e}\n")
            return False

    return 0 if asyncio.run(_probe()) else 1


def cmd_restart(args=None):
    """Restart AirKeys."""
    print("\n  Restarting AirKeys...")
    cmd_off(args)
    time.sleep(1)
    return cmd_on(args)


# =====================================================================
# Main Parser
# =====================================================================

def main():
    parser = argparse.ArgumentParser(
        description="AirKeys — Turn your laptop keyboard into a wireless Bluetooth keyboard for mobile devices.",
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
    parser_on = subparsers.add_parser("on", aliases=["start"], help="Turn ON AirKeys")
    parser_on.add_argument("-f", "--foreground", action="store_true", help="Run attached in the foreground")

    # off
    subparsers.add_parser("off", aliases=["stop"], help="Turn OFF AirKeys")

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
    subparsers.add_parser("restart", help="Restart AirKeys")

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
        print("                         AIRKEYS CLI                            ")
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
