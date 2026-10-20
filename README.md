# AirKeys

AirKeys is an experimental Windows application that presents a laptop as a Bluetooth Low Energy (BLE) keyboard for a compatible receiving device. It captures supported laptop key events, converts them to HID keyboard reports, and publishes them through a local HID-over-GATT (HOGP) service.

> **Prototype status:** The software path is implemented and unit tested, but Bluetooth discovery, pairing, subscription, input delivery, and reconnection remain dependent on the specific Windows adapter, driver, and receiving device. There is no current demonstration recording or compatibility certification in this repository.

## What it does

- Runs a BLE HID-over-GATT keyboard service on Windows.
- Captures supported keyboard events using `pynput` and sends standard eight-byte HID reports to subscribed hosts.
- Provides command-line and batch-script controls to start, stop, inspect, and diagnose the service.
- Requests authenticated and encrypted access for HID GATT characteristics.

## What it does not do

- It does not implement Bluetooth Classic HID.
- It does not guarantee compatibility with Android, iOS, desktops, TVs, or every Bluetooth adapter.
- It does not handle arbitrary Unicode text, consumer/media keys, mouse input, keyboard LEDs, or host output reports.
- It does not maintain its own bonded-device allowlist or reconnection policy; those responsibilities belong to Windows and the receiving host.

## Requirements

- Windows 10 (version 1703 or later) or Windows 11
- Python 3.10 or later
- A Bluetooth adapter and driver that support the BLE peripheral role
- A receiving device that supports BLE HID keyboards

Run the capability check before attempting to pair. Both the peripheral-role and GATT HID-service checks must succeed:

```powershell
python cli.py check
```

Installing dependencies cannot add BLE peripheral support to an unsupported adapter or driver.

## Install

From the repository root, either run `setup.bat` or create a virtual environment and install the dependencies manually:

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python cli.py check
```

## Use

```powershell
python cli.py on
python cli.py status
python cli.py off
```

| Command | Purpose |
|---|---|
| `python cli.py on` | Starts AirKeys in the background. Add `--foreground` to run it in the current console. |
| `python cli.py off` | Requests a graceful shutdown. |
| `python cli.py switch` | Toggles the background service. |
| `python cli.py status` | Shows process and service status. |
| `python cli.py check` | Checks dependencies, adapter capability, and local HID service creation. |
| `python cli.py logs` | Prints recent diagnostic logs. |
| `python cli.py restart` | Restarts the service. |

Windows shortcuts for the common actions are available in `scripts/`.

### Pair a receiving device

1. Start AirKeys and confirm `python cli.py check` has passed on that machine.
2. Open the receiving device's Bluetooth settings and scan for devices.
3. Pair with the local service as it is presented by Windows. The display name is controlled by Windows and may not be `AirKeys`.
4. Focus a text field on the receiving device and test input.

Pairing alone does not confirm that HID input is working. Use the real-device checks below before describing a device as compatible.

## Architecture

```mermaid
flowchart LR
  K[Physical laptop keyboard] --> P[pynput listener]
  P --> M[pynput_key_to_scancode]
  M --> R[HidReportBuilder]
  R --> Q[main.py async send queue]
  Q --> B[BleHidService]
  B --> G[Windows WinRT GATT server]
  G --> H[Paired host subscribed to Input Report]
  H --> A[Host keyboard layout and focused app]
```

| Component | Responsibility |
|---|---|
| `cli.py` | Checks prerequisites; starts, stops, monitors, and tails the service. |
| `src/main.py` | Coordinates keyboard capture, forwarding state, report state, PID files, signals, and shutdown. |
| `src/hid_report.py` | Defines HID usages, modifier bits, the report map, and the report builder. |
| `src/ble_hid_service.py` | Creates local GATT services, advertises them, tracks subscribers, and serializes notifications. |
| `tests/` | Unit tests and mocked BLE lifecycle tests; no physical-device tests. |

### Data flow and lifecycle

```mermaid
sequenceDiagram
  participant C as cli.py
  participant M as main.py
  participant B as BleHidService
  participant W as Windows BLE stack
  participant H as HID host
  C->>M: start process
  M->>B: start()
  B->>W: verify adapter; create and advertise GATT services
  H->>W: pair and subscribe to Input Report
  W-->>B: subscriber change
  M->>B: send 8-byte HID notifications
  C->>M: stop sentinel, or user presses Scroll Lock
  M->>B: release all keys; stop advertising
