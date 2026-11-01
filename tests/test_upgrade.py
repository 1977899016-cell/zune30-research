"""Portable upgrade regressions use synthetic bytes, never a real device vault."""
import hashlib
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools' / 'upgrade'))
from ce_bin import parse, rebuild
from runtime import REGIONS, assemble
from check_backups import check
from build_upgrade import patch

def container(address=0x88200000, payload=b'fixture', span=0x1000, entry=0x88200000):
    return (b'B000FF\n' + struct.pack('<II', 0x88200000, span)
            + struct.pack('<III', address, len(payload), sum(payload)) + payload
            + struct.pack('<III', 0, entry, 0))

class UpgradeTests(unittest.TestCase):
    def test_container_roundtrip_and_appended_rom(self):
        original = parse(container())
        flat = original.flatten() + b'new ROM bytes'
        rebuilt = parse(rebuild(original, flat))
        self.assertEqual(rebuilt.flatten(), flat)
        self.assertEqual(len(rebuilt.records), 2)

    def test_damaged_payload_rejected(self):
        data = bytearray(container())
        data[27] ^= 1
        with self.assertRaisesRegex(ValueError, 'checksum'):
            parse(data)

    def test_truncation_terminal_and_trailing_data_rejected(self):
        for data in [container()[:-1], container() + b'x', container(entry=0x90000000)]:
            with self.assertRaises(ValueError):
                parse(data)

    def test_overlap_rejected_even_with_valid_payload_checksums(self):
        original = container()
        extra = struct.pack('<III', 0x88200001, 3, sum(b'abc')) + b'abc'
        with self.assertRaisesRegex(ValueError, 'Overlapping'):
            parse(original[:-12] + extra + original[-12:])

    def test_untrusted_ranges_rejected_before_large_allocation(self):
        for data in [container(span=0xffffffff), container(address=0x90000000)]:
            with self.assertRaises(ValueError):
                parse(data)

    def test_38_field_map_is_bounded_disjoint_and_excludes_certificate(self):
        self.assertEqual(len(REGIONS), 38)
        self.assertTrue(all(0x3c0 <= offset < offset + size <= 65536 and size % 8 == 0
                            for offset, size in REGIONS))
        for (offset, size), (other, _) in zip(REGIONS, REGIONS[1:]):
            self.assertLessEqual(offset + size, other)

    def test_native_stub_uses_current_input_digest_and_nonce(self):
        legacy = bytes((index * 17 + 3) % 256 for index in range(65536))
        token = b'fixture-token-16'
        self.assertEqual(len(token), 16)
        code = assemble(legacy, token)
        self.assertEqual(len(code), 1700)
        self.assertIn(hashlib.sha1(legacy).digest() + token, code)
        changed = assemble(legacy[:-1] + bytes([legacy[-1] ^ 1]), token)
        self.assertNotEqual(code, changed)

    def test_stub_refuses_wrong_input_sizes(self):
        for legacy, token in [(b'x', bytes(16)), (bytes(65536), b'x')]:
            with self.assertRaises(ValueError):
                assemble(legacy, token)

    def test_other_stock_image_is_rejected_before_decoder_or_patch(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported stock NK hash'):
            patch(container(), bytes(65536), bytes(16), b'', None)

    def test_backup_inventory_binds_legacy_to_original_nor(self):
        nor = bytes(2 * 1024 * 1024)
        result = check(container(), nor, bytes(1024 * 1024), bytes(65536))
        self.assertTrue(result['vault_matches_original_nor_region'])
        self.assertFalse(result['backup_created_by_this_tool'])
        with self.assertRaisesRegex(ValueError, 'does not match'):
            check(container(), nor, bytes(1024 * 1024), b'x' * 65536)

if __name__ == '__main__':
    unittest.main()
