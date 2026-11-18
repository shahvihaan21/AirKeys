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
        self.descriptors = {}
        self.mock_results = None

    async def create_descriptor_async(self, uuid, params):
        desc = types.SimpleNamespace(descriptor=object(), params=params)
        self.descriptors[uuid] = desc
        return desc

    def add_subscribed_clients_changed(self, handler):
        self.handler = handler

    async def notify_value_async(self, buffer):
        if self.fail_notify:
            raise RuntimeError("link lost")
        self.notifications.append(buffer)
        return self.mock_results


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


class _BluetoothAdapter:
    @classmethod
    async def get_default_async(cls):
        return types.SimpleNamespace(is_peripheral_role_supported=True, is_advertisement_offload_supported=True)


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
    bluetooth.BluetoothAdapter = _BluetoothAdapter
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

    async def test_send_shortcut_sends_press_and_release(self):
        service = self.module.BleHidService()
        await service._create_hid_service()
        characteristic = service._input_report_char
        characteristic.notifications.clear()
        
        result = await service.send_shortcut("ctrl+c", hold_duration=0.01)
        self.assertTrue(result)
        # Should have sent 2 notifications: press and release
        self.assertEqual(len(characteristic.notifications), 2)
        press_rep = characteristic.notifications[0]
        release_rep = characteristic.notifications[1]
        self.assertEqual(press_rep[0], 0x01)  # MOD_LEFT_CTRL
        self.assertEqual(press_rep[2], 0x06)  # 'c' scancode
        self.assertEqual(release_rep, b"\x00" * 8)

    async def test_send_text_sends_keystrokes(self):
        service = self.module.BleHidService()
        await service._create_hid_service()
        characteristic = service._input_report_char
        characteristic.notifications.clear()

        sent_count = await service.send_text("Hi", key_delay=0.001)
        self.assertEqual(sent_count, 2)
        # Each character sends press and release -> 4 notifications total
        self.assertEqual(len(characteristic.notifications), 4)

        # First char: 'H' (with Left Shift)
        press_h = characteristic.notifications[0]
        rel_h = characteristic.notifications[1]
        self.assertEqual(press_h[0], 0x02)  # MOD_LEFT_SHIFT
        self.assertEqual(press_h[2], 0x0B)  # 'h' scancode
        self.assertEqual(rel_h, b"\x00" * 8)

        # Second char: 'i'
        press_i = characteristic.notifications[2]
        rel_i = characteristic.notifications[3]
        self.assertEqual(press_i[0], 0x00)
        self.assertEqual(press_i[2], 0x0C)  # 'i' scancode
        self.assertEqual(rel_i, b"\x00" * 8)

    async def test_ensure_keys_released_flushes_zero_reports(self):
        service = self.module.BleHidService()
        await service._create_hid_service()
        characteristic = service._input_report_char
        characteristic.notifications.clear()

        result = await service.ensure_keys_released(retries=2, delay=0.001)
        self.assertTrue(result)
        self.assertEqual(len(characteristic.notifications), 2)
        for n in characteristic.notifications:
            self.assertEqual(n, b"\x00" * 8)

    async def test_delivery_statistics_and_access_denied(self):
        service = self.module.BleHidService()
        await service._create_hid_service()
        characteristic = service._input_report_char

        self.assertEqual(service.sent_reports, 0)
        self.assertEqual(service.failed_reports, 0)

        # Successful send
        self.assertTrue(await service.send_report(b"\x00" * 8))
        self.assertEqual(service.sent_reports, 1)
        self.assertEqual(service.failed_reports, 0)

        # ACCESS_DENIED from host (value 3 in GattCommunicationStatus)
        characteristic.mock_results = [types.SimpleNamespace(status=types.SimpleNamespace(value=3))]
        self.assertFalse(await service.send_report(b"\x00" * 8))
        self.assertEqual(service.sent_reports, 1)
        self.assertEqual(service.failed_reports, 1)

    async def test_descriptor_requires_authenticated_encryption(self):
        service = self.module.BleHidService()
        await service._create_hid_service()
        characteristic = service._input_report_char
        desc = characteristic.descriptors[self.module.UUID_REPORT_REFERENCE]
        self.assertEqual(desc.params.read_protection_level, _Protection.ENCRYPTION_AND_AUTHENTICATION_REQUIRED)
        self.assertEqual(desc.params.write_protection_level, _Protection.ENCRYPTION_AND_AUTHENTICATION_REQUIRED)

    async def test_startup_failure_cleans_up_providers(self):
        service = self.module.BleHidService()
        adapter_mock = types.SimpleNamespace(
            is_peripheral_role_supported=True,
            is_advertisement_offload_supported=True,
        )
        self.module.BluetoothAdapter.get_default_async = unittest.mock.AsyncMock(return_value=adapter_mock)
        service._create_battery_service = unittest.mock.AsyncMock(side_effect=RuntimeError("Battery service crash"))

        with self.assertRaises(RuntimeError):
            await service.start()

        # Both providers must be cleaned up and set to None
        self.assertIsNone(service._hid_provider)
        self.assertIsNone(service._battery_provider)
        self.assertFalse(service._is_advertising)




