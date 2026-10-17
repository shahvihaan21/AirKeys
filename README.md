# AirKeys ⌨️📱

Turn your Windows laptop's physical keyboard into a wireless Bluetooth keyboard for your phone or tablet — **without installing any app or receiver on the phone**.

The mobile device detects and connects to the laptop as a standard, generic Bluetooth HID keyboard.

---

## 📂 Project Structure

A clean, minimalist, and properly structured layout:

```
AirKeys/
├── docs/                     # Architectural feasibility & protocol specifications
│   ├── feasibility.md        # Windows Bluetooth driver & HOGP analysis
│   └── reverse_engineering.md# BLE HID protocol and scancode reverse engineering
├── scripts/                  # 1-Click Windows shortcuts & helper scripts
│   ├── off.bat               # 1-Click shortcut to turn OFF
│   ├── on.bat                # 1-Click shortcut to turn ON
│   ├── status.bat            # 1-Click shortcut to check status
│   ├── switch.bat            # 1-Click shortcut to toggle ON/OFF
│   └── switch.py             # Instant ON/OFF power switch CLI
├── src/                      # Core implementation
│   ├── __init__.py
│   ├── ble_hid_service.py    # BLE HID-over-GATT (HOGP) service via WinRT
│   ├── hid_report.py         # Standard 8-byte HID keyboard reports & scancodes
│   └── main.py               # Keyboard capture hook, state manager & background daemon
├── tests/                    # Automated unit test suite
│   ├── __init__.py
│   ├── test_cli.py           # CLI state & process management tests
│   └── test_hid_report.py    # Keystroke encoding & modifier tests
├── .gitignore                # Git ignore configuration
├── cli.py                    # Master CLI script (on, off, switch, status, logs, check)
├── README.md                 # Project documentation
└── requirements.txt          # Python dependencies
```

---

## ⚡ Quick Start: The ON / OFF Switch

You have multiple convenient ways to turn AirKeys ON and OFF:

### 1. The Quick Switches (1-Click Shortcuts)
All launcher shortcuts are organized in the `scripts/` folder:
- **Turn ON**: Double-click `scripts/on.bat` (or run `python cli.py on`)
- **Turn OFF**: Double-click `scripts/off.bat` (or run `python cli.py off`)
- **Flip Switch (Toggle ON / OFF)**: Double-click `scripts/switch.bat` or run:
  ```bash
  python cli.py switch
  # or
  python scripts/switch.py
  ```

### 2. The Interactive Visual Switch
Open an interactive console dashboard to flip the switch and monitor status in real-time:
```bash
python cli.py switch -i
# or
python scripts/switch.py -i
```

### 3. CLI Commands
```bash
python cli.py on           # Turn ON AirKeys in background
python cli.py off          # Turn OFF AirKeys cleanly
python cli.py switch       # Flip ON/OFF switch
python cli.py status       # Check service status & active PID
python cli.py check        # Test Bluetooth hardware BLE support
python cli.py logs         # Tail recent diagnostic logs
python cli.py restart      # Restart service
```

---

## 📱 Pairing with Your Phone

1. **Turn on AirKeys**: Run `python cli.py on` or double-click `scripts/switch.bat`.
2. **On your phone**:
   - Go to **Settings → Connected devices → Bluetooth**.
   - Tap **Pair new device**.
   - Select **LaptopKey** (or your machine's BLE advertised name) from the list.
   - If Windows shows a pairing notification banner, click **Allow / Connect**.
3. **Typing**:
   - As soon as paired, your phone will register it as a **Physical Keyboard**.
   - Keystrokes typed on your laptop keyboard are instantly transmitted over BLE!

---

## 🎛️ Live Runtime Controls

While AirKeys is running:

| Key / Action | What it does |
| :--- | :--- |
| <kbd>F12</kbd> | **Forwarding Mute Switch**: Toggles whether keystrokes go to the phone or stay on your laptop (without disconnecting Bluetooth). |
| <kbd>Scroll Lock</kbd> | **Clean Exit**: Releases all keys, unhooks keyboard listener, terminates BLE advertising, and exits. |
| `python cli.py off` | **CLI Off Switch**: Gracefully signals background daemon to release keys and shut down. |

---

## 🛠️ Requirements & Installation

- **OS**: Windows 10 (1703+) or Windows 11 (64-bit)
- **Python**: 3.10+
- **Bluetooth Adapter**: Must support BLE Peripheral Role (Intel, Qualcomm, Realtek, Broadcom)
- **Phone**: Android 5.0+ or any BLE HID-compatible device (iOS, smart TVs, PCs, etc.)

### Install Dependencies
```bash
pip install -r requirements.txt
```

Verify your Bluetooth adapter capability at any time:
```bash
python cli.py check
```

---

## 🧪 Running Automated Tests

Run the full test suite:
```bash
python -m unittest discover tests
```
