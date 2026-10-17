# BtRemote Reverse-Engineering Report (Phase 1)

## 1. Overview & Source Architecture
- **Repository URL**: `https://gitlab.com/Atharok/BtRemote`
- **Application Type**: Android application written 100% in Kotlin (targeting Android 9 / API 28+).
- **Core Purpose**: Turns an Android smartphone into a Bluetooth HID peripheral (Remote Control, Keyboard, Mouse) to control Android TV or other Bluetooth HID hosts without requiring a companion app on the host device.
- **License**: GNU General Public License v3.0 (GPLv3). Third-party dependencies (Jetpack Compose, Koin, AndroidX) use Apache 2.0.

### Directory Structure & Key Files
```
BtRemote/
├── app/src/main/
│   ├── AndroidManifest.xml
│   └── java/com/atharok/btremote/
│       ├── common/
│       │   ├── injections/Modules.kt            # Dependency injection definitions (Koin)
│       │   └── utils/Constants.kt               # HID Descriptor, Report IDs, Timing constants
│       ├── data/
│       │   └── bluetooth/
│       │       ├── BluetoothHidCore.kt          # Core Bluetooth HID Device wrapper & I/O
│       │       ├── BluetoothLocalData.kt        # Local adapter info & bonded devices query
│       │       ├── BluetoothScanner.kt          # Bluetooth Classic device discovery
│       │       └── BluetoothStatus.kt           # Adapter state monitoring
│       ├── domain/entities/remoteInput/
│       │   ├── RemoteButtonProperties.kt        # Predefined buttons & byte sequences
│       │   └── keyboard/
│       │       ├── KeyboardKey.kt               # HID keyboard scan codes & modifier masks
│       │       └── virtualKeyboard/
│       │           ├── VirtualKeyboardLayout.kt # Mapping base class
│       │           └── EnglishUSVirtualKeyboardLayout.kt # Char-to-report byte mapping
│       └── presentation/services/
│           └── BluetoothHidService.kt           # Foreground service managing lifecycle
```

---

## 2. Bluetooth & HID Implementation Details

### A. HID Profile Registration & Device Discovery
- **Native API Used**: `android.bluetooth.BluetoothHidDevice` (introduced in Android P / API 28).
- **Profile Initialization Sequence**:
  1. `BluetoothHidCore.startBluetoothHidProfile()`:
     Invokes `BluetoothAdapter.getProfileProxy(context, serviceListener, BluetoothProfile.HID_DEVICE)`.
  2. In `ServiceListener.onServiceConnected(i, bluetoothProfile)`:
     Casts profile to `BluetoothHidDevice`.
  3. Registers application SDP record using `BluetoothHidDevice.registerApp(...)`:
     ```kotlin
     hidDevice.registerApp(hidSettings, null, null, Runnable::run, callback)
     ```
  4. SDP Settings configured in `Modules.kt`:
     - Name: App Name ("BT Remote")
     - Description: `"Bluetooth HID Device"`
     - Provider: `"Atharok"`
     - Subclass: `BluetoothHidDevice.SUBCLASS2_UNCATEGORIZED` (0xC0)
     - Descriptor: Raw byte array `bluetoothHidDescriptor` from `Constants.kt`.
- **Discovery Implementation**:
  - `BluetoothScanner.startDiscoveryDevices()` invokes `BluetoothAdapter.startDiscovery()`.
  - Registered `BroadcastReceiver` catches `BluetoothDevice.ACTION_FOUND` and collects remote devices (`DeviceEntity`).

### B. Bluetooth Pairing and Connection Sequence
- **Connection**:
  1. `BluetoothHidCore.connectDevice(deviceAddress: String)`:
     Fetches `BluetoothDevice` via `adapter.getRemoteDevice(macAddress)`.
  2. Calls `BluetoothHidDevice.connect(device)`.
  3. Connection state updates stream via `BluetoothHidDevice.Callback.onConnectionStateChanged(device, state)`.
  4. States tracked: `BluetoothProfile.STATE_CONNECTING`, `STATE_CONNECTED`, `STATE_DISCONNECTING`, `STATE_DISCONNECTED`.
- **Pairing**: Relies on standard Android OS Bluetooth Classic / BR/EDR pairing flow triggered when the remote host attempts to connect to the registered HID SDP service or vice versa.

