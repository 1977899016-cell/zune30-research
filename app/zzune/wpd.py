"""Windows inbox WPD transport. Import COM only inside an explicit worker action.

No device is opened on import. A read-only instance rejects all write operations.
No automatic authentication, USB reset, firmware retry or process termination.
"""
import ctypes
import os
from pathlib import Path
import struct
from .protocol import MtpError

COMMON = '{F0422A9C-5DC8-4440-B5BD-5DF28835658A}'
MTP = '{4D545058-1A2E-4106-A357-771E0819FC56}'

def modules():
    import comtypes
    import comtypes.client
    cache = Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'ZZAudio' / 'ZuneAssistant' / 'comcache'
    cache.mkdir(parents=True, exist_ok=True)
    comtypes.client.gen_dir = str(cache)
    api = comtypes.client.GetModule('PortableDeviceApi.dll')
    types = comtypes.client.GetModule('PortableDeviceTypes.dll')
    return comtypes, api, types

def inventory():
    comtypes, _, _ = modules()
    class Interface(ctypes.Structure):
        _fields_ = [('size', ctypes.c_ulong), ('guid', comtypes.GUID),
                    ('flags', ctypes.c_ulong), ('reserved', ctypes.c_size_t)]
    api = ctypes.WinDLL('setupapi', use_last_error=True)
    api.SetupDiGetClassDevsW.argtypes = [ctypes.POINTER(comtypes.GUID), ctypes.c_wchar_p, ctypes.c_void_p, ctypes.c_ulong]
    api.SetupDiGetClassDevsW.restype = ctypes.c_void_p
    api.SetupDiEnumDeviceInterfaces.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.POINTER(comtypes.GUID), ctypes.c_ulong, ctypes.POINTER(Interface)]
    api.SetupDiGetDeviceInterfaceDetailW.argtypes = [ctypes.c_void_p, ctypes.POINTER(Interface), ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong), ctypes.c_void_p]
    api.SetupDiDestroyDeviceInfoList.argtypes = [ctypes.c_void_p]
    guid = comtypes.GUID('{6AC27878-A6FA-4155-BA85-F98F491D4F33}')
    handle = api.SetupDiGetClassDevsW(ctypes.byref(guid), None, None, 0x12)
    if handle == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    result = []
    try:
        for index in range(256):
            interface = Interface(); interface.size = ctypes.sizeof(interface)
            if not api.SetupDiEnumDeviceInterfaces(handle, None, ctypes.byref(guid), index, ctypes.byref(interface)):
                if ctypes.get_last_error() == 259:
                    break
                raise ctypes.WinError(ctypes.get_last_error())
            required = ctypes.c_ulong()
            api.SetupDiGetDeviceInterfaceDetailW(handle, ctypes.byref(interface), None, 0, ctypes.byref(required), None)
            if not 8 <= required.value <= 65536:
                raise ValueError('WPD 接口路径长度无效')
            buffer = ctypes.create_string_buffer(required.value)
            ctypes.c_ulong.from_buffer(buffer).value = 8 if ctypes.sizeof(ctypes.c_void_p) == 8 else 6
            if not api.SetupDiGetDeviceInterfaceDetailW(handle, ctypes.byref(interface), buffer, required.value, ctypes.byref(required), None):
                raise ctypes.WinError(ctypes.get_last_error())
            name = ctypes.wstring_at(ctypes.addressof(buffer) + 4)
            if any(marker in name.lower() for marker in ('vid_045e&pid_0710', 'vid_1209&pid_0001')):
                result.append(name)
        else:
            raise ValueError('WPD 接口数量超出限制')
    finally:
        api.SetupDiDestroyDeviceInfoList(handle)
    return result

