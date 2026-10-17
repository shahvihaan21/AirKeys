# Windows Feasibility Audit — LaptopKey (Phase 2)

## 1. System Environment

| Component | Detected Value |
|---|---|
| **OS** | Microsoft Windows 11 Pro, Build 26300.0 |
| **Python** | 3.12.10 (CPython, 64-bit) |
| **Bluetooth Adapter** | Intel(R) Wireless Bluetooth(R) (USB VID `0x8087`, PID `0x0026`) |
| **BLE Peripheral Role** | **Supported** (`is_peripheral_role_supported = True`) |
| **Advertisement Offload** | **Supported** (`is_advertisement_offload_supported = True`) |
| **WinRT GATT Server** | **GattServiceProvider for HID Service (0x1812) created successfully** |

---

## 2. Why a Normal Windows Bluetooth App Cannot Expose a BR/EDR HID Keyboard

BtRemote (Phase 1 reference) uses Android's `BluetoothHidDevice` API, which registers the phone as a **Bluetooth Classic (BR/EDR) HID Device** via the SDP protocol. Windows has **no public API** for this role:

- Windows Bluetooth Classic stack (`bthport.sys`, `bth.inf`) is architected exclusively as a **HID Host** (Central). It includes `hidbth.sys` for connecting *to* keyboards, not for *becoming* one.
- There is no `BluetoothHidDevice` equivalent in Win32, WinRT, or .NET.
- The Windows HID minidriver architecture (`hidclass.sys`) is designed for devices plugged *into* Windows, not for Windows to present itself as a device to other hosts.
- Custom BR/EDR SDP service registration and L2CAP channel management for HID would require a kernel-mode Bluetooth filter driver — significant complexity and no documented supported path.

**Conclusion**: BR/EDR (Bluetooth Classic) HID peripheral role is not feasible on Windows without custom kernel drivers.

---

## 3. Feasible Alternative: BLE HID over GATT Profile (HOGP)

Bluetooth Low Energy defines the **HID over GATT Profile (HOGP)**, standardized in the Bluetooth specification. Under HOGP, a peripheral device exposes a GATT server with:

- **HID Service** (UUID `0x1812`)
- **Device Information Service** (UUID `0x180A`)
- **Battery Service** (UUID `0x180F`)

Android (5.0+), iOS (8+), and other BLE hosts natively support connecting to HOGP peripherals as keyboards without any app installation.

### Verified on This System

| Check | Result |
|---|---|
| `BluetoothAdapter.is_peripheral_role_supported` | ✅ `True` |
| `BluetoothAdapter.is_advertisement_offload_supported` | ✅ `True` |
| `GattServiceProvider.create_async(0x1812)` | ✅ Success |

The Intel Wireless Bluetooth adapter on this laptop fully supports the BLE peripheral role, and the WinRT GATT Server APIs are functional.

### API Stack

```
Python 3.12
    └─ winrt-runtime (pywinrt 3.2.1)
        └─ WinRT GattServiceProvider API
            └─ Windows.Devices.Bluetooth.GenericAttributeProfile
                └─ Windows BLE Stack (bthport.sys + bthleenum.sys)
                    └─ Intel BT HCI (USB)
```

### Required GATT Characteristics for HOGP Keyboard

| UUID | Name | Properties | Purpose |
|---|---|---|---|
| `0x2A4A` | HID Information | Read | HID version, country code, flags |
| `0x2A4B` | Report Map | Read | HID descriptor (keyboard layout) |
| `0x2A4C` | HID Control Point | Write-No-Response | Suspend/Exit-Suspend |
| `0x2A4D` | Report (Input) | Read, Notify | Keyboard reports via notifications |
| `0x2A4D` | Report (Output) | Read, Write | LED state from host (optional) |

Each Report characteristic requires a **Report Reference Descriptor** (`0x2908`) specifying Report ID and Report Type (Input=1, Output=2).

### Keyboard Report Format (Standard 8-byte)

```
Byte 0: Modifier bitmap (Ctrl, Shift, Alt, GUI — left and right)
Byte 1: Reserved (0x00)
Bytes 2-7: Up to 6 simultaneous keycodes (USB HID Usage Table 0x07)
```

---

## 4. Approach Comparison

| Approach | Feasibility | Complexity | No Install on Phone | Maintenance |
|---|---|---|---|---|
| **BR/EDR HID (like BtRemote)** | ❌ No Windows API | Kernel driver | Yes | Very high |
| **BLE HOGP via WinRT GattServiceProvider** | ✅ Verified | Moderate (Python) | Yes | Low |
| **USB HID Gadget (OTG cable)** | ✅ Works | Low | Yes (wired) | Low |
| **Network-based (ADB/TCP)** | ✅ Works | Low | Requires app | Medium |

---

## 5. Known Risks and Limitations

1. **Device Information Service (`0x180A`)**: Windows may reserve this UUID. If `GattServiceProvider` refuses it, we can try omitting it or using vendor-specific workarounds. Android does not strictly require it for HOGP.

2. **Battery Service (`0x180F`)**: Some hosts (especially iOS) expect this. If Windows blocks it, we may need to test without it. Android is generally lenient.

3. **Pairing / Bonding**: HOGP typically requires LE Secure Connections bonding. Windows handles incoming pairing natively when the peripheral advertises with security flags. This needs testing with an actual Android device.

4. **Report Reference Descriptors**: The WinRT `GattLocalCharacteristicParameters` API supports adding custom descriptors, but the exact mechanism needs validation.

5. **Latency**: BLE has higher latency than BR/EDR HID. For keyboard use, this is typically acceptable (10-30ms additional vs. Classic).

6. **Reconnection**: BLE peripherals can store bonding information. After initial pairing, reconnection should work by re-advertising. Needs testing.

---

## 6. GO / NO-GO Decision

### ✅ GO — Proceed to Phase 3

**Rationale**:
- The laptop's Intel Bluetooth adapter **confirms** BLE peripheral role support.
- The WinRT `GattServiceProvider` API **successfully created** a provider for the HID Service UUID.
- Python WinRT bindings (pywinrt 3.2.1) are **fully functional** on this system.
- The HOGP approach requires **no app installation** on the Android phone.
- The HOGP approach requires **no kernel drivers or native components** — pure Python.

**Implementation plan**:
1. Create a GATT server with HID Service, required characteristics, and report map.
2. Start BLE advertising.
3. Capture laptop keyboard input via Python (`pynput` or low-level hooks).
4. Translate key events to standard 8-byte HID reports.
5. Send reports as GATT notifications to the connected host.

**Next step**: Phase 3 — Build minimal proof of concept.