### C. HID Report Descriptors & Report Format
The descriptor in `Constants.kt` defines three Report IDs over Classic Bluetooth L2CAP channels (PSM 0x0011 Control, PSM 0x0013 Interrupt):
1. **Report ID 1 — Keyboard**:
   - Usage Page: Generic Desktop (`0x01`), Usage: Keyboard (`0x06`).
   - Field 1 (Modifier byte): Usage Page Keyboard Key Codes (`0x07`), Usages `0xE0` to `0xE7` (Left Ctrl, Left Shift, Left Alt, Left GUI, Right Ctrl, Right Shift, Right Alt, Right GUI). 8 bits, Variable.
   - Field 2 (Key byte): Usage Page Keyboard Key Codes (`0x07`), Logical Min `0`, Logical Max `255`. 8 bits (1 byte), Array.
   - **Total keyboard report length**: 2 bytes (`[modifiers, keycode]`).
2. **Report ID 2 — Consumer Control (Remote)**:
   - Usage Page Consumer Devices (`0x0C`), Usage Consumer Control (`0x01`).
   - 16-bit usage code (2 bytes).
3. **Report ID 3 — Mouse**:
   - 3 buttons (3 bits) + 5 padding bits (1 byte), Relative X (1 byte), Relative Y (1 byte), Wheel (1 byte). Total: 4 bytes payload.

### D. Key Events, Modifiers, and Report Transmission
- **Report Transmission API**:
  `BluetoothHidDevice.sendReport(device, reportId, reportBytes)`.
- **Key Press & Release Sequence**:
  In `BluetoothHidCore.sendTextReport(...)`:
  1. Key Down: `sendReport(KEYBOARD_REPORT_ID, [modifier_byte, keycode])`
  2. Delay: `25ms` (`DELAY_BETWEEN_KEY_PRESSES_IN_MILLIS`)
  3. Key Up: `sendReport(KEYBOARD_REPORT_ID, [0x00, 0x00])` (`REMOTE_INPUT_NONE`)
  4. Delay: `25ms`
- **Modifiers in BtRemote**:
  - `KEY_CTRL_LEFT` = `0x01`
  - `KEY_SHIFT_LEFT` = `0x02`
  - `KEY_ALT` = `0x04`
  - `KEY_META_LEFT` = `0x08`
  - `KEY_CTRL_RIGHT` = `0x10`
  - `KEY_SHIFT_RIGHT` = `0x20`
  - `KEY_ALT_GR` = `0x40`
  - `KEY_META_RIGHT` = `0x80`
- **Keycodes**: Standard USB HID Usage Tables for Keyboard (e.g. `0x04` for 'a', `0x28` for Enter, `0x2A` for Backspace).

### E. Disconnection and Reconnection
- **Disconnection**:
  Calls `BluetoothHidDevice.disconnect(device)`. (Note: The author notes in comments that on some devices like Pixel 3a, calling disconnect twice is needed due to driver/stack bugs).
- **Reconnection**:
  Stores `autoConnectDeviceAddress`. When `BluetoothHidDevice.Callback.onAppStatusChanged(registered=true)` fires, if an address is saved, `connectDevice(autoConnectDeviceAddress)` is automatically invoked.

---

## 3. Architecture & Technical Differences from Windows
| Dimension | BtRemote (Android) | Windows Target (LaptopKey) |
|---|---|---|
| **OS Role** | Android acting as Bluetooth Peripheral (HID Device) | Windows acting as Bluetooth Peripheral (HID Device) |
| **API Mechanism** | High-level Java/Kotlin framework API: `android.bluetooth.BluetoothHidDevice` (Android 9+) | Windows does **NOT** provide a public Win32 or WinRT API for Bluetooth HID Device profile (Peripheral role over BR/EDR or GATT HID Service Peripheral). Windows Bluetooth stack is strictly engineered as a HID **Host** (Central). |
| **Hardware / Radio** | Smartphone Bluetooth controller with peripheral BR/EDR and BLE peripheral firmware support | Laptop Bluetooth controller (Intel, Realtek, Qualcomm, Broadcom). Many controllers support peripheral advertising, but Windows OS drivers restrict peripheral HID. |

---

## 4. Verified Findings vs. Assumptions
- **Verified Findings**:
  - `BtRemote` is strictly an Android client app utilizing Android's specialized `BluetoothHidDevice` API.
  - The HID descriptor and report structures are verified directly from `Constants.kt` lines 53-120.
  - Key codes, report framing, and modifier byte bitmasks are verified from `KeyboardKey.kt` and `EnglishUSVirtualKeyboardLayout.kt`.
- **Assumptions / Non-transfers**:
  - Android's `BluetoothHidDevice` API has **no equivalent** direct counterpart in the standard Windows SDK or WinRT `Windows.Devices.Bluetooth` namespaces.
  - Feasibility on Windows requires an in-depth audit of Windows Bluetooth driver capabilities and peripheral support (Phase 2).
