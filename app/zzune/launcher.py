"""Pause only the known ZuneLauncher process, then restore its prior state.

Does not edit startup registration, stop services or close the Zune main app.
A private journal survives an assistant crash; Windows logon startup is unchanged.
"""
import csv
import ctypes
import hashlib
import os
from pathlib import Path
import subprocess
from .storage import atomic_json, read_json


class WindowsLease:
    def acquire(self):
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, ctypes.c_bool, ctypes.c_wchar_p]
        self.kernel.CreateMutexW.restype = ctypes.c_void_p
        self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        self.kernel.ReleaseMutex.argtypes = [ctypes.c_void_p]
        self.handle = self.kernel.CreateMutexW(None, True, 'Local\\ZZAudio-ZuneAssistant-LauncherPause')
        if not self.handle: raise ctypes.WinError(ctypes.get_last_error())
        if ctypes.get_last_error() == 183:
            self.kernel.CloseHandle(self.handle); self.handle = None
            raise RuntimeError('另一个助手窗口或任务正在管理 Zune 自动启动，请使用原来的窗口。')

    def release(self):
        if getattr(self, 'handle', None):
            self.kernel.ReleaseMutex(self.handle); self.kernel.CloseHandle(self.handle)
            self.handle = None


class WindowsLauncher:
    def __init__(self):
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.OpenProcess.argtypes = [ctypes.c_ulong, ctypes.c_bool, ctypes.c_ulong]
        self.kernel.OpenProcess.restype = ctypes.c_void_p
        self.kernel.CloseHandle.argtypes = [ctypes.c_void_p]
        self.kernel.QueryFullProcessImageNameW.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.c_wchar_p, ctypes.POINTER(ctypes.c_ulong)]
        self.kernel.TerminateProcess.argtypes = [ctypes.c_void_p, ctypes.c_uint]
        self.kernel.WaitForSingleObject.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        self.kernel.ProcessIdToSessionId.argtypes = [ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
        self.session = self.session_id(os.getpid())
        self.paths = {self.normal(Path(os.environ[name]) / 'Zune/ZuneLauncher.exe')
                      for name in ('ProgramFiles', 'ProgramFiles(x86)', 'ProgramW6432') if os.environ.get(name)}

    def normal(self, path): return os.path.normcase(str(Path(path).resolve()))
    def known(self, path): return self.normal(path) in self.paths and Path(path).is_file()
    def fingerprint(self, path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()

    def session_id(self, pid):
        value = ctypes.c_ulong()
        if not self.kernel.ProcessIdToSessionId(pid, ctypes.byref(value)):
            raise ctypes.WinError(ctypes.get_last_error())
        return value.value

    def image(self, handle):
        value = ctypes.create_unicode_buffer(32768); size = ctypes.c_ulong(len(value))
        if not self.kernel.QueryFullProcessImageNameW(handle, 0, value, ctypes.byref(size)):
            raise ctypes.WinError(ctypes.get_last_error())
        return str(Path(value.value).resolve())

    def entries(self):
        result = subprocess.run([str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'System32/tasklist.exe'),
                                 '/FI', 'IMAGENAME eq ZuneLauncher.exe', '/FO', 'CSV', '/NH'],
                                capture_output=True, timeout=10, check=True,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        entries = []
        for row in csv.reader(result.stdout.decode('ascii', errors='replace').splitlines()):
            if not row or row[0].lower() != 'zunelauncher.exe': continue
            pid = int(row[1])
            try:
                if self.session_id(pid) != self.session: continue
                handle = self.kernel.OpenProcess(0x1000, False, pid)
                if not handle: raise ctypes.WinError(ctypes.get_last_error())
                try: entries.append((pid, self.image(handle)))
                finally: self.kernel.CloseHandle(handle)
            except OSError as exc:
                if getattr(exc, 'winerror', None) not in (87, 1168): raise
        return entries

    def stop(self, pid, path):
        # Query and terminate through the same handle to avoid PID reuse races.
        handle = self.kernel.OpenProcess(0x1000 | 0x100000 | 1, False, pid)
        if not handle:
            error = ctypes.get_last_error()
            if error in (87, 1168): return
            raise ctypes.WinError(error)
        try:
            if self.session_id(pid) != self.session or self.normal(self.image(handle)) != self.normal(path) or not self.known(path):
                raise ValueError('启动器进程身份或路径已改变，未关闭它')
            if not self.kernel.TerminateProcess(handle, 0): raise ctypes.WinError(ctypes.get_last_error())
            if self.kernel.WaitForSingleObject(handle, 5000) != 0: raise RuntimeError('等待 ZuneLauncher 退出超时')
        finally:
            self.kernel.CloseHandle(handle)

    def start(self, path):
        if not self.known(path): raise ValueError('启动器路径不受支持，未执行')
        subprocess.Popen([str(path)], creationflags=subprocess.CREATE_NO_WINDOW,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class LauncherPause:
    def __init__(self, folder, progress=lambda *_: None, backend=None, lease=None):
        self.path = Path(folder) / 'launcher-pause.PRIVATE.json'
        self.backend = backend if backend is not None else WindowsLauncher()
        self.lease = lease if lease is not None else WindowsLease()
        self.progress = progress
        self.active = False
        self.restore_paths = {}

    def pause(self):
        if self.active: return
        self.lease.acquire()
        try:
            previous = read_json(self.path, {'schema': 1, 'restore_paths': {}})
            if previous.get('schema') != 1 or not isinstance(previous.get('restore_paths'), dict):
                raise ValueError('启动器恢复记录无效，请保留日志')
            targets = self.backend.entries()
            planned = dict(previous['restore_paths'])
            for path in planned:
                if not self.backend.known(path): raise ValueError('恢复记录中的启动器路径不受支持')
                if self.backend.fingerprint(path) != planned[path]: raise ValueError('恢复记录中的启动器文件已改变，未关闭它')
            for pid, path in targets:
                if not self.backend.known(path): raise ValueError('启动器路径不受支持，未关闭未知程序')
                planned.setdefault(path, self.backend.fingerprint(path))
            self.restore_paths = planned
            atomic_json(self.path, {'schema': 1, 'restore_paths': planned})
            self.active = True
            for pid, path in targets: self.backend.stop(pid, path)
            self.progress('已暂停官方 Zune 自动启动器；本任务结束后恢复。已打开的 Zune 主程序仍需先完成同步再退出。', None)
        except Exception:
            if self.active: self.restore()
            else: self.lease.release()
            raise

    def restore(self):
        if not self.active: return
        try:
            running = {os.path.normcase(path) for _, path in self.backend.entries()}
            for path, fingerprint in self.restore_paths.items():
                if not self.backend.known(path) or self.backend.fingerprint(path) != fingerprint:
                    raise ValueError('启动器文件已改变，未执行；恢复记录已保留')
                if os.path.normcase(path) not in running: self.backend.start(path)
            self.path.unlink(missing_ok=True)
        finally:
            self.active = False
            self.lease.release()
