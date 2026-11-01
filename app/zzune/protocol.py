"""Strict MTP datasets shared by the real transport and offline tests."""
import struct

class Reader:
    def __init__(self, data):
        self.data, self.at = bytes(data), 0

    def take(self, count):
        if count < 0 or self.at + count > len(self.data):
            raise ValueError('设备返回的数据不完整')
        result = self.data[self.at:self.at + count]
        self.at += count
        return result

    def number(self, fmt):
        return struct.unpack(fmt, self.take(struct.calcsize(fmt)))[0]

    def string(self):
        count = self.number('<B')
        raw = self.take(count * 2)
        if count and raw[-2:] != b'\0\0':
            raise ValueError('MTP 字符串未结束')
        return raw[:-2].decode('utf-16-le') if count else ''

    def array(self):
        count = self.number('<I')
        if count > 4096:
            raise ValueError('MTP 数组过长')
        return [self.number('<H') for _ in range(count)]

def string(text):
    if not text:
        return b'\0'
    data = (text + '\0').encode('utf-16-le')
    if len(data) // 2 > 255:
        raise ValueError('MTP 名称过长')
    return bytes([len(data) // 2]) + data

def object_info(name, size, format_code):
    return (struct.pack('<IHHIH7IHII', 0x10001, format_code, 0, size, 0,
                        *([0] * 6), 0xffffffff, 0, 0, 0)
            + string(name) + string('') * 3)

def device_info(data):
    r = Reader(data)
    r.number('<H'); r.number('<I'); r.number('<H'); r.string(); r.number('<H')
    operations = r.array()
    r.array(); r.array(); r.array()
    formats = r.array()
    manufacturer, model, firmware, serial = [r.string() for _ in range(4)]
    if not serial or len(serial) > 200:
        raise ValueError('没有取得可靠的设备身份')
    return {'manufacturer': manufacturer, 'model': model, 'firmware': firmware,
            'serial': serial, 'operations': operations, 'formats': formats}

def handles(data):
    r = Reader(data)
    count = r.number('<I')
    if count > 4096 or len(data) != 4 + count * 4:
        raise ValueError('暂存队列无效')
    return [r.number('<I') for _ in range(count)]

class MtpError(RuntimeError):
    def __init__(self, code):
        self.code = code
        super().__init__('MTP 返回 ' + hex(code))
