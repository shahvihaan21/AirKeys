# Architecture and data flow

AirKeys is a Windows-only experimental BLE HID-over-GATT (HOGP) keyboard. It is not a Bluetooth Classic HID implementation.

```mermaid
flowchart LR
  K[Physical laptop keyboard] --> P[pynput listener]
  P --> M[pynput_key_to_scancode]
  M --> R[HidReportBuilder]
  R --> Q[main.py async send queue]
  Q --> B[BleHidService]
  B --> G[Windows WinRT GATT server]
  G --> H[Paired host subscribed to Input Report]
  H --> A[Host keyboard layout / focused app]
```

`src/main.py` owns the application lifecycle and keyboard listener. `src/hid_report.py` maps supported `pynput` events to USB HID Usage Page 0x07 and builds the report. `src/ble_hid_service.py` owns the local GATT services and sends notifications. `cli.py` starts and stops the background process using PID and stop-sentinel files.

## Startup and shutdown

```mermaid
sequenceDiagram
  participant C as cli.py
  participant M as main.py
  participant B as BleHidService
  participant W as Windows BLE stack
  participant H as HID host
  C->>M: start background process
  M->>B: start()
  B->>W: check peripheral role; create GATT services
  B->>W: advertise HID and optional Battery services
  H->>W: pair and subscribe to Input Report
  W-->>B: subscribed-clients change
  M->>B: notify 8-byte reports while subscribed
  C->>M: stop sentinel, or user presses Scroll Lock
  M->>B: all-keys-released report; stop()
  B->>W: stop advertising
```

Notifications are only attempted when the Input Report characteristic has subscribers. A failed send or a subscriber-loss callback clears the local pressed-key state; the next successful connection does not inherit that state.

## GATT surface

| Service | Characteristic | Direction | Current behavior |
|---|---|---|---|
| HID `0x1812` | HID Information `0x2A4A` | read | Static HID 1.11 information |
| HID `0x1812` | Report Map `0x2A4B` | read | One boot-style keyboard report map |
| HID `0x1812` | HID Control Point `0x2A4C` | write without response | Exposed; application does not interpret writes |
| HID `0x1812` | Protocol Mode `0x2A4E` | read/write without response | Exposed with static Report Protocol value; writes are not interpreted |
| HID `0x1812` | Input Report `0x2A4D` | read/notify | Sends 8-byte keyboard reports with Report Reference `(0, Input)` |
| Battery `0x180F` | Battery Level `0x2A19` | read/notify | Best-effort optional service, static `100` |

The HID service is required for startup. Battery-service creation failure is logged and does not stop the HID service.

