# Contributing

Please open an issue before a large behavior change. Include the Windows build, Python version, Bluetooth adapter and driver, receiving-device model/OS, `cli.py check` output, and relevant sanitized logs.

For code changes:

1. Keep claims in documentation aligned with observed evidence.
2. Add or update focused tests for report, CLI, or mocked BLE logic.
3. Run `python -m unittest discover tests`.
4. For Bluetooth changes, execute the real-device protocol in `docs/verification.md` and report the hardware result separately from unit-test results.

Do not add credentials, pairing identifiers, personal input, or unredacted logs. See `docs/implementation-status.md` for current scope and planned work.

