"""Exercise WPD access requirements without physical USB commands."""
from pathlib import Path
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from zzune.wpd import WpdTransport


class Values:
    def __init__(self): self.data = {}
    def SetUnsignedIntegerValue(self, key, value): self.data[key] = value
    def SetGuidValue(self, key, value): self.data[key] = value
    def SetStringValue(self, key, value): self.data[key] = value
    def SetIPortableDevicePropVariantCollectionValue(self, key, value): self.data[key] = value
    def GetErrorValue(self, key): return 0
    def GetStringValue(self, key): return 'read-context'
    def GetUnsignedLargeIntegerValue(self, key): return 0
    def GetIPortableDevicePropVariantCollectionValue(self, key): raise OSError('no response parameters')
    def GetUnsignedIntegerValue(self, key): return 0x2001


class Collection:
    def ChangeType(self, value): pass


class Device:
    def __init__(self): self.access = None; self.commands = []
    def Open(self, path, values):
        self.access = next(value for (guid, pid), value in values.data.items() if pid == 9)
    def SendCommand(self, flags, values):
        # MTP pass-through requires write access even for GetDeviceInfo.
        if self.access != 0xc0000000: raise PermissionError('WPD pass-through access denied')
        self.commands.append(values.data)
        return Values()
    def Close(self): pass


class WpdAccessTests(unittest.TestCase):
    def setUp(self):
        self.device = Device()
        api = SimpleNamespace(PortableDevice='device', IPortableDevice=object,
                              _tagpropertykey=lambda guid, pid: (guid, pid),
                              IPortableDeviceValues=object,
                              IPortableDevicePropVariantCollection=object)
        types = SimpleNamespace(PortableDeviceValues='values',
                                PortableDevicePropVariantCollection='collection')
        def create(kind, **kwargs):
            return self.device if kind == 'device' else Collection() if kind == 'collection' else Values()
        com = SimpleNamespace(GUID=lambda value: value, COMError=OSError,
                              client=SimpleNamespace(CreateObject=create))
        self.mock = patch('zzune.wpd.modules', return_value=(com, api, types))
        self.mock.start(); self.addCleanup(self.mock.stop)

    def test_readonly_getdeviceinfo_uses_required_host_access(self):
        transport = WpdTransport('synthetic-device', writable=False)
        self.assertEqual(transport.operation(0x1001, read=True), b'')
        self.assertEqual(self.device.access, 0xc0000000)

    def test_readonly_still_rejects_every_write_before_sendcommand(self):
        transport = WpdTransport('synthetic-device', writable=False)
        for op, kwargs in [(0x100c, {'data': b'upload'}), (0x100d, {'data': b'data'}),
                           (0x9204, {}), (0x1001, {}), (0x1001, {'read': True, 'data': b'x'})]:
            with self.subTest(op=op, kwargs=kwargs):
                with self.assertRaises(ValueError): transport.operation(op, **kwargs)
        self.assertEqual(self.device.commands, [])

    def test_writable_connection_can_submit_explicit_allowed_command(self):
        transport = WpdTransport('synthetic-device', writable=True)
        self.assertEqual(transport.operation(0x9204), 0x2001)
        self.assertEqual(len(self.device.commands), 1)


if __name__ == '__main__': unittest.main()
