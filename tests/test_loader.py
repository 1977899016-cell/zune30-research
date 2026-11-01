"""Execute the included ARM loader; model filesystem/GDI calls only."""
import hashlib
import struct
import unittest
from pathlib import Path

import pefile
from unicorn import Uc, UC_ARCH_ARM, UC_MODE_ARM, UC_HOOK_CODE
from unicorn.arm_const import UC_ARM_REG_R0, UC_ARM_REG_R1, UC_ARM_REG_SP, UC_ARM_REG_LR, UC_ARM_REG_PC

ROOT = Path(__file__).resolve().parents[1]
EXPECTED = 'dd2c0bf0fad44cc24a058820395b51b960a39fd662364654992144ef92df982d'
PATH = r'\Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf'


def replay(open_after=0, size=8206424, gdi_result=1):
    data = (ROOT / 'artifacts/ZCJKBoot.exe').read_bytes()
    assert hashlib.sha256(data).hexdigest() == EXPECTED
    pe = pefile.PE(data=data)
    machine = Uc(UC_ARCH_ARM, UC_MODE_ARM)
    machine.mem_map(0x10000, 0x10000)
    machine.mem_write(0x10000, pe.get_memory_mapped_image())
    machine.mem_map(0x300000, 0x10000)
    machine.mem_map(0x400000, 0x10000)
    names = ['CreateFileW', 'GetFileSize', 'CloseHandle', 'AddFontResourceW', 'Sleep', 'SignalStarted', 'ExitThread']
    imports = pe.DIRECTORY_ENTRY_IMPORT[0].imports
    assert len(imports) == len(names) and all(x.ordinal is not None for x in imports)
    mapping = {}
    for i, (name, imp) in enumerate(zip(names, imports)):
        address = 0x300000 + i * 0x100
        machine.mem_write(imp.address, struct.pack('<I', address))
        mapping[address] = name
    events, attempts, exited = [], 0, False

    def wide(address):
        values = []
        for i in range(255):
            v = struct.unpack('<H', machine.mem_read(address + 2 * i, 2))[0]
            if not v:
                return ''.join(values)
            values.append(chr(v))
        raise AssertionError('Unterminated path')

    def hook(u, pc, width, extra):
        nonlocal attempts, exited
        name = mapping.get(pc)
        if name is None:
            return
        a, b = u.reg_read(UC_ARM_REG_R0), u.reg_read(UC_ARM_REG_R1)
        events.append(name)
        result = 1
        if name == 'CreateFileW':
            assert wide(a) == PATH
            attempts += 1
            result = 7 if attempts > open_after else 0xffffffff
        elif name == 'GetFileSize':
            assert a == 7 and b == 0
            result = size
        elif name == 'CloseHandle':
            assert a == 7
        elif name == 'AddFontResourceW':
            assert wide(a) == PATH
            result = gdi_result
        elif name == 'Sleep':
            assert a == 100
        elif name == 'SignalStarted':
            assert a == 45
        elif name == 'ExitThread':
            assert a == 0 and events[-2] == 'SignalStarted'
            exited = True
            u.emu_stop()
            return
        u.reg_write(UC_ARM_REG_R0, result)
        u.reg_write(UC_ARM_REG_PC, u.reg_read(UC_ARM_REG_LR))

    machine.hook_add(UC_HOOK_CODE, hook)
    machine.reg_write(UC_ARM_REG_SP, 0x40f000)
    machine.emu_start(0x10000 + pe.OPTIONAL_HEADER.AddressOfEntryPoint, 0xffffffff, count=200000, timeout=3000000)
    assert exited
    return events, attempts


class LoaderTests(unittest.TestCase):
    def test_load_precedes_service_signal(self):
        events, attempts = replay()
        self.assertEqual(attempts, 1)
        self.assertLess(events.index('AddFontResourceW'), events.index('SignalStarted'))

    def test_missing_font_is_bounded_and_still_releases_services(self):
        events, attempts = replay(open_after=999)
        self.assertEqual(attempts, 300)
        self.assertNotIn('AddFontResourceW', events)
        self.assertEqual(events[-2:], ['SignalStarted', 'ExitThread'])

    def test_size_mismatch_does_not_load_font(self):
        events, attempts = replay(size=1234)
        self.assertEqual(attempts, 1)
        self.assertNotIn('AddFontResourceW', events)

    def test_late_file_can_be_loaded(self):
        events, attempts = replay(open_after=3)
        self.assertEqual(attempts, 4)
        self.assertEqual(events.count('AddFontResourceW'), 1)

    def test_gdi_failure_has_bounded_retries(self):
        events, attempts = replay(gdi_result=0)
        self.assertEqual(attempts, 300)
        self.assertEqual(events.count('AddFontResourceW'), 300)
        self.assertEqual(events[-2:], ['SignalStarted', 'ExitThread'])


if __name__ == '__main__':
    unittest.main()
