"""Mocked lifecycle tests; these do not exercise a Bluetooth adapter."""
import asyncio
import importlib
import os
import sys
import types
import unittest


class _Writer:
    def __init__(self):
        self.data = b""

    def write_bytes(self, data):
        self.data = bytes(data)

    def detach_buffer(self):
        return self.data


class _Characteristic:
    def __init__(self, params):
        self.params = params
        self.subscribed_clients = types.SimpleNamespace(size=1)
        self.notifications = []
        self.fail_notify = False
        self.handler = None

    async def create_descriptor_async(self, uuid, params):
        return types.SimpleNamespace(descriptor=object())

    def add_subscribed_clients_changed(self, handler):
        self.handler = handler

    async def notify_value_async(self, buffer):
        if self.fail_notify:
            raise RuntimeError("link lost")
        self.notifications.append(buffer)


class _Service:
    def __init__(self):
        self.characteristics = {}

    async def create_characteristic_async(self, uuid, params):
        characteristic = _Characteristic(params)
        self.characteristics[uuid] = characteristic
        return types.SimpleNamespace(characteristic=characteristic)


class _Provider:
    def __init__(self):
        self.service = _Service()
        self.advertising = False

    def start_advertising_with_parameters(self, params):
        self.advertising = True

    def stop_advertising(self):
        self.advertising = False


class _GattServiceProvider:
    @classmethod
    async def create_async(cls, uuid):
        return types.SimpleNamespace(service_provider=_Provider(), error=None)


class _Parameters:
    pass


class _Protection:
    PLAIN = "plain"
    ENCRYPTION_AND_AUTHENTICATION_REQUIRED = "authenticated-encrypted"


def _install_winrt_stubs():
    packages = {
        "winrt": types.ModuleType("winrt"),
        "winrt.windows": types.ModuleType("winrt.windows"),
        "winrt.windows.devices": types.ModuleType("winrt.windows.devices"),
        "winrt.windows.devices.bluetooth": types.ModuleType("winrt.windows.devices.bluetooth"),
        "winrt.windows.devices.bluetooth.genericattributeprofile": types.ModuleType(
            "winrt.windows.devices.bluetooth.genericattributeprofile"
        ),
        "winrt.windows.storage": types.ModuleType("winrt.windows.storage"),
        "winrt.windows.storage.streams": types.ModuleType("winrt.windows.storage.streams"),
    }
    gatt = packages["winrt.windows.devices.bluetooth.genericattributeprofile"]
    gatt.GattServiceProvider = _GattServiceProvider
    gatt.GattServiceProviderAdvertisingParameters = _Parameters
    gatt.GattLocalCharacteristicParameters = _Parameters
    gatt.GattLocalDescriptorParameters = _Parameters
    gatt.GattCharacteristicProperties = types.SimpleNamespace(READ=1, NOTIFY=2, WRITE_WITHOUT_RESPONSE=4)
    gatt.GattProtectionLevel = _Protection
    bluetooth = packages["winrt.windows.devices.bluetooth"]
    bluetooth.BluetoothAdapter = object
    bluetooth.BluetoothError = RuntimeError
    packages["winrt.windows.storage.streams"].DataWriter = _Writer
    sys.modules.update(packages)


class TestBleHidService(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        _install_winrt_stubs()
        sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src")))
        sys.modules.pop("ble_hid_service", None)
        cls.module = importlib.import_module("ble_hid_service")

    async def test_hid_characteristics_require_authenticated_encryption(self):
        service = self.module.BleHidService()
        await service._create_hid_service()
        characteristics = service._hid_provider.service.characteristics
        protected = (
            self.module.UUID_HID_INFORMATION,
            self.module.UUID_REPORT_MAP,
            self.module.UUID_HID_CONTROL_POINT,
            self.module.UUID_PROTOCOL_MODE,
            self.module.UUID_REPORT,
        )
        for uuid in protected:
            params = characteristics[uuid].params
            levels = (getattr(params, "read_protection_level", None), getattr(params, "write_protection_level", None))
            self.assertIn(_Protection.ENCRYPTION_AND_AUTHENTICATION_REQUIRED, levels)

    async def test_notification_failure_and_disconnect_are_safe(self):
        service = self.module.BleHidService()
        await service._create_hid_service()
        characteristic = service._input_report_char
        self.assertTrue(await service.send_report(b"\0" * 8))
        characteristic.fail_notify = True
        self.assertFalse(await service.send_report(b"\0" * 8))
        characteristic.subscribed_clients = types.SimpleNamespace(size=0)
        self.assertFalse(await service.send_report(b"\0" * 8))
        with self.assertRaises(ValueError):
            await service.send_report(b"short")

