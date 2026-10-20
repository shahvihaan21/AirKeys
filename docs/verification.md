# Verification

## Automated checks

Run from the repository root:

```powershell
python -m unittest discover tests
```

| Test module | What it verifies | What it does not verify |
|---|---|---|
| `test_hid_report.py` | 8-byte reports, modifiers, rollover behavior, supported mappings, release-all | OS hooks, Windows Bluetooth, or a receiving device |
| `test_cli.py` | PID helper behavior and startup refusal when dependencies are absent | A detached process on a physical Windows installation |
| `test_ble_hid_service.py` | Protected characteristic configuration and mocked send/disconnect behavior | WinRT, radio hardware, advertising, pairing, or host interoperability |

## Real-device protocol

Record the target machine, Windows build, Python version, Bluetooth adapter/driver, receiving host/model/OS, and outcome. Run `python cli.py check`; retain its output. Then test:

1. Advertising/discovery and OS pairing.
2. Subscription followed by lowercase/uppercase ASCII, digits, shifted punctuation, arrows, Backspace, Tab, and Enter.
3. Ctrl, Alt, and Shift combinations.
4. F12 mute/unmute and Scroll Lock shutdown.
5. Disconnect while a key is held, reconnect, and confirm no stuck key.
6. Stop/restart and reconnect.

Mark failures as failures; pairing alone is not proof of keyboard input. Do not report compatibility until all relevant steps have an observed result.

