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
import json
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

from hid_report import (
    HidReportBuilder,
    pynput_key_to_scancode,
    build_shortcut_reports,
    parse_shortcut,
    text_to_hid_reports,
)
from ble_hid_service import BleHidService

# ---- Configuration ----
PID_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".airkeys.pid"))
LEGACY_PID_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".laptopkey.pid"))
STOP_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".airkeys.stop"))
LEGACY_STOP_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".laptopkey.stop"))
CMD_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".airkeys.cmd"))
LEGACY_CMD_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".laptopkey.cmd"))
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
_report_lock = threading.RLock()
_pending_sends = set()


def _schedule_send(report: bytes):
    """Queue a report and surface asynchronous failures instead of losing them."""
    if _loop is None or _ble_service is None or _loop.is_closed():
        log.warning("Dropped HID report because the BLE event loop is unavailable.")
        return
    future = asyncio.run_coroutine_threadsafe(_ble_service.send_report(report), _loop)
    _pending_sends.add(future)

    def _completed(done):
        _pending_sends.discard(done)
        try:
            sent = done.result()
            if not sent and _ble_service and _ble_service.has_subscribers:
                log.warning("HID report was not delivered; clearing pressed-key state.")
                with _report_lock:
                    _report_builder.release_all()
        except Exception:
            log.exception("HID report task failed.")
            with _report_lock:
                _report_builder.release_all()

    future.add_done_callback(_completed)


def _toggle_forwarding():
    """Toggle forwarding between Laptop and Phone without disconnecting BLE."""
    global _is_forwarding_enabled
    _is_forwarding_enabled = not _is_forwarding_enabled
    if _is_forwarding_enabled:
        log.info("▶ FORWARDING ON: Keystrokes are now sent to Phone (Press F12 to mute)")
    else:
        # Release all active keys on phone so nothing gets stuck
        with _report_lock:
            _schedule_send(_report_builder.release_all())
        log.info("⏸ FORWARDING MUTED: Keystrokes stay on Laptop (Press F12 to resume)")


async def _send_shortcut_coro(shortcut: str, hold_duration: float = 0.05) -> bool:
    """Send shortcut combo asynchronously over BLE."""
    if _ble_service is None or not _is_forwarding_enabled:
        log.warning(f"Cannot send shortcut '{shortcut}': BLE service not active or forwarding muted.")
        return False
    try:
        press_report, release_report = build_shortcut_reports(shortcut)
        with _report_lock:
            sent = await _ble_service.send_report(press_report)
        if sent:
            await asyncio.sleep(hold_duration)
            with _report_lock:
                await _ble_service.send_report(release_report)
            log.info(f"✓ Sent shortcut over BLE: {shortcut}")
            return True
        else:
            log.warning(f"Could not send shortcut '{shortcut}': no connected/subscribed device.")
            with _report_lock:
                _report_builder.release_all()
            return False
    except Exception as e:
        log.error(f"Error sending shortcut '{shortcut}': {e}")
        with _report_lock:
            _report_builder.release_all()
        return False


def send_shortcut(shortcut: str, hold_duration: float = 0.05) -> bool:
    """
    Send a shortcut combo (e.g. 'ctrl+c', 'ctrl+v', 'copy', 'paste') over BLE.
    If the BLE event loop is running in this process, dispatches directly.
    Otherwise, queues it via CMD_FILE for the background AirKeys process.
    """
    if _loop is not None and not _loop.is_closed() and _ble_service is not None:
        future = asyncio.run_coroutine_threadsafe(
            _send_shortcut_coro(shortcut, hold_duration), _loop
        )
        try:
            return future.result(timeout=2.0)
        except Exception as e:
            log.error(f"Failed waiting for shortcut '{shortcut}': {e}")
            return False
    else:
        return queue_shortcut_cmd(shortcut)


def queue_shortcut_cmd(shortcut: str) -> bool:
    """Queue a shortcut command into CMD_FILE for the running AirKeys process."""
    try:
        parse_shortcut(shortcut)  # validate syntax first
        with open(CMD_FILE, "a", encoding="utf-8") as f:
            f.write(f"shortcut:{shortcut}\n")
        return True
    except Exception as e:
        log.error(f"Could not queue shortcut command: {e}")
        return False


