"""Real GUI action methods, with desktop process launch and widgets replaced."""
from pathlib import Path
import io
import queue
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'app'))
from zzune.gui import Window


class GuiLauncherTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(); self.addCleanup(self.temporary.cleanup)
        self.window = object.__new__(Window)
        self.window.busy = self.window.demo = False
        self.window.launcher_pause = Mock()
        self.window.folder = Path(self.temporary.name)
        self.window.backup_root = self.window.folder / 'Backups'
        self.window.current = {'serial': 'SYNTHETIC-DEVICE-A'}
        self.window.events = queue.Queue()
        self.window.status = Mock()
        self.window.bar = {}
        self.window.update_controls = Mock()
        self.window.root = Mock()

    def test_first_action_pauses_launcher_and_worker_defers_restore_to_GUI(self):
        process = SimpleNamespace(poll=lambda: 0, stderr=io.StringIO(''), wait=lambda: 0)
        thread = lambda target, daemon: SimpleNamespace(start=target)
        with patch('zzune.gui.subprocess.Popen', return_value=process) as launch, patch('zzune.gui.threading.Thread', side_effect=thread):
            self.window.start('inspect')
        self.window.launcher_pause.pause.assert_called_once()
        self.window.launcher_pause.restore.assert_not_called()
        self.assertIn('--launcher-parent', launch.call_args.args[0])
        self.window.busy = False
        self.window.close()
        self.window.launcher_pause.restore.assert_called_once()
        self.window.root.destroy.assert_called_once()

    def test_pause_failure_prevents_worker_start(self):
        self.window.launcher_pause.pause.side_effect = RuntimeError('synthetic host failure')
        with patch('zzune.gui.messagebox.showerror'), patch('zzune.gui.subprocess.Popen') as launch:
            self.window.start('backup')
        launch.assert_not_called()
        self.assertFalse(self.window.busy)

    def test_demo_never_pauses_host_launcher(self):
        self.window.demo = True
        self.window.start('inspect')
        self.window.launcher_pause.pause.assert_not_called()


if __name__ == '__main__': unittest.main()
