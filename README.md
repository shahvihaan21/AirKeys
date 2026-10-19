# ⌨️ AirKeys — Turn Your Laptop into a Bluetooth Keyboard

<p align="center">
  <strong>Your laptop's keyboard. Your phone's screen. No companion app required.</strong>
</p>

AirKeys is a Windows-based experimental project that explores turning a laptop into a wireless Bluetooth keyboard for an Android phone or another compatible device. It uses the Bluetooth Human Interface Device (HID) concept so a compatible phone can recognize the laptop as a standard keyboard.

The project combines a practical everyday idea with hands-on work in Bluetooth Low Energy (BLE), HID reports, keyboard event handling, Windows integration, and debugging.

<p align="center">
  <img src="https://img.shields.io/badge/Platform-Windows-blue" alt="Platform: Windows">
  <img src="https://img.shields.io/badge/Language-Python-3776AB" alt="Language: Python">
  <img src="https://img.shields.io/badge/Connectivity-Bluetooth%20LE-5865F2" alt="Connectivity: Bluetooth LE">
  <img src="https://img.shields.io/badge/Status-Experimental%20Prototype-orange" alt="Status: Experimental prototype">
</p>

---

## ✨ Why AirKeys?

Typing long messages on a phone can be awkward when a physical keyboard is already available. AirKeys explores a way to use that keyboard directly, without installing a dedicated receiver app on the mobile device.

- ⌨️ **More comfortable typing:** Use your laptop's physical keyboard for mobile text input.
- 📱 **No phone-side companion app:** The intended workflow uses the phone's built-in support for compatible Bluetooth keyboards.
- 📡 **Direct wireless connection:** Designed around Bluetooth rather than Wi-Fi or cloud services.
- 🧪 **Built to learn:** A practical experiment in HID protocols, BLE communication, and Windows system integration.
- 🎛️ **Convenient controls:** Includes command-line controls and Windows shortcut scripts for managing the service.

> **Compatibility note:** This approach depends on the Bluetooth adapter, Windows drivers and APIs, and the receiving device's HID support. Not every Windows laptop supports acting as a BLE keyboard peripheral out of the box.

## 🎬 See It in Action

The intended experience is simple: enable AirKeys, pair the phone with the advertised Bluetooth keyboard, and type on the laptop.

<!-- Add a real demonstration GIF or screenshot at assets/airkeys-demo.gif to display it here. -->
<p align="center">
  <img src="assets/airkeys-demo.gif" alt="AirKeys demonstration: typing on a laptop and receiving text on a phone" width="800">
</p>
<p align="center"><em>⌨️ One laptop. One phone. Wireless typing.</em></p>

**Adding a demo:** Save a short recording or GIF showing actual input being received by the phone as `assets/airkeys-demo.gif`. If you do not have a demo file yet, remove the image block above until one is available; otherwise GitHub will show a broken image.

---

## ⚙️ How It Works

AirKeys explores Bluetooth HID emulation, with BLE HID over GATT (HOGP) as its intended peripheral approach.

At a high level, the program:

1. 🖥️ Runs on the Windows laptop.
2. 📡 Advertises a compatible Bluetooth HID keyboard service, where supported.
3. 📱 Allows a compatible phone or other host to discover and pair with the keyboard.
4. ⌨️ Captures keyboard input and represents key presses using standard HID keyboard reports.
5. 🔁 Provides runtime controls to pause forwarding or shut down cleanly.

Bluetooth discovery and pairing alone are not enough: the laptop must expose the right peripheral role and a compatible HID service, and the phone must accept the resulting keyboard input.

### 🧩 Technical Components

| Component | Role |
|---|---|
| Bluetooth HID / HOGP | Describes how a compatible host recognizes keyboard input over BLE. |
| BLE service | Handles the Bluetooth HID-over-GATT service through supported Windows APIs. |
| HID reports | Encodes key presses, releases, and modifier keys into keyboard reports. |
| Keyboard event handling | Captures local keyboard events for forwarding. |
| Runtime controls | Manages activation, deactivation, status, and clean shutdown. |
| Diagnostics and tests | Helps check adapter support and validate key-report and CLI behavior. |

---

## 🧰 Requirements