async def _send_text_coro(text: str, key_delay: float = 0.015) -> int:
    """Send text string over BLE HID."""
    if _ble_service is None or not _is_forwarding_enabled:
        log.warning("Cannot send text: BLE service not active or forwarding muted.")
        return 0
    try:
        pairs = text_to_hid_reports(text)
        if not pairs:
            log.warning("No mappable characters found in text.")
            return 0
        count = 0
        for press_report, release_report in pairs:
            with _report_lock:
                sent = await _ble_service.send_report(press_report)
            if not sent:
                log.warning(f"Could not send character {count + 1}/{len(pairs)}: no connected/subscribed device.")
                with _report_lock:
                    _report_builder.release_all()
                break
            if key_delay > 0:
                await asyncio.sleep(key_delay)
            with _report_lock:
                await _ble_service.send_report(release_report)
            if key_delay > 0:
                await asyncio.sleep(key_delay)
            count += 1
        log.info(f"✓ Sent {count}/{len(pairs)} characters over BLE.")
        return count
    except Exception as e:
        log.error(f"Error sending text: {e}")
        with _report_lock:
            _report_builder.release_all()
        return 0


def send_text(text: str, key_delay: float = 0.015) -> int:
    """
    Send text over BLE.
    If the BLE event loop is running in this process, dispatches directly.
    Otherwise, queues it via CMD_FILE for the background AirKeys process.
    """
    if _loop is not None and not _loop.is_closed() and _ble_service is not None:
        future = asyncio.run_coroutine_threadsafe(
            _send_text_coro(text, key_delay), _loop
        )
        try:
            return future.result(timeout=10.0)
        except Exception as e:
            log.error(f"Failed waiting for text sending: {e}")
            return 0
    else:
        return 1 if queue_text_cmd(text) else 0


def queue_text_cmd(text: str) -> bool:
    """Queue a text typing command into CMD_FILE for the running AirKeys process."""
    try:
        payload = json.dumps(text)
        with open(CMD_FILE, "a", encoding="utf-8") as f:
            f.write(f"text:{payload}\n")
        return True
    except Exception as e:
        log.error(f"Could not queue text command: {e}")
        return False



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
    if scancode is None and mod_bit is None:
        return  # unmapped key
    with _report_lock:
        if scancode is None:
            report = _report_builder.press_modifier(mod_bit)
        else:
            report = _report_builder.press_key(scancode, mod_bit or 0)
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
    if scancode is None and mod_bit is None:
        return  # unmapped key
    with _report_lock:
        if scancode is None:
            report = _report_builder.release_modifier(mod_bit)
        else:
            report = _report_builder.release_key(scancode)
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
            with _report_lock:
                _report_builder.release_all()

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

            # Check for queued commands (e.g. shortcuts)
            for c_path in (CMD_FILE, LEGACY_CMD_FILE):
                if os.path.exists(c_path):
                    proc_path = c_path + ".proc"
                    try:
                        os.replace(c_path, proc_path)
                        with open(proc_path, "r", encoding="utf-8") as f:
                            lines = [line.strip() for line in f if line.strip()]
                        try:
                            os.remove(proc_path)
                        except Exception:
                            pass
                        for line in lines:
                            if line.startswith("shortcut:"):
                                shortcut_str = line[len("shortcut:"):].strip()
                                asyncio.create_task(_send_shortcut_coro(shortcut_str))
                            elif line.startswith("text:"):
                                raw_payload = line[len("text:"):].strip()
                                try:
                                    text_str = json.loads(raw_payload)
                                    if not isinstance(text_str, str):
                                        text_str = str(text_str)
                                except Exception:
                                    text_str = raw_payload
                                asyncio.create_task(_send_text_coro(text_str))
                    except Exception as e:
                        log.warning(f"Error handling cmd file ({c_path}): {e}")

            await asyncio.sleep(0.1)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        listener.stop()
        if _ble_service:
            try:
                with _report_lock:
                    release_report = _report_builder.release_all()
                await _ble_service.send_report(release_report)
                await _ble_service.stop()
            except Exception as e:
                log.warning(f"Error during BLE shutdown: {e}")
        _remove_pid()
        for s_path in (STOP_FILE, LEGACY_STOP_FILE, CMD_FILE, LEGACY_CMD_FILE):
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
