"""Private, atomic local journals; a commit intent is durable before USB commit."""
from pathlib import Path
import hashlib
import json
import os
import tempfile

def digest(data):
    return hashlib.sha256(data).hexdigest()

def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='journal-', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)

def read_json(path, default=None):
    return json.loads(Path(path).read_text(encoding='utf-8')) if Path(path).exists() else default

def write_once(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError('备份文件已存在但内容不同，已停止以保留原件')
        return
    with path.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())

def same_unit(expected, observed):
    # These are the actual protocol serial strings, not a filename/USB path guess.
    if not expected or observed.get('serial') != expected:
        raise ValueError('设备身份与本次备份不符，已禁止写入')

class Session:
    def __init__(self, root, serial):
        self.root = Path(root) / ('device-' + digest(serial.encode())[:16])
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / 'session.PRIVATE.json'
        self.data = read_json(self.path, {'schema': 1, 'serial': serial, 'backups_complete': False})
        if self.data['serial'] != serial:
            raise ValueError('本地备份会话身份不符')

    def save(self):
        atomic_json(self.path, self.data)

    def verified_backups(self):
        if not self.data.get('backups_complete'):
            raise ValueError('原机备份尚未完整完成')
        required = {'nk.original.PRIVATE.bin', 'nor.original.PRIVATE.bin',
                    'disk-prefix.original.PRIVATE.bin', 'vault.legacy.PRIVATE.bin'}
        if set(self.data.get('backup_files', {})) != required:
            raise ValueError('原机备份清单不完整')
        for name, info in self.data['backup_files'].items():
            path = self.root / name
            if not path.is_file() or digest(path.read_bytes()) != info['sha256']:
                raise ValueError('备份缺失或已改变：' + name)
        return self.root

    def verified_original_nk(self):
        expected = self.data.get('original_nk_sha256') or self.data.get('backup_files', {}).get('nk.original.PRIVATE.bin', {}).get('sha256')
        path = self.root / 'nk.original.PRIVATE.bin'
        if not expected or not path.is_file() or digest(path.read_bytes()) != expected:
            raise ValueError('尚无已校验的原机 NK；不能自动恢复')
        return path
