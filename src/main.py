"""
main.py — AirKeys: Turn your laptop keyboard into a Bluetooth keyboard for mobile devices

Orchestrates:
  1. BLE HID service (ble_hid_service.py)
  2. Local keyboard capture (pynput)
  3. HID report generation (hid_report.py)
  4. Runtime state & PID management

Hotkeys:
  - F12: Switch typing forwarding ON / OFF (passthrough to laptop)
  - Scroll Lock: Clean shutdown & disconnect
"""
import asyncio
import logging
import os
import signal
import sys
import threading

# Ensure Windows console handles UTF-8 / emojis gracefully
if sys.platform == "win32":
    if sys.stdout is not None:
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    if sys.stderr is not None:
        try:
            sys.stderr.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

# Ensure local package imports work regardless of working directory
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pynput import keyboard as kb

from hid_report import HidReportBuilder, pynput_key_to_scancode
from ble_hid_service import BleHidService

# ---- Configuration ----
PID_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".airkeys.pid"))
LEGACY_PID_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".laptopkey.pid"))
STOP_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".airkeys.stop"))
LEGACY_STOP_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".laptopkey.stop"))
LOG_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "airkeys.log"))

# ---- Logging ----
file_handler = logging.FileHandler(LOG_FILE, mode="a", encoding="utf-8")
file_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))

log = logging.getLogger("airkeys")
log.setLevel(logging.INFO)
log.addHandler(file_handler)

if sys.stdout is not None:
    try:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", datefmt="%H:%M:%S"))
        log.addHandler(console_handler)
    except Exception:
        pass

# ---- State Globals ----
_report_builder = HidReportBuilder()
_ble_service: BleHidService | None = None
_loop: asyncio.AbstractEventLoop | None = None
_exit_event = threading.Event()
_is_forwarding_enabled = True  # Can be toggled on/off with F12


def _schedule_send(report: bytes):
    """Thread-safe: schedule send_report on the asyncio event loop."""
    if _loop is None or _ble_service is None or _loop.is_closed():
        return
    asyncio.run_coroutine_threadsafe(_ble_service.send_report(report), _loop)


def _toggle_forwarding():
    """Toggle forwarding between Laptop and Phone without disconnecting BLE."""
    global _is_forwarding_enabled
    _is_forwarding_enabled = not _is_forwarding_enabled
    if _is_forwarding_enabled:
        log.info("▶ FORWARDING ON: Keystrokes are now sent to Phone (Press F12 to mute)")
    else:
        # Release all active keys on phone so nothing gets stuck
        _schedule_send(_report_builder.release_all())
        log.info("⏸ FORWARDING MUTED: Keystrokes stay on Laptop (Press F12 to resume)")


def _on_key_press(key):
    """pynput callback — runs in listener thread."""
    # F12 toggles forwarding switch
    if key == kb.Key.f12:
        _toggle_forwarding()
        return

    # If forwarding is muted, ignore keystrokes
    if not _is_forwarding_enabled:
        return

    mod_bit, scancode = pynput_key_to_scancode(key)
    if mod_bit is not None:
        report = _report_builder.press_modifier(mod_bit)
    elif scancode is not None:
        report = _report_builder.press_key(scancode)
    else:
        return  # unmapped key
    _schedule_send(report)


def _on_key_release(key):
    """pynput callback — runs in listener thread."""
    # Scroll Lock triggers clean exit
    if key == kb.Key.scroll_lock:
        log.info("Scroll Lock pressed — shutting down.")
        _exit_event.set()
        return False  # stop listener

    if key == kb.Key.f12:
        return

    if not _is_forwarding_enabled:
        return

    mod_bit, scancode = pynput_key_to_scancode(key)
    if mod_bit is not None:
        report = _report_builder.release_modifier(mod_bit)
    elif scancode is not None:
        report = _report_builder.release_key(scancode)
    else:
        return  # unmapped key
    _schedule_send(report)


def _write_pid():
    """Write current process PID to file for CLI management."""
    pid_str = str(os.getpid())
    for path in (PID_FILE, LEGACY_PID_FILE):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(pid_str)
        except Exception as e:
            log.warning(f"Could not write PID file ({path}): {e}")


def _remove_pid():
    """Remove PID files on clean exit."""
    for path in (PID_FILE, LEGACY_PID_FILE):
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception:
            pass


async def _main():
    global _ble_service, _loop
    _loop = asyncio.get_running_loop()

    # Callback when phone connects/subscribes
    def on_subscriber_change(has_sub: bool):
        if has_sub:
            log.info("✓ Phone CONNECTED & SUBSCRIBED! Keyboard is live.")
        else:
            log.info("Phone disconnected or unsubscribed.")

    _ble_service = BleHidService(on_subscriber_change=on_subscriber_change)
    try:
        await _ble_service.start()
    except Exception as e:
        log.error(f"Failed to start BLE HID service: {e}")
        _remove_pid()
        return 1

    # Do not claim the service is running until Bluetooth advertising is ready.
    _write_pid()

    if sys.stdout is not None:
        try:
            print()
            print("=" * 64)
            print("   AirKeys — BLE HID Keyboard Active")
            print("=" * 64)
            print("   Status:        🟢 ADVERTISING (Waiting for Phone)")
            print("   Pairing:       Open phone Bluetooth -> Pair 'AirKeys' or PC name")
            print("   On/Off Switch: Press [F12] anytime to MUTE / UNMUTE forwarding")
            print("   Exit Switch:   Press [Scroll Lock] or Ctrl+C to stop")
            print("=" * 64)
            print()
        except Exception:
            pass

    # Start keyboard listener
    listener = kb.Listener(on_press=_on_key_press, on_release=_on_key_release)
    listener.start()

    # Graceful signal handler
    def _handle_signal(signum, frame):
        log.info(f"Signal {signum} received — triggering graceful shutdown.")
        _exit_event.set()

    try:
        signal.signal(signal.SIGINT, _handle_signal)
        signal.signal(signal.SIGTERM, _handle_signal)
    except Exception:
        pass

    try:
        while not _exit_event.is_set():
            if os.path.exists(STOP_FILE) or os.path.exists(LEGACY_STOP_FILE):
                log.info("Stop sentinel detected from CLI — stopping service.")
                break
            await asyncio.sleep(0.2)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        listener.stop()
        if _ble_service:
            try:
                await _ble_service.send_report(_report_builder.release_all())
                await _ble_service.stop()
            except Exception as e:
                log.warning(f"Error during BLE shutdown: {e}")
        _remove_pid()
        for s_path in (STOP_FILE, LEGACY_STOP_FILE):
            if os.path.exists(s_path):
                try:
                    os.remove(s_path)
                except Exception:
                    pass
        log.info("AirKeys stopped successfully.")


if __name__ == "__main__":
    try:
        sys.exit(asyncio.run(_main()) or 0)
    except KeyboardInterrupt:
        _remove_pid()
        print("\nExiting...")
