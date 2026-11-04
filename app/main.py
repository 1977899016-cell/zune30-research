"""ZZ AUDIO Zune 30 Upgrade Assistant. Default launch is a local GUI, no USB I/O."""
import argparse
import ctypes
import json
import os
from pathlib import Path
import sys

IPC_FILE = None

def emit(value):
    line = json.dumps(value, ensure_ascii=False)
    if IPC_FILE:
        with IPC_FILE.open('a', encoding='utf-8') as stream:
            stream.write(line + '\n'); stream.flush()
    if sys.stdout is not None:
        print(line, flush=True)

def base_folder():
    return Path(os.environ.get('LOCALAPPDATA', Path.home())) / 'ZZAudio' / 'ZuneAssistant'

def worker(action, serial, source, root, launcher_parent=False):
    if os.name != 'nt': raise RuntimeError('设备功能仅支持 Windows')
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
    kernel.CreateMutexW.restype = ctypes.c_void_p
    kernel.CloseHandle.argtypes = [ctypes.c_void_p]
    mutex = kernel.CreateMutexW(None, True, 'Local\\ZZAudio-ZuneAssistant-DeviceOperation')
    if not mutex or ctypes.get_last_error() == 183:
        if mutex: kernel.CloseHandle(mutex)
        raise RuntimeError('另一个 Zune 工具任务仍在运行，请勿同时操作')
    launcher_pause = None
    try:
        from zzune.engine import Assistant
        def progress(message, percent):
            emit({'event': 'progress', 'message': message, 'percent': percent})
        if not launcher_parent and action != 'prepare':
            from zzune.launcher import LauncherPause
            launcher_pause = LauncherPause(base_folder(), progress)
            launcher_pause.pause()
        assistant = Assistant(root, progress)
        if action == 'inspect': result = assistant.inspect()
        elif action == 'backup': result = assistant.backup(serial)
        elif action == 'prepare': result = assistant.prepare(serial, source)
        elif action == 'upgrade': result = assistant.upgrade(serial)
        elif action == 'restore': result = assistant.restore(serial)
        else: raise ValueError('未知操作')
        emit({'event': 'result', 'result': result})
        return 0
    finally:
        try:
            if launcher_pause: launcher_pause.restore()
        finally:
            kernel.CloseHandle(mutex)

def main():
    global IPC_FILE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--worker', choices=['inspect', 'backup', 'prepare', 'upgrade', 'restore'])
    parser.add_argument('--serial', default='')
    parser.add_argument('--source', default='')
    parser.add_argument('--backup-root', type=Path)
    parser.add_argument('--self-test', action='store_true')
    parser.add_argument('--demo', action='store_true', help='Visual preview only; no device operations')
    parser.add_argument('--ipc-file', type=Path, help='Private local JSONL for the GUI/worker; no network transport')
    parser.add_argument('--launcher-parent', action='store_true', help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.ipc_file:
        args.ipc_file.parent.mkdir(parents=True, exist_ok=True)
        with args.ipc_file.open('x', encoding='utf-8'): pass
        IPC_FILE = args.ipc_file
    if args.worker:
        if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
        try:
            return worker(args.worker, args.serial, args.source, args.backup_root or base_folder() / 'Backups', args.launcher_parent)
        except Exception as exc:
            emit({'event': 'error', 'message': str(exc)})
            return 1
    from zzune.gui import Window
    if args.self_test:
        import tempfile
        with tempfile.TemporaryDirectory(prefix='zzune-ui-test-') as temporary:
            window = Window(Path(temporary), demo=False)
            window.root.withdraw(); window.root.update()
            assert not window.busy
            assert not window.upgrade_button.instate(['!disabled'])
            assert not window.backup_button.instate(['!disabled'])
            assert window.inspect_button.instate(['!disabled'])
            from zzune.engine import helper_manifest, neutral_helper
            assert len(helper_manifest()) == 3 and len(neutral_helper()) == 2048
            from runtime import assemble
            assert len(assemble(bytes(65536), b'fixture-token-16')) == 1700
            from zzune.engine import BUNDLE
            from ce_lzx import load_decoder, encode
            fixture_data = b'ZZAudio offline codec fixture' * 300
            encode(fixture_data, load_decoder(BUNDLE/'app/vendor'), Path(os.environ.get('WINDIR', 'C:/Windows'))/'System32/makecab.exe')
            from zzune.wpd import modules, WpdTransport
            if os.name == 'nt':
                comtypes, api, types = modules()
                fixture = object.__new__(WpdTransport)
                fixture.comtypes, fixture.api, fixture.types = comtypes, api, types
                values = fixture.values()
                values.SetUnsignedIntegerValue(fixture.key('{F0422A9C-5DC8-4440-B5BD-5DF28835658A}', 1002), 12)
                # Only local COM value objects: no enumeration/Open/USB commands.
            window.root.destroy()
            emit({'gui_started': True, 'unsafe_actions_disabled_by_default': True,
                              'assets_valid': True, 'COM_typelibs_loaded': os.name == 'nt',
                              'ARM_assembler_and_CE_codec_checked': True,
                              'physical_device_operations': False})
            return 0
    window = Window(base_folder(), demo=args.demo)
    try:
        window.root.mainloop()
    finally:
        window.launcher_pause.restore()
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