```

The required HID service (`0x1812`) exposes HID Information, Report Map, Control Point, Protocol Mode, and a notifying Input Report (`0x2A4D`) with an Input Report Reference. The application also tries to expose an optional Battery service (`0x180F`) with a static 100% value. Battery-service failure is non-fatal; HID-service creation failure prevents startup.

## Keyboard behavior

AirKeys sends one eight-byte report with no report ID:

```text
byte 0       modifier bitmap
byte 1       reserved (0x00)
bytes 2..7   up to six USB HID keyboard usages
```

Supported input includes ASCII letters, digits, US punctuation, shifted US punctuation, common editing/navigation keys, function keys, and Ctrl/Shift/Alt/GUI modifiers. HID represents physical key positions, so the receiving device's active keyboard layout determines the displayed character. Unsupported and non-ASCII characters are ignored.

Physical modifiers remain active until their release event. Uppercase letters and shifted punctuation add a temporary Shift bit for the press report. The builder tracks at most six non-modifier keys; pressing a seventh removes the oldest tracked key.

| Control | Behavior |
|---|---|
| `F12` | Toggles forwarding. Muting sends a release-all report first. |
| `Scroll Lock` | Stops the listener and begins clean shutdown. |
| `Ctrl+C` / `python cli.py off` | Requests clean shutdown. |

AirKeys does not suppress normal laptop input; the local operating system may receive the same key events.

## Security and reliability

AirKeys captures global keyboard events while active. Use it only with a trusted paired device and stop it when it is not needed. HID characteristics request Windows authenticated encryption, and reports are notified only when an Input Report client is subscribed.

Windows and the receiving host enforce pairing, encryption, and bond management. AirKeys has no application-level peer allowlist, bond store, peer-identity callback, or per-notification authorization step. Do not use this prototype for passwords, recovery phrases, payment information, or other sensitive text until you have validated its behavior on the exact devices involved.

Notification sends are serialized. Failed sends and subscription loss clear AirKeys' in-memory pressed-key state. Normal shutdown attempts to send a release-all report, stop capture, stop advertising, and remove runtime state files. A crash, power loss, or forced termination can prevent the final release report; test for stuck keys after such events.

## Compatibility and troubleshooting

| Platform / requirement | Status |
|---|---|
| Windows 10/11 with Python 3.10+ | Required |
| BLE peripheral role and local HID service creation | Required; verify with `python cli.py check` |
| Android BLE HID host | Candidate; device-specific and not certified |
| iOS/iPadOS or desktop host | Unverified |
| Bluetooth Classic-only host | Unsupported |

| Symptom | Recommended action |
|---|---|
| No adapter or peripheral-role support | Enable Bluetooth, update the adapter driver, or use an adapter supported by Windows for BLE peripheral mode. |
| Service exits or is not discoverable | Run `python cli.py logs`, then resolve dependency or HID-service creation errors. |
| Pairing succeeds but there is no input | Check logs for a subscriber change and run the key tests below. Pairing is not proof of input delivery. |
| Unexpected characters | Test with a US-oriented keyboard layout on the receiving host; HID sends usages, not Unicode. |
| A key appears stuck | Disconnect/reconnect, restart AirKeys, and record the held key and timing with sanitized logs. |
| `off` forces termination | Check logs. The final release report may not have been sent. |

## Verification

Run the automated tests from the repository root:

```powershell
python -m unittest discover tests
```

The tests cover HID report construction and mappings, CLI helper behavior, and a mocked BLE-service lifecycle. They do not exercise a real Windows radio, advertising, pairing, or host interoperability.

For a real-device result, record the Windows build, Python version, Bluetooth adapter and driver, receiving device and OS, and `python cli.py check` output. Then verify:

1. Discovery and OS pairing.
2. Lowercase/uppercase ASCII, digits, shifted punctuation, arrows, Backspace, Tab, and Enter.
3. Ctrl, Alt, and Shift combinations.
4. F12 mute/unmute and Scroll Lock shutdown.
5. Disconnect while a key is held, reconnect, and confirm no key remains stuck.
6. Stop, restart, reconnect, and retest input.

No demonstration video or screenshot is currently committed. A valid future demonstration should continuously show the capability check, pairing, typing in a visible text field, F12 mute/unmute, and clean shutdown, with sensitive data removed.

## Development and contributions

Before a substantial change, open an issue with the Windows build, Python version, Bluetooth adapter/driver, receiving-device model/OS, capability-check output, and sanitized logs. Keep claims aligned with observed evidence, add focused tests, and run the full test suite. Do not commit credentials, pairing identifiers, personal input, or unredacted logs.

### Roadmap

1. Publish repeatable, redacted real-device evidence and record both successful and failed compatibility results.
2. Add hardware-in-the-loop tests for pairing, notification delivery, reconnect, and stuck-key recovery.
3. Improve reconnection, host-state handling, and layout/special-key support only with corresponding tests.

## Project layout

```text
AirKeys/
├── scripts/                 # Windows command shortcuts
├── src/
│   ├── main.py              # Runtime and keyboard capture
│   ├── hid_report.py        # HID report format and key mapping
│   └── ble_hid_service.py   # WinRT BLE HOGP service
├── tests/                   # Unit and mocked BLE lifecycle tests
├── cli.py                   # Service control CLI
├── requirements.txt         # Python dependencies
├── setup.bat                # Windows setup helper
└── README.md                # Project documentation
```
