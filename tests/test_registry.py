"""Startup deadlock regression and offline registry preservation checks."""
import sys
import struct
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from prepare_registry import MAGIC, key_record, value, prepare, values, init_graph, records, update_key


def fixture(extra=b''):
    body = key_record(2, 'init') + value('Launch20', 'device.exe')
    body += value('Launch30', 'gwes.exe') + value('Depend30', struct.pack('<H', 20), 3)
    body += value('Launch60', 'services.exe') + value('Depend60', struct.pack('<H', 20), 3)
    body += extra + key_record(2, r'Software\Unrelated') + value('KeepMe', b'\x12\x34\x56\x78', 4)
    return MAGIC + struct.pack('<I', len(body) + 8) + body


class RegistryTests(unittest.TestCase):
    def test_original_boot_graph_remains_reachable(self):
        result, graph = prepare(fixture())
        self.assertTrue(graph['passed'])
        self.assertEqual(graph['launch_order'], [20, 30, 45, 60])
        self.assertEqual(graph['dependencies'][45], [30])
        self.assertEqual(graph['dependencies'][60], [20, 45])
        self.assertEqual(values(result)[2, r'software\unrelated', 'keepme'], (4, b'\x12\x34\x56\x78'))

    def test_exact_real_failure_pattern_is_detected(self):
        good, _ = prepare(fixture())
        failed = update_key(good, 'init', {'depend45': value('Depend45', struct.pack('<HH', 30, 60), 3)})
        graph = init_graph(failed)
        self.assertFalse(graph['passed'])
        self.assertEqual(graph['blocked']['45'], [60])
        self.assertEqual(graph['blocked']['60'], [45])

    def test_other_launch45_is_not_overwritten(self):
        with self.assertRaisesRegex(ValueError, 'another program'):
            prepare(fixture(value('Launch45', r'\Windows\Other.exe')))

    def test_repeated_offline_preparation_is_idempotent(self):
        first, _ = prepare(fixture())
        second, _ = prepare(first)
        self.assertEqual(first, second)

    def test_bad_length_and_truncated_record_are_rejected(self):
        for data in (fixture()[:-1], b'not a registry', fixture() + b'x'):
            with self.assertRaises(ValueError):
                records(data)

    def test_custom_family_and_three_faces(self):
        result, _ = prepare(fixture(), 'My Licensed Font')
        rows = [r for r in records(result) if r['kind'] == 2 and 'fontlink' in r['key'].lower()]
        self.assertEqual(len(rows), 3)
        self.assertTrue(all('My Licensed Font' in r['data'].decode('utf-16-le') for r in rows))

    def test_missing_prerequisite_is_rejected(self):
        blob = fixture().replace('Launch30'.encode('utf-16-le'), 'Launch31'.encode('utf-16-le'))
        with self.assertRaisesRegex(ValueError, 'launch entry missing'):
            prepare(blob)


if __name__ == '__main__':
    unittest.main()
