# Security, reliability, and lifecycle

AirKeys captures global keyboard events while its listener is active. Those events are transformed into HID reports and may be notified to every subscribed client. Treat this as sensitive input capability: use only with a trusted, paired host and stop the process when it is not needed.

## Security boundary

- HID characteristics request `ENCRYPTION_AND_AUTHENTICATION_REQUIRED` from Windows.
- Notifications are attempted only when the Input Report characteristic has subscribers.
- Pairing, encryption enforcement, bond management, and peer identity are Windows/host responsibilities. AirKeys has no application-level allowlist, bond store, peer identity callback, or per-notification authorization decision.
- The Battery service is intentionally plain and exposes only a static 100% value; it contains no keyboard data.

Do not use this prototype for passwords, recovery phrases, payment data, or other sensitive entry until you have validated pairing and reconnection on the exact devices involved.

## Reliability behavior

- Send operations are serialized by an async lock.
- A failed notification and a subscriber-loss event clear in-memory pressed-key state.
- Disabling forwarding with F12 generates a release-all report before muting.
- Normal shutdown attempts release-all, stops the key listener, stops advertising, removes PID files, and clears stop sentinels.

There is an unavoidable limitation: abrupt process crashes, battery loss, or forced termination can prevent the final release report from reaching the host. The real-device checklist includes a held-key disconnect test for this reason.

