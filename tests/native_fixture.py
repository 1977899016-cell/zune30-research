"""Execute the distributed original ARM backup helpers against synthetic CE APIs."""
import struct
from pathlib import Path
import pefile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC
from zzune.engine import bound_helper, helper_manifest

STUB = 0x70000000
TOKEN = b'fixture-token-16'
OBJECT = 0x040000ee
PREFIX = '\\Hard Disk2\\Content'
PATH = PREFIX + '\\0400\\00\\ee.bin'
ALT = PREFIX + '\\0000\\00\\ee.bin'
NK = b'B000FF\n' + bytes(range(256)) * 273
NOR = bytes(range(256)) * 8192
DISK = bytes((i * 7 + 1) % 256 for i in range(256)) * 4096

class Replay:
    def __init__(self, role, case='success', initial=None):
        self.role, self.case = role, case
        row = helper_manifest()[role]
        self.capacity = row['capacity']
        self.pad = bytes(range(256)) * (self.capacity // 256)
        header = struct.pack('<16s16s8I', row['magic'].encode(), TOKEN, row['version'], self.capacity, OBJECT, 0, 0, 0, 0, 0)
        image = bound_helper(role, header)
        self.payload = bytearray(initial) if initial is not None else bytearray(header + self.pad[64:])
        if case == 'wrong_token': self.payload[16] ^= 1
        self.u = Uc(UC_ARCH_ARM, UC_MODE_ARM)
        self.u.mem_map(0x10000, 0x10000); self.u.mem_map(STUB, 0x10000)
        self.u.mem_map(0x400000, 0x30000); self.u.mem_map(0x600000, 0x20000)
        pe = pefile.PE(data=image)
        for section in pe.sections: self.u.mem_write(0x10000 + section.VirtualAddress, section.get_data())
        self.names = {}
        for index, imp in enumerate(pe.DIRECTORY_ENTRY_IMPORT[0].imports):
            address = STUB + index * 4
            self.names[address] = row['ordinals'][str(imp.ordinal)]
            self.u.mem_write(imp.address, struct.pack('<I', address))
        self.names.update({STUB+0x1000: 'PmcGetPath', STUB+0x2000: 'MmMapIoSpace', STUB+0x2004: 'MmUnmapIoSpace'})
        self.files = {ALT if case == 'low_path' else PATH: self.payload, '\\Hard Disk\\nk.bin': bytearray(NK)}
        self.handles, self.closed, self.writes, self.calls, self.reads = {}, [], [], [], {}
        self.permissions, self.mode, self.maps, self.unmaps, self.ioctls = 0x21, 0, 0, 0, []
        self.done = False
        self.u.hook_add(UC_HOOK_CODE, self.hook, begin=STUB, end=STUB+0xffff)

    def word(self, pointer): return struct.unpack('<I', self.u.mem_read(pointer, 4))[0]
    def put(self, pointer, value): self.u.mem_write(pointer, struct.pack('<I', value & 0xffffffff))
    def wide(self, pointer):
        data = bytearray()
        for index in range(520):
            char = bytes(self.u.mem_read(pointer + index*2, 2))
            if char == b'\0\0': return data.decode('utf-16-le')
            data += char
        raise AssertionError('Unbounded path')

    def ret(self, value):
        self.u.reg_write(UC_ARM_REG_R0, value & 0xffffffff)
        self.u.reg_write(UC_ARM_REG_PC, self.u.reg_read(UC_ARM_REG_LR))

    def hook(self, u, pc, size, extra):
        name = self.names[pc]; self.calls.append(name)
        a, b, c, d = [u.reg_read(r) for r in (UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_R2, UC_ARM_REG_R3)]
        sp = u.reg_read(UC_ARM_REG_SP)
        if name == 'SignalStarted': assert a == 85; self.ret(1)
        elif name == 'Sleep': self.ret(0)
        elif name == 'LoadLibraryW':
            assert self.wide(a) in ('pmcapi.dll', 'ceddk.dll'); self.ret(9 if self.wide(a) == 'pmcapi.dll' else 10)
        elif name == 'GetProcAddressW':
            label = self.wide(b)
            self.ret(STUB + {'PmcGetPath': 0x1000, 'MmMapIoSpace': 0x2000, 'MmUnmapIoSpace': 0x2004}[label])
        elif name == 'PmcGetPath':
            assert a == 4 and c == 260; u.mem_write(b, (PREFIX+'\0').encode('utf-16-le')); self.ret(0)
        elif name == 'CreateFileW':
            path = self.wide(a)
            assert self.word(sp) == 3 and path in (PATH, ALT, '\\Hard Disk\\nk.bin', 'DSK1:')
            if path == 'DSK1:':
                assert b == 0x80000000 and self.permissions == 0x21 and self.mode == 0
            else:
                assert path in (PATH, ALT) or b == 0x80000000
                assert b in (0x80000000, 0xc0000000)
            if path != 'DSK1:' and path not in self.files: self.ret(-1); return
            handle = 100 + len(self.handles); self.handles[handle] = [path, 0, b]; self.ret(handle)
        elif name == 'GetFileSize':
            self.put(b, 0); self.ret(len(self.files[self.handles[a][0]]))
        elif name == 'SetFilePointer':
            assert c == d == 0; self.handles[a][1] = b; self.ret(b)
        elif name == 'ReadFile':
            path, offset, access = self.handles[a]
            data = bytearray(self.files[path][offset:offset+c])
            key = (path, offset, c); self.reads[key] = self.reads.get(key, 0) + 1
            if self.case == 'unstable_nk' and path.endswith('nk.bin') and c > 7 and self.reads[key] % 2 == 0: data[0] ^= 1
            u.mem_write(b, bytes(data)); self.put(d, len(data)); self.handles[a][1] += len(data); self.ret(1)
        elif name == 'WriteFile':
            path, offset, access = self.handles[a]
            assert path in (PATH, ALT) and access == 0xc0000000 and offset+c <= self.capacity
            data = bytes(u.mem_read(b, c))
            self.files[path][offset:offset+c] = data; self.writes.append((offset, c))
            self.handles[a][1] += c; self.put(d, c); self.ret(1)
        elif name == 'FlushFileBuffers': self.ret(1)
        elif name == 'CloseHandle':
            self.closed.append(a)
            if self.case == 'changed_between_opens' and self.handles[a][2] == 0x80000000 and self.handles[a][0] in (PATH, ALT): self.payload[16] ^= 1
            self.ret(1)
        elif name == 'GetCurrentPermissions': self.ret(self.permissions)
        elif name == 'LocalAlloc': assert a == 0 and b == 98304; self.ret(0x600000)
        elif name == 'LocalFree': assert a == 0x600000; self.ret(0)
        elif name == 'CeGetCurrentTrust': self.ret(1 if self.case == 'untrusted' else 2)
        elif name == 'SetProcPermissions': previous = self.permissions; self.permissions = a; self.ret(previous)
        elif name == 'SetKMode': previous = self.mode; self.mode = a; self.ret(previous)
        elif name == 'MmMapIoSpace':
            assert (a, b, c, d) == (0xa0000000, 0, 0x200000, 0); self.maps += 1; self.ret(0x20000000)
        elif name == 'MmUnmapIoSpace': assert (a, b) == (0x20000000, 0x200000); self.unmaps += 1; self.ret(0)
        elif name == 'ReadProcessMemory':
            assert a == 0x42 and self.permissions == 0xffffffff and self.mode == 1
            if b == 0x88201000: data = bytearray.fromhex('00000fe11300a0e3800080e3400080e3')
            elif b == 0x882019e0: data = bytearray(struct.pack('<6I', 0x88000000, 0x80000000, 64, 0x80000000, 0xa0000000, 64))
            else:
                assert 0x20000000 <= b < b+d <= 0x20200000 and d == 32768
                data = bytearray(NOR[b-0x20000000:b-0x20000000+d])
                self.reads[b] = self.reads.get(b, 0) + 1
                if self.case == 'unstable_nor' and self.reads[b] % 2 == 0: data[0] ^= 1
            if self.case == 'bad_guard' and b == 0x88201000: data[0] ^= 1
            u.mem_write(c, bytes(data)); self.put(self.word(sp), len(data)); self.ret(1)
        elif name == 'DeviceIoControl':
            assert b == 0x75c08 and self.handles[a][0] == 'DSK1:' and d == 28
            sector, count, buffers, status, callback, pointer, length = struct.unpack('<7I', u.mem_read(c, 28))
            assert count == 64 and sector % 64 == 0 and sector+count <= 2048 and length == 32768
            assert buffers == 1 and callback == 0 and self.word(sp) == self.word(sp+4) == self.word(sp+12) == 0
            self.ioctls.append((b, sector, count))
            data = bytearray(DISK[sector*512:(sector+count)*512])
            if self.case == 'unstable_disk' and len(self.ioctls) % 2 == 0: data[0] ^= 1
            u.mem_write(pointer, bytes(data)); self.put(c+12, 0); self.ret(1)
        elif name == 'ExitThread': self.done = True; u.emu_stop()
        else: raise AssertionError(name)

    def run(self):
        self.u.reg_write(UC_ARM_REG_SP, 0x420000)
        self.u.emu_start(0x11000, 0xffffffff, timeout=20000000, count=400000000)
        assert self.done and set(self.handles) == set(self.closed)
        fields = struct.unpack_from('<8I', self.payload, 32)
        self.state, self.size, self.error, checksum = fields[3:7]
        self.body = bytes(a ^ b for a, b in zip(self.payload[64:64+self.size], self.pad[64:64+self.size]))
        if self.state in (2, 3): assert sum(self.body) & 0xffffffff == checksum
        return self
