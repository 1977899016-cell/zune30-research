"""Actual distributed ARM helpers, synthetic source regions and mocked OS APIs."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from native_fixture import Replay, NK, NOR, DISK

class NativeBackupTests(unittest.TestCase):
    def test_nk_double_read_and_owned_output(self):
        result = Replay('backup-nk').run()
        self.assertEqual((result.state, result.error), (2, 0))
        self.assertEqual(result.body, NK)
        again = Replay('backup-nk', initial=result.payload).run()
        self.assertFalse(again.writes)

    def test_wrong_owner_and_change_between_opens_never_write(self):
        for role in ('backup-nk', 'backup-raw'):
            for case in ('wrong_token', 'changed_between_opens'):
                result = Replay(role, case).run()
                self.assertFalse(result.writes)
                self.assertFalse(result.ioctls)

    def test_unstable_nk_does_not_produce_completed_backup(self):
        result = Replay('backup-nk', 'unstable_nk').run()
        self.assertEqual((result.state, result.error), (3, 13))

    def test_raw_backup_exact_sources_restores_privilege_and_only_reads_disk(self):
        result = Replay('backup-raw').run()
        self.assertEqual((result.state, result.error), (2, 0))
        self.assertEqual(result.body[64:], NOR + DISK)
        self.assertEqual((result.permissions, result.mode), (0x21, 0))
        self.assertEqual((result.maps, result.unmaps), (1, 1))
        self.assertEqual(len(result.ioctls), 64)
        again = Replay('backup-raw', initial=result.payload).run()
        self.assertFalse(again.writes or again.ioctls)

    def test_raw_guard_and_unstable_sources_fail_without_success(self):
        for case, error in [('untrusted', 19), ('bad_guard', 21), ('unstable_nor', 24), ('unstable_disk', 31)]:
            result = Replay('backup-raw', case).run()
            self.assertEqual((result.state, result.error), (3, error))
            self.assertEqual((result.permissions, result.mode), (0x21, 0))
            if case in ('untrusted', 'bad_guard'): self.assertFalse(result.maps or result.ioctls)

if __name__ == '__main__': unittest.main()
