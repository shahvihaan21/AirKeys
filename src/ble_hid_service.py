"""
ble_hid_service.py — BLE HID over GATT (HOGP) Service for Windows

Uses WinRT GattServiceProvider to expose a standard BLE keyboard
that any BLE HID host (Android, iOS, etc.) can pair with and
receive keystrokes from — no app required on the host.

Architecture:
  - HID Service (0x1812) with Report Map, HID Info, Control Point, Input Report
  - Battery Service (0x180F) — static 100%
  - Advertising with service UUIDs

Does NOT capture keyboard input; that is the caller's responsibility.
"""
import asyncio
import logging
import uuid as _uuid
from typing import Callable, Optional

from winrt.windows.devices.bluetooth import BluetoothAdapter, BluetoothError
from winrt.windows.devices.bluetooth.genericattributeprofile import (
    GattServiceProvider,
    GattServiceProviderAdvertisingParameters,
    GattLocalCharacteristicParameters,
    GattLocalDescriptorParameters,
    GattCharacteristicProperties,
    GattProtectionLevel,
)
from winrt.windows.storage.streams import DataWriter

from hid_report import KEYBOARD_REPORT_MAP

log = logging.getLogger("ble_hid")

# ---- Standard BLE UUIDs ----
UUID_HID_SERVICE        = _uuid.UUID("00001812-0000-1000-8000-00805f9b34fb")
UUID_BATTERY_SERVICE    = _uuid.UUID("0000180f-0000-1000-8000-00805f9b34fb")
UUID_HID_INFORMATION    = _uuid.UUID("00002a4a-0000-1000-8000-00805f9b34fb")
UUID_REPORT_MAP         = _uuid.UUID("00002a4b-0000-1000-8000-00805f9b34fb")
UUID_HID_CONTROL_POINT  = _uuid.UUID("00002a4c-0000-1000-8000-00805f9b34fb")
UUID_REPORT             = _uuid.UUID("00002a4d-0000-1000-8000-00805f9b34fb")
UUID_REPORT_REFERENCE   = _uuid.UUID("00002908-0000-1000-8000-00805f9b34fb")
UUID_BATTERY_LEVEL      = _uuid.UUID("00002a19-0000-1000-8000-00805f9b34fb")
UUID_PROTOCOL_MODE      = _uuid.UUID("00002a4e-0000-1000-8000-00805f9b34fb")


def _write_bytes(data: bytes):
    """Helper: create an IBuffer from bytes."""
    w = DataWriter()
    w.write_bytes(data)
    return w.detach_buffer()


