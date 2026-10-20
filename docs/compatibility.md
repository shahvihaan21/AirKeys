# Compatibility and troubleshooting

## Compatibility matrix

| Platform / requirement | Status | Notes |
|---|---|---|
| Windows 10/11 + Python 3.10+ | Required | This is the implementation platform. |
| Adapter BLE peripheral role | Required | `python cli.py check` must report supported. |
| WinRT local HID service creation | Required | The same check must create HOGP service `0x1812`. |
| Android BLE HID host | Candidate; device-specific | No current compatibility certification or media evidence is committed. |
| iOS/iPadOS BLE HID host | Unverified | Do not assume support. |
| Windows/macOS/Linux receiving host | Unverified | Do not assume support. |
| Bluetooth Classic-only host | Unsupported | AirKeys is BLE HOGP, not Classic HID. |

## Troubleshooting

| Symptom | Check / action |
|---|---|
| `check` reports no adapter or no peripheral role | Update the adapter driver, enable Bluetooth, or use an adapter that supports BLE peripheral mode under Windows. Python packages cannot add this capability. |
| Service exits or never appears | Run `python cli.py logs`; first resolve missing dependencies and failures creating the HID service. |
| Phone pairs but receives no input | Confirm it subscribed to the Input Report, use the log to look for subscriber changes, then perform the supported-key test in `verification.md`. |
| Input has unexpected characters | Use a US-oriented host layout for testing. HID usages are physical positions, and the receiving host applies its own layout. |
| Key looks stuck | Disconnect/reconnect and restart AirKeys. Capture logs and report the held key plus disconnect timing. |
| `off` has to force terminate | Check logs and report it. A forced termination may skip the release report. |

