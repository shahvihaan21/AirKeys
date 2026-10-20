# Implementation status

This table distinguishes repository behavior from intended work. “Implemented” means code exists; it does not mean it has been demonstrated on every adapter or host.

| Area | Status | Evidence / limitation |
|---|---|---|
| Windows BLE peripheral capability check | Implemented | `cli.py check` probes adapter and GATT HID-provider creation. It must pass on the target machine. |
| Local HID GATT service | Implemented | HID Information, Report Map, Control Point, Protocol Mode, Input Report, and Report Reference are created in `src/ble_hid_service.py`. |
| BLE advertising | Implemented | Starts after required HID service setup succeeds. The advertised display name is controlled by Windows and is not guaranteed to be `AirKeys`. |
| Keyboard capture and forwarding | Implemented | `pynput` callbacks map a defined subset of keys and queue reports. |
| Standard keyboard reports | Implemented | Eight bytes: modifier, reserved byte, and six usage slots. |
| Authenticated/encrypted HID GATT access | Implemented in configuration | The HID characteristics request Windows authenticated encryption. Actual pairing, bonding, and host enforcement require a device test. |
| Clean stop / release report | Implemented | Scroll Lock, Ctrl+C/signal, and CLI stop attempt an all-keys-released report before advertising stops. Forced process termination cannot guarantee this. |
| Android input validation | Historical observation only | The README records an earlier practical experiment, but there is no repeatable recording or current device result committed with this revision. |
| iOS, smart-TV, desktop-host support | Not verified | Do not infer support from standard UUIDs or successful advertising. |
| Bluetooth Classic HID | Not implemented | Windows public APIs do not provide the required peripheral HID-device role; see `feasibility.md`. |
| Consumer/media keys, mouse, text composition, LEDs | Not implemented | Only the mapped keyboard usages are sent. Output reports and LED state are not consumed. |
| Arbitrary Unicode / layout-aware text | Not implemented | Reports represent US physical key positions; unsupported characters are ignored and the host layout decides glyphs. |
| Persistent pairing/reconnect policy | Not implemented by AirKeys | Managed by Windows and the receiving host; no app-level bond store or allowlist exists. |

## Planned work

1. Capture reproducible real-device demonstrations and compatibility observations.
2. Add integration tests on a supported adapter and at least one host.
3. Add controlled reconnection, host state, and GATT Control Point/Protocol Mode handling if required by tested hosts.
4. Expand layout, special-key, and accessibility behavior only with corresponding tests.