class WpdTransport:
    def __init__(self, device_id, writable=False):
        self.comtypes, self.api, self.types = modules()
        self.writable = writable
        self.params = []
        values = self.values()
        # Windows requires GENERIC_READ | GENERIC_WRITE for MTP pass-through
        # SendCommand, including read-only GetDeviceInfo. Device write authority
        # remains controlled by self.writable and operation()'s allowlist below.
        values.SetUnsignedIntegerValue(self.key('{204D9F0C-2292-4080-9F42-40664E70F859}', 9), 0xc0000000)
        self.dev = self.comtypes.client.CreateObject(self.api.PortableDevice, interface=self.api.IPortableDevice)
        self.dev.Open(device_id, values)

    def key(self, guid, pid):
        return self.api._tagpropertykey(self.comtypes.GUID(guid), pid)

    def values(self):
        return self.comtypes.client.CreateObject(self.types.PortableDeviceValues, interface=self.api.IPortableDeviceValues)

    def request(self, command, values=()):
        query = self.values()
        query.SetGuidValue(self.key(COMMON, 1001), self.comtypes.GUID(MTP))
        query.SetUnsignedIntegerValue(self.key(COMMON, 1002), command)
        for pid, kind, value in values:
            key = self.key(MTP, pid)
            if kind == 'u32': query.SetUnsignedIntegerValue(key, value)
            elif kind == 'u64': query.SetUnsignedLargeIntegerValue(key, value)
            elif kind == 'str': query.SetStringValue(key, value)
            elif kind == 'buf':
                array = (ctypes.c_ubyte * len(value)).from_buffer_copy(value)
                query.SetBufferValue(key, array, len(value))
            elif kind == 'params':
                collection = self.comtypes.client.CreateObject(self.types.PortableDevicePropVariantCollection, interface=self.api.IPortableDevicePropVariantCollection)
                collection.ChangeType(19)
                for parameter in value:
                    variant = self.api.tag_inner_PROPVARIANT(); variant.vt = 19
                    ctypes.c_uint32.from_buffer(variant, 8).value = parameter
                    collection.Add(ctypes.byref(variant))
                query.SetIPortableDevicePropVariantCollectionValue(key, collection)
        response = self.dev.SendCommand(0, query)
        hr = response.GetErrorValue(self.key(COMMON, 1003)) & 0xffffffff
        if hr:
            raise RuntimeError('Windows WPD 错误 ' + hex(hr) + '（命令 ' + str(command) + '）。驱动会话暂不可用，可能有软件占用或设备尚未完成重连；请检查屏幕和官方 Zune 软件状态。')
        return response

    def code(self, response):
        self.params = []
        try:
            collection = response.GetIPortableDevicePropVariantCollectionValue(self.key(MTP, 1004))
            count = ctypes.c_ulong(); collection.GetCount(ctypes.byref(count))
            if count.value > 8: raise ValueError('MTP 参数过多')
            for index in range(count.value):
                variant = self.api.tag_inner_PROPVARIANT(); collection.GetAt(index, ctypes.byref(variant))
                self.params.append(ctypes.c_uint32.from_buffer(variant, 8).value)
        except (OSError, self.comtypes.COMError):
            pass
        code = response.GetUnsignedIntegerValue(self.key(MTP, 1003))
        if code not in (0x2001, 0xa221): raise MtpError(code)
        return code

    def operation(self, operation, params=(), data=None, read=False):
        allowed = (0x1001, 0x1007, 0x1008, 0x101b)
        if not self.writable and (operation not in allowed or data is not None or not read):
            raise ValueError('只读连接拒绝写操作')
        if operation not in (*allowed, 0x100c, 0x100d, 0x9204):
            raise ValueError('工具不允许此设备命令')
        args = [(1001, 'u32', operation), (1002, 'params', params)]
        if data is None and not read:
            return self.code(self.request(12, args))
        if data is not None: args.append((1007, 'u64', len(data)))
        response = self.request(13 if read else 14, args)
        context = response.GetStringValue(self.key(MTP, 1006))
        output = bytearray()
        try:
            if read:
                size = response.GetUnsignedLargeIntegerValue(self.key(MTP, 1007))
                if size > 1024 * 1024: raise ValueError('设备单次读取长度超出限制')
                while len(output) < size:
                    count = min(65536, size - len(output))
                    reply = self.request(15, [(1006, 'str', context), (1008, 'u32', count), (1012, 'buf', bytes(count))])
                    n = reply.GetUnsignedIntegerValue(self.key(MTP, 1009))
                    pointer, allocated = reply.GetBufferValue(self.key(MTP, 1012))
                    try:
                        if not 0 < n <= count or allocated < n: raise ValueError('设备读取长度无效')
                        output.extend(ctypes.string_at(pointer, n))
                    finally:
                        ole = ctypes.WinDLL('ole32'); ole.CoTaskMemFree.argtypes = [ctypes.c_void_p]
                        ole.CoTaskMemFree(pointer)
            else:
                offset = 0
                while offset < len(data):
                    chunk = data[offset:offset + 65536]
                    reply = self.request(16, [(1006, 'str', context), (1010, 'u32', len(chunk)), (1012, 'buf', chunk)])
                    count = reply.GetUnsignedIntegerValue(self.key(MTP, 1011))
                    if not 0 < count <= len(chunk): raise ValueError('设备写入长度无效')
                    offset += count
        finally:
            end = self.request(17, [(1006, 'str', context)])
        self.code(end)
        return bytes(output) if read else None

    def close(self):
        self.dev.Close()
