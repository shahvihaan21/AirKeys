# Components and key reports

| Component | Responsibility |
|---|---|
| `cli.py` | Checks prerequisites; launches, monitors, stops, and tails the background process. |
| `src/main.py` | Coordinates BLE, global key capture, forwarding mode, report state, PID files, signals, and shutdown. |
| `src/hid_report.py` | Defines the HID report descriptor, supported usages, modifier bits, and stateful report builder. |
| `src/ble_hid_service.py` | Creates protected local GATT services, advertises, tracks subscribers, and serializes notifications. |
| `tests/` | Unit and mocked-lifecycle regression checks; no physical Bluetooth device tests. |

## Report behavior

The one report format has no report ID and is exactly eight bytes:

```text
byte 0       modifier bitmap
byte 1       reserved (0x00)
bytes 2..7   up to six simultaneous USB HID keyboard usages
```

Physical Ctrl, Shift, Alt, and GUI events persist in the modifier bitmap until their release event. Uppercase ASCII and shifted US punctuation add a temporary left-Shift bit to their press report, then return to the physical modifier state on release. The builder keeps up to six non-modifier usages; a seventh newly pressed usage evicts the oldest tracked usage. Unmapped events and non-ASCII characters are ignored.

F12 is consumed by AirKeys to toggle forwarding. Scroll Lock is consumed on release to stop the service. The local OS may still receive ordinary keystrokes; AirKeys does not suppress them.