- **Operating system:** Windows 10 (version 1703 or later) or Windows 11, 64-bit
- **Python:** 3.10 or newer
- **Bluetooth adapter:** Must support the required BLE peripheral role and work with the implementation
- **Receiving device:** Android 5.0+ or another device that supports compatible Bluetooth HID keyboards
- **Dependencies:** Installed from `requirements.txt`

Support for iOS, smart TVs, PCs, and other BLE HID-compatible devices may vary. The requirements above do not guarantee compatibility with every adapter or device.

## 🚀 Installation

### 1. Get the project

Clone the repository, or download and extract its source code. Open a terminal in the project directory.

### Recommended: one-step setup

Double-click `setup.bat` (or run it from Command Prompt). It creates a project-local `.venv`, installs the required packages into that environment, and checks whether the Bluetooth adapter can act as a BLE peripheral. The shortcut scripts automatically use this environment afterwards.

If the final check reports that the BLE peripheral role is unsupported, this is a hardware/driver limitation rather than an installation failure. AirKeys cannot make that adapter advertise as a HID keyboard; update the Bluetooth driver or use an adapter that supports BLE peripheral mode.

### 2. Create and activate a virtual environment (recommended)

```powershell
py -3.10 -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation due to its execution policy, use an approved activation method for your environment or run the commands through Command Prompt instead.

### 3. Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Check Bluetooth capability

```powershell
python cli.py check
```

Run this check before troubleshooting pairing. If the adapter or Windows environment does not support the required BLE peripheral behavior, the project may not be able to operate on that machine without a different supported implementation or hardware.

`check` must finish with both **BLE Peripheral Role: Supported** and **GattServiceProvider HOGP: Supported**. Installing Python packages cannot compensate for either result being unsupported.

---

## ⚡ Quick Start: Control AirKeys

AirKeys provides command-line controls and Windows shortcut scripts.

### Common commands

Run these commands from the project root:

```powershell
python cli.py on
python cli.py status
python cli.py off
```

| Command | What it does |
|---|---|
| `python cli.py on` | Starts AirKeys in the background. |
| `python cli.py off` | Requests a clean shutdown. |
| `python cli.py switch` | Toggles AirKeys on or off. |
| `python cli.py status` | Checks service status and active process information. |
| `python cli.py check` | Checks Bluetooth BLE support. |
| `python cli.py logs` | Displays recent diagnostic logs. |
| `python cli.py restart` | Restarts the service. |

### 🖱️ One-click Windows shortcuts

The `scripts/` folder includes shortcuts for common actions:

- `scripts/on.bat` — turn AirKeys on
- `scripts/off.bat` — turn AirKeys off
- `scripts/switch.bat` — toggle on/off
- `scripts/status.bat` — check status

Double-click the relevant `.bat` file to run its action. You can also use the command-line interface for the same controls.

### 🎛️ Interactive switch

To open the interactive console switch, run:

```powershell
python cli.py switch -i
```

The standalone helper is also available:

```powershell
python scripts/switch.py -i
```

---

## 📱 Pair Your Phone

1. **Start AirKeys** using `python cli.py on` or `scripts/switch.bat`.
2. On your phone, open **Settings → Bluetooth** (the exact menu name varies by device).
3. Choose **Pair new device** or the equivalent discovery option.
4. Select **LaptopKey** or the Bluetooth name advertised by your implementation.
5. If Windows displays a pairing or connection prompt, review it and allow the connection when appropriate.
6. Open a text field on the phone and try typing on the laptop keyboard.

Once connected successfully, the phone should recognize the device as a physical keyboard. The advertised name may differ depending on the current configuration.

**If it does not work:** run `python cli.py check`, verify that the adapter supports the required BLE peripheral role, confirm that AirKeys is running, and check the logs. A successful Bluetooth pairing does not necessarily mean HID input is being delivered correctly.

---

## 🎹 Runtime Controls

While AirKeys is running, the implementation provides these controls:

| Key / command | Action |
|---|---|
| `F12` | Toggles keyboard forwarding on or off without disconnecting Bluetooth. |
| `Scroll Lock` | Initiates a clean exit, releases held keys, removes the keyboard hook, and stops BLE advertising. |
| `python cli.py off` | Requests a graceful shutdown of the background service. |

These controls are implementation-specific and may depend on the active configuration and runtime environment.

---

## 🧪 Run the Tests

Run the automated test suite from the project root:

```powershell
python -m unittest discover tests
```

The test suite includes checks for HID report encoding and modifier handling, as well as CLI state and process-management behavior.

Tests can help validate individual components, but they do not replace testing with the actual Bluetooth adapter and receiving device.

---

## 📂 Project Structure

```text
AirKeys/
├── docs/
│   ├── feasibility.md          # Windows Bluetooth and HOGP feasibility notes
│   └── reverse_engineering.md  # BLE HID protocol and scancode research
├── scripts/
│   ├── off.bat                 # Turn AirKeys off
│   ├── on.bat                  # Turn AirKeys on
│   ├── status.bat              # Check service status
│   ├── switch.bat              # Toggle on/off
│   └── switch.py               # Interactive/CLI switch helper
├── src/
│   ├── __init__.py
│   ├── ble_hid_service.py      # BLE HID-over-GATT service
│   ├── hid_report.py           # HID keyboard reports and scancodes
│   └── main.py                 # Keyboard capture and runtime management
├── tests/
│   ├── __init__.py
│   ├── test_cli.py             # CLI and process-management tests
│   └── test_hid_report.py      # HID report and modifier tests
├── assets/
│   └── airkeys-demo.gif        # Optional project demonstration
├── cli.py                      # Main command-line interface
├── requirements.txt            # Python dependencies
└── README.md                   # Project documentation
```

The `assets/` folder and demo GIF are optional additions for the README; create them only when you have a real screenshot or recording to include.

---

## 🧠 Development Journey & Lessons Learned

AirKeys began with a practical question: could a laptop act as a keyboard for a phone instead of merely connecting to a keyboard?

The experiment involved researching the difference between Bluetooth host and peripheral roles, exploring HID behavior, working with key reports, and troubleshooting connection and input delivery.

The development notes for the original LaptopKey experiment record an initial prototype session of approximately 30 minutes and around 20 minutes of active troubleshooting. They also record a practical test in which text was typed on a phone using the program. These are observations from that experiment, not a claim of universal compatibility or production readiness.

### Key takeaways

- **Pairing is not the same as input:** The correct Bluetooth role and HID service must be available.
- **Hardware support matters:** Adapters, drivers, and operating-system APIs can determine whether peripheral emulation is possible.
- **Protocol details matter:** Key presses, releases, and modifier states must be encoded and handled consistently.
- **Test on real devices:** Unit tests are useful, but real Bluetooth behavior needs hardware testing.
- **Small experiments can teach a lot:** A simple convenience idea can lead to meaningful work in wireless communication and system integration.

## 🛣️ Possible Next Steps

- 🔄 Improve pairing and reconnection reliability.
- ⌨️ Expand keyboard-layout, shortcut, modifier, and special-character handling.
- 📱 Test across more Android versions, phones, and Bluetooth adapters.
- 🖥️ Add a lightweight status interface for connecting and disconnecting.
- 📖 Improve setup guidance and reproducible troubleshooting.
- 🧪 Expand automated tests and document hardware-specific limitations.

These are potential improvements, not features guaranteed to be available in the current prototype.

---

## 🤝 Contributing & Feedback

This is an experimental personal engineering project. If you try it on a different Windows machine or Bluetooth adapter, useful feedback includes:

- Windows version and Bluetooth adapter model
- Receiving device and operating-system version
- Whether the device can discover and pair with AirKeys
- Whether keyboard input works after pairing
- Any relevant diagnostic output, with personal information removed

Please avoid reporting a device as supported based on Bluetooth discovery alone; successful keyboard input is the meaningful test.

## 📌 Project Details

- **Name:** AirKeys
- **Category:** Bluetooth HID emulation, wireless communication, system integration
- **Primary platform:** Windows
- **Implementation language:** Python
- **Target experience:** Use a laptop keyboard to enter text on a compatible mobile device
- **Status:** Experimental prototype

---

<p align="center">
  <strong>Built out of curiosity. Tested through experimentation. ⌨️📡</strong><br>
  <em>Making everyday devices do something a little more interesting.</em>
</p>