class BleHidService:
    """
    Manages the BLE GATT server lifecycle for a HOGP keyboard peripheral.

    Usage:
        service = BleHidService()
        await service.start()
        # ... later, when a host is connected:
        await service.send_report(report_bytes)
        # ... when done:
        await service.stop()
    """

    def __init__(self, on_subscriber_change: Optional[Callable] = None):
        self._hid_provider: Optional[GattServiceProvider] = None
        self._battery_provider: Optional[GattServiceProvider] = None
        self._input_report_char = None
        self._on_subscriber_change = on_subscriber_change
        self._is_advertising = False
        self._has_subscribers = False
        self._send_lock: Optional[asyncio.Lock] = None

    @staticmethod
    def _secure_protection_level():
        """Require an authenticated, encrypted LE link for HID interaction."""
        return GattProtectionLevel.ENCRYPTION_AND_AUTHENTICATION_REQUIRED

    # ---- Public API ----

    async def start(self) -> None:
        """Initialize GATT services and start advertising."""
        log.info("Checking adapter capabilities...")
        adapter = await BluetoothAdapter.get_default_async()
        if adapter is None:
            raise RuntimeError("No Bluetooth adapter found.")
        if not adapter.is_peripheral_role_supported:
            raise RuntimeError("Bluetooth adapter does not support peripheral role.")
        if not adapter.is_advertisement_offload_supported:
            log.warning("Advertisement offload not supported; advertising may not work.")
        log.info("Adapter OK — peripheral role supported.")

        await self._create_hid_service()
        await self._create_battery_service()
        self._start_advertising()
        log.info("BLE HID keyboard is now advertising. Pair from your phone.")

    async def stop(self) -> None:
        """Stop advertising and tear down services."""
        if self._hid_provider and self._is_advertising:
            self._hid_provider.stop_advertising()
        if self._battery_provider:
            try:
                self._battery_provider.stop_advertising()
            except Exception:
                pass
        self._is_advertising = False
        log.info("Stopped advertising.")

    async def send_report(self, report: bytes) -> bool:
        """
        Send an 8-byte keyboard HID report to connected host(s).
        Returns True if at least one notification was sent.
        """
        if len(report) != 8:
            raise ValueError("HID keyboard reports must be exactly 8 bytes.")
        if self._input_report_char is None:
            log.warning("Input report characteristic not initialized.")
            return False
        if self._send_lock is None:
            self._send_lock = asyncio.Lock()
        async with self._send_lock:
            try:
                subscribers = self._input_report_char.subscribed_clients
                if subscribers is None or subscribers.size == 0:
                    return False
                await self._input_report_char.notify_value_async(_write_bytes(report))
                return True
            except Exception as e:
                # A disconnected host can fail between the subscription check
                # and notification.  Return a result that callers must handle.
                log.error("Failed to send HID report: %s", e)
                return False

    @property
    def has_subscribers(self) -> bool:
        """True if at least one host is subscribed to input reports."""
        if self._input_report_char is None:
            return False
        try:
            subs = self._input_report_char.subscribed_clients
            return subs is not None and subs.size > 0
        except Exception:
            return False

    # ---- Internal: HID Service ----

    async def _create_hid_service(self) -> None:
        result = await GattServiceProvider.create_async(UUID_HID_SERVICE)
        if result.service_provider is None:
            raise RuntimeError(f"Failed to create HID service provider: {result.error}")
        self._hid_provider = result.service_provider
        service = self._hid_provider.service

        # 1. HID Information (0x2A4A) — Read
        params = GattLocalCharacteristicParameters()
        params.characteristic_properties = GattCharacteristicProperties.READ
        params.read_protection_level = self._secure_protection_level()
        # bcdHID = 1.11, bCountryCode = 0, Flags = 0x02 (normally connectable)
        params.static_value = _write_bytes(bytes([0x11, 0x01, 0x00, 0x02]))
        r = await service.create_characteristic_async(UUID_HID_INFORMATION, params)
        if r.characteristic is None:
            raise RuntimeError("Failed to create HID Information characteristic.")
        log.debug("Created HID Information characteristic.")

        # 2. Report Map (0x2A4B) — Read
        params = GattLocalCharacteristicParameters()
        params.characteristic_properties = GattCharacteristicProperties.READ
        params.read_protection_level = self._secure_protection_level()
        params.static_value = _write_bytes(KEYBOARD_REPORT_MAP)
        r = await service.create_characteristic_async(UUID_REPORT_MAP, params)
        if r.characteristic is None:
            raise RuntimeError("Failed to create Report Map characteristic.")
        log.debug("Created Report Map characteristic.")

        # 3. HID Control Point (0x2A4C) — Write Without Response
        params = GattLocalCharacteristicParameters()
        params.characteristic_properties = GattCharacteristicProperties.WRITE_WITHOUT_RESPONSE
        params.write_protection_level = self._secure_protection_level()
        r = await service.create_characteristic_async(UUID_HID_CONTROL_POINT, params)
        if r.characteristic is None:
            raise RuntimeError("Failed to create HID Control Point characteristic.")
        log.debug("Created HID Control Point characteristic.")

        # 4. Protocol Mode (0x2A4E) — Read, Write Without Response
        params = GattLocalCharacteristicParameters()
        params.characteristic_properties = (
            GattCharacteristicProperties.READ |
            GattCharacteristicProperties.WRITE_WITHOUT_RESPONSE
        )
        params.read_protection_level = self._secure_protection_level()
        params.write_protection_level = self._secure_protection_level()
        # Protocol Mode: 0x01 = Report Protocol
        params.static_value = _write_bytes(bytes([0x01]))
        r = await service.create_characteristic_async(UUID_PROTOCOL_MODE, params)
        if r.characteristic is None:
            log.warning("Could not create Protocol Mode characteristic (non-fatal).")
        else:
            log.debug("Created Protocol Mode characteristic.")

        # 5. Input Report (0x2A4D) — Read, Notify
        params = GattLocalCharacteristicParameters()
        params.characteristic_properties = (
            GattCharacteristicProperties.READ |
            GattCharacteristicProperties.NOTIFY
        )
        # Windows enforces this protection level for access to the local
        # characteristic/CCCD.  Reports are never notified until a client has
        # subscribed, so an unauthenticated client cannot receive them.
        params.read_protection_level = self._secure_protection_level()
        r = await service.create_characteristic_async(UUID_REPORT, params)
        if r.characteristic is None:
            raise RuntimeError("Failed to create Input Report characteristic.")
        self._input_report_char = r.characteristic

        # Add Report Reference descriptor (Report ID=0, Type=Input=1)
        desc_params = GattLocalDescriptorParameters()
        desc_params.read_protection_level = self._secure_protection_level()
        desc_params.static_value = _write_bytes(bytes([0x00, 0x01]))
        dr = await self._input_report_char.create_descriptor_async(
            UUID_REPORT_REFERENCE, desc_params
        )
        if dr.descriptor is None:
            log.warning("Could not create Report Reference descriptor.")
        else:
            log.debug("Created Report Reference descriptor on Input Report.")

        # Subscribe to subscriber changes
        def _on_subscribers_changed(sender, args):
            has = self.has_subscribers
            if has != self._has_subscribers:
                self._has_subscribers = has
                log.info(f"Subscriber status changed: {'connected' if has else 'disconnected'}")
                if self._on_subscriber_change:
                    self._on_subscriber_change(has)

        self._input_report_char.add_subscribed_clients_changed(_on_subscribers_changed)
        log.info("HID Service created with all characteristics.")

    # ---- Internal: Battery Service ----

    async def _create_battery_service(self) -> None:
        """Create a simple Battery Service reporting 100%. Some hosts require this."""
        try:
            result = await GattServiceProvider.create_async(UUID_BATTERY_SERVICE)
            if result.service_provider is None:
                log.warning(f"Battery service creation failed: {result.error}. Continuing without it.")
                return
            self._battery_provider = result.service_provider
            service = self._battery_provider.service

            params = GattLocalCharacteristicParameters()
            params.characteristic_properties = (
                GattCharacteristicProperties.READ |
                GattCharacteristicProperties.NOTIFY
            )
            params.read_protection_level = GattProtectionLevel.PLAIN
            params.static_value = _write_bytes(bytes([100]))  # 100%

            r = await service.create_characteristic_async(UUID_BATTERY_LEVEL, params)
            if r.characteristic is None:
                log.warning("Could not create Battery Level characteristic.")
                return

            # Start advertising battery service too
            adv_params = GattServiceProviderAdvertisingParameters()
            adv_params.is_discoverable = True
            adv_params.is_connectable = True
            self._battery_provider.start_advertising_with_parameters(adv_params)
            log.debug("Battery Service created and advertising.")
        except Exception as e:
            log.warning(f"Battery service setup failed (non-fatal): {e}")

    # ---- Internal: Advertising ----

    def _start_advertising(self) -> None:
        if self._hid_provider is None:
            raise RuntimeError("HID service provider not initialized.")
        adv_params = GattServiceProviderAdvertisingParameters()
        adv_params.is_discoverable = True
        adv_params.is_connectable = True
        self._hid_provider.start_advertising_with_parameters(adv_params)
        self._is_advertising = True
        log.info("HID Service advertising started.")
