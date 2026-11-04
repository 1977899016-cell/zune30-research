"""Temporary launcher suppression lifecycle, with no real process operations."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from zzune.launcher import LauncherPause


class Lease:
    def __init__(self): self.held = False
    def acquire(self): self.held = True
    def release(self): self.held = False


class Backend:
    def __init__(self):
        self.processes = [(7, 'known-launcher.exe')]
        self.calls = []
        self.hash = 'original-file-hash'
    def known(self, path): return path == 'known-launcher.exe'
    def entries(self): return list(self.processes)
    def fingerprint(self, path): return self.hash
    def stop(self, pid, path): self.calls.append(('stop', pid, path)); self.processes.remove((pid, path))
    def start(self, path): self.calls.append(('start', path)); self.processes.append((8, path))


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.backend, self.lease = Backend(), Lease()
        self.guard = LauncherPause(self.root, backend=self.backend, lease=self.lease)

    def test_stops_only_launcher_and_restores_once(self):
        self.guard.pause(); self.guard.pause()
        self.assertEqual(self.backend.calls, [('stop', 7, 'known-launcher.exe')])
        self.assertTrue(self.lease.held)
        self.guard.restore(); self.guard.restore()
        self.assertEqual(self.backend.calls[-1], ('start', 'known-launcher.exe'))
        self.assertEqual(len(self.backend.calls), 2)
        self.assertFalse(self.lease.held)

    def test_originally_absent_launcher_stays_absent(self):
        self.backend.processes.clear()
        self.guard.pause(); self.guard.restore()
        self.assertEqual(self.backend.calls, [])

    def test_unknown_path_is_never_stopped(self):
        self.backend.processes.append((99, 'unknown-launcher.exe'))
        with self.assertRaisesRegex(ValueError, '路径'):
            self.guard.pause()
        self.assertEqual(self.backend.calls, [])
        self.assertFalse(self.lease.held)

    def test_changed_executable_is_not_restarted(self):
        self.guard.pause(); self.backend.hash = 'changed-file'
        with self.assertRaisesRegex(ValueError, '改变'):
            self.guard.restore()
        self.assertEqual(self.backend.calls, [('stop', 7, 'known-launcher.exe')])
        self.assertFalse(self.lease.held)
        self.assertTrue(self.guard.path.exists())

    def test_previous_crash_journal_is_adopted(self):
        self.guard.pause()
        self.lease.release()  # Simulate OS releasing the process mutex after a crash.
        next_guard = LauncherPause(self.root, backend=self.backend, lease=Lease())
        next_guard.pause(); next_guard.restore()
        self.assertEqual(self.backend.calls, [('stop', 7, 'known-launcher.exe'), ('start', 'known-launcher.exe')])

    def test_manual_launcher_restart_is_not_duplicated(self):
        self.guard.pause(); self.backend.processes.append((9, 'known-launcher.exe'))
        self.guard.restore()
        self.assertEqual(self.backend.calls, [('stop', 7, 'known-launcher.exe')])

    def test_changed_crash_record_blocks_before_stopping_more_processes(self):
        self.guard.pause(); self.lease.release()
        self.backend.hash = 'changed-file'
        self.backend.processes.append((9, 'known-launcher.exe'))
        next_guard = LauncherPause(self.root, backend=self.backend, lease=Lease())
        with self.assertRaisesRegex(ValueError, '改变'):
            next_guard.pause()
        self.assertEqual(self.backend.calls, [('stop', 7, 'known-launcher.exe')])


if __name__ == '__main__': unittest.main()
