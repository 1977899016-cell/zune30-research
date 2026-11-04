"""Small UI interface for device inspection, backup, prepare, upgrade and restore.

Writes occur only in explicitly selected worker actions. Each operation keeps a
private same-unit journal. Firmware commits are never retried automatically.
"""
from contextlib import contextmanager
from pathlib import Path
import hashlib
import json
import os
import secrets
import struct
import subprocess
import sys
import tempfile
import time
from .protocol import device_info, object_info, Reader
from .storage import Session, atomic_json, read_json, write_once, digest, same_unit
from .transfer import NORMAL, RECOVERY, FirmwareTransaction, identify, full_readback
from .host import OfficialZuneBusy, official_zune_running

BUNDLE = Path(getattr(sys, '_MEIPASS', Path(__file__).resolve().parents[2]))
ASSETS = BUNDLE / 'app' / 'assets'
UPGRADE = BUNDLE / 'tools' / 'upgrade'
sys.path.insert(0, str(UPGRADE))
from ce_bin import parse
from check_backups import check
from build_upgrade import patch, STOCK_SHA256
from ce_lzx import load_decoder, encode

ORIGINAL_NK = '9d947febb71fbe8a528a19fde97df22f35208865329f15c26a2f9412b7067d10'
BOOTLOADER = 'e5077048e6a67c32bb3e948d27b9b643897c487631e0a860c495dd8ee096db7d'

def helper_manifest():
    return read_json(ASSETS / 'helpers.json')['files']

def bound_helper(role, header):
    row = helper_manifest()[role]
    payload = (ASSETS / row['filename']).read_bytes()
    if digest(payload) != row['sha256'] or len(header) != 64:
        raise ValueError('备份程序校验失败')
    magic, token, version, capacity, handle, status, size, error, checksum, permissions = struct.unpack('<16s16s8I', header)
    if (magic != row['magic'].encode().ljust(16, b'\0') or version != row['version']
            or capacity != row['capacity'] or handle >> 24 != 4
            or handle in (0x04000000, 0x04000001, 0x04000002)
            or any((status, size, error, checksum, permissions))):
        raise ValueError('备份程序绑定头不符合已核对的布局')
    marker = bytes.fromhex(row['template_header_hex'])
    offset = row['binding_offset']
    if payload[offset:offset+64] != marker or payload.count(marker) != 1:
        raise ValueError('备份程序绑定位置无效')
    return payload[:offset] + header + payload[offset+64:]

def neutral_helper():
    row = helper_manifest()['neutral-qtk']
    data = (ASSETS / row['filename']).read_bytes()
    if digest(data) != row['sha256']: raise ValueError('退出程序校验失败')
    return data

class Assistant:
    def __init__(self, backup_root, progress=lambda *_: None, transport_factory=None, enumerate_devices=None,
                 sleep=time.sleep, now=time.monotonic, host_busy=None):
        if transport_factory is None:
            from .wpd import WpdTransport, inventory
            transport_factory, enumerate_devices = WpdTransport, inventory
            if host_busy is None: host_busy = official_zune_running
        self.root = Path(backup_root)
        self.progress = progress
        self.factory, self.enumerate = transport_factory, enumerate_devices
        self.sleep, self.now = sleep, now
        self.host_busy = host_busy or (lambda: False)

    @contextmanager
    def connect(self, serial=None, writable=False):
        if self.host_busy():
            raise OfficialZuneBusy('检测到官方 Zune 软件正在运行（设备重启后可能自动打开）。请先等同步或固件安装结束，再退出该软件；保持 USB 连接。本工具不会自动关闭它。')
        ids = self.enumerate()
        if len(ids) != 1:
            raise RuntimeError('请只连接一台 Zune；当前检测到 ' + str(len(ids)) + ' 个接口')
        transport = self.factory(ids[0], writable=writable)
        try:
            info = device_info(transport.operation(0x1001, read=True))
            if serial: same_unit(serial, info)
            if info['manufacturer'] != 'Microsoft' or info['model'] != 'Zune':
                raise ValueError('不是支持的 Zune 接口')
            yield transport, info
        finally:
            try: transport.close()
            except Exception: pass

    def inspect(self):
        with self.connect() as (_, info):
            session = Session(self.root, info['serial'])
            complete = session.data.get('backups_complete', False)
            if complete: session.verified_backups()
            try:
                session.verified_original_nk(); restore_available = True
            except ValueError:
                restore_available = False
            attempts = session.data.get('restore_attempts', 0)
            restore_journal = read_json(session.root / f'restore-{attempts}.PRIVATE.json', {})
            if attempts and restore_journal.get('commit_intent') and info['firmware'] == NORMAL and session.data.get('restore_waiting_for_boot'):
                session.data.update(restore_success_generation=attempts, restore_waiting_for_boot=False)
                if session.data.get('last_restore_was_recovery'):
                    session.data['recovery_writeback_observed'] = True
                session.save()
            return {**info, 'backups_complete': complete, 'prepared': session.data.get('prepared', False),
                    'workspace': str(session.root), 'expected_backup_firmware': info['firmware'] == NORMAL,
                    'recovery': info['firmware'] == RECOVERY,
                    'recovery_verified': session.data.get('recovery_writeback_observed', False),
                    'restore_available': restore_available,
                    'profile_supported': session.data.get('bootloader_profile_supported', False)}

    def _wait(self, serial, predicate, message, seconds=240):
        start = self.now()
        last_error = None
        while self.now() - start < seconds:
            self.progress(message, None)
            try:
                with self.connect(serial) as (transport, info):
                    result = predicate(transport, info)
                    if result is not None: return result
            except OfficialZuneBusy as exc:
                last_error = str(exc)
                self.progress(last_error, None)
            except (RuntimeError, OSError) as exc:
                last_error = str(exc)
            self.sleep(3)
        detail = (' 最近状态：' + last_error) if last_error else ''
        raise RuntimeError('等待设备超时。未重复安装提交。请查看屏幕；黑屏时使用“恢复原系统”的按键引导。' + detail)

    def _create_carrier(self, session, role):
        row = helper_manifest()[role]
        state = session.data.setdefault('carriers', {}).get(role)
        if state:
            initial = (session.root / state['initial']).read_bytes()
            if digest(initial) != state['sha256']: raise ValueError('本地备份容器原件已改变')
            return state, initial
        with self.connect(session.data['serial'], writable=True) as (transport, info):
            identify(transport, session.data['serial'], NORMAL)
            if not {0x100c, 0x100d, 0x1008, 0x101b}.issubset(info['operations']) or 0x3000 not in info['formats']:
                raise ValueError('此设备不支持已核对的普通备份容器传输')
            name = 'ZZAudio_Backup_' + secrets.token_hex(8) + '.bin'
            capacity = row['capacity']
            transport.operation(0x100c, [0x10001, 0xffffffff], data=object_info(name, capacity, 0x3000))
            params = transport.params
            if len(params) < 3 or params[0] != 0x10001 or params[2] >> 24 != 4 or params[2] in (0x04000000, 0x04000001, 0x04000002):
                raise ValueError('普通备份容器句柄无效')
            handle = params[2]
            header = struct.pack('<16s16s8I', row['magic'].encode(), secrets.token_bytes(16), row['version'], capacity, handle, 0, 0, 0, 0, 0)
            initial = header + secrets.token_bytes(capacity - 64)
            filename = role + '.carrier.initial.PRIVATE.bin'
            write_once(session.root / filename, initial)
            # Save ownership before upload; a failed upload never installs a helper.
            state = {'handle': handle, 'name': name, 'initial': filename, 'sha256': digest(initial),
                     'uploaded_verified': False, 'helper_commit_requested': False}
            session.data['carriers'][role] = state; session.save()
            self.progress('创建并回读自己的备份容器', 0)
            transport.operation(0x100d, data=initial)
            full_readback(transport, handle, initial, self.progress)
            state['uploaded_verified'] = True; session.save()
            return state, initial

    def _capture(self, session, role):
        state, initial = self._create_carrier(session, role)
        if not state['uploaded_verified']:
            raise RuntimeError('上次容器传输未完成；本次没有安装程序。请保留本地日志供核对，不要重复提交旧队列。')
        if not state['helper_commit_requested']:
            with self.connect(session.data['serial'], writable=True) as (transport, _):
                # Ownership rechecked on the actual device before installing code.
                got = transport.operation(0x101b, [state['handle'], 0, 64], read=True)
                if got != initial[:64]: raise ValueError('设备容器头已改变，禁止启动备份程序')
                helper = bound_helper(role, initial[:64])
                journal = session.root / (role + '.install.PRIVATE.json')
                state['helper_commit_requested'] = True; session.save()
                try:
                    FirmwareTransaction(transport, session.data['serial'], journal, progress=self.progress).run([('qtk.exe', helper)])
                except Exception:
                    previous = read_json(journal, {})
                    if not previous.get('commit_intent'):
                        state['helper_commit_requested'] = False; session.save()
                    raise
        def result(transport, info):
            if info['firmware'] != NORMAL: return None
            header = transport.operation(0x101b, [state['handle'], 0, 64], read=True)
            if len(header) != 64 or header[:44] != initial[:44]: raise ValueError('备份容器身份不符')
            _, _, _, status, size, error, checksum, _ = struct.unpack_from('<8I', header, 32)
            if status in (0, 1): return None
            if status != 2 or error: raise ValueError('设备备份程序报告错误 ' + str(error) + '，未开放升级')
            if not 39 <= size <= len(initial) - 64: raise ValueError('备份输出长度无效')
            body = bytearray()
            for offset in range(64, 64 + size, 262144):
                count = min(262144, 64 + size - offset)
                encrypted = transport.operation(0x101b, [state['handle'], offset, count], read=True)
                if len(encrypted) != count: raise ValueError('备份输出不完整')
                body.extend(a ^ b for a, b in zip(encrypted, initial[offset:offset+count]))
                self.progress('回读原机备份', int((offset - 64 + count) * 100 / size))
            if sum(body) & 0xffffffff != checksum: raise ValueError('备份数据校验失败')
            return bytes(body)
        return self._wait(session.data['serial'], result, '等待备份程序完成并重新连接；保持 USB 接好')

    def backup(self, serial):
        session = Session(self.root, serial)
        if session.data.get('backups_complete'):
            session.verified_backups()
            return {'message': '已有完整原机备份，校验通过；未重复安装备份程序', 'workspace': str(session.root)}
        with self.connect(serial) as (_, info):
            if info['firmware'] != NORMAL: raise ValueError('USB 自动备份目前只支持已分析的 1.0 (186) TEST 接口')
        nk_path = session.root / 'nk.original.PRIVATE.bin'
        if not nk_path.exists():
            nk = self._capture(session, 'backup-nk')
            parse(nk)
            write_once(nk_path, nk)
        nk = nk_path.read_bytes()
        parse(nk)
        session.data['original_nk_sha256'] = digest(nk); session.save()
        if digest(nk) != ORIGINAL_NK:
            raise ValueError('系统备份已保存，但它不是已核对的 1.0 TEST 构建；已禁止内核读取及升级')
        if not all((session.root / name).exists() for name in ('nor.original.PRIVATE.bin', 'disk-prefix.original.PRIVATE.bin', 'vault.legacy.PRIVATE.bin')):
            body = self._capture(session, 'backup-raw')
            if len(body) != 64 + 0x200000 + 0x100000 or body[:16] != b'ZTEST1RAW109'.ljust(16, b'\0'):
                raise ValueError('原机完整备份布局不符')
            version, trust, permission, mode, restored, nor_bytes, disk_bytes, nor_sum, disk_sum, error, _, _ = struct.unpack_from('<12I', body, 16)
            nor, disk = body[64:64+0x200000], body[64+0x200000:]
            if (version, trust, restored, nor_bytes, disk_bytes, error) != (109, 2, 1, 0x200000, 0x100000, 0):
                raise ValueError('原机权限恢复或完整备份检查未通过')
            if sum(nor) & 0xffffffff != nor_sum or sum(disk) & 0xffffffff != disk_sum:
                raise ValueError('原机备份分区校验不符')
            write_once(session.root / 'nor.original.PRIVATE.bin', nor)
            write_once(session.root / 'disk-prefix.original.PRIVATE.bin', disk)
            write_once(session.root / 'vault.legacy.PRIVATE.bin', nor[0x70000:0x80000])
        nor = (session.root / 'nor.original.PRIVATE.bin').read_bytes()
        disk = (session.root / 'disk-prefix.original.PRIVATE.bin').read_bytes()
        legacy = (session.root / 'vault.legacy.PRIVATE.bin').read_bytes()
        report = check(nk, nor, disk, legacy)
        atomic_json(session.root / 'backup-inventory.PRIVATE.json', report)
        session.data['backup_files'] = {
            name: {'sha256': digest((session.root / name).read_bytes())}
            for name in ('nk.original.PRIVATE.bin', 'nor.original.PRIVATE.bin', 'disk-prefix.original.PRIVATE.bin', 'vault.legacy.PRIVATE.bin')
        }
        session.data['backups_complete'] = True
        session.data['bootloader_profile_supported'] = digest(nor[:0x40000]) == BOOTLOADER
        session.save()
        return {'message': '原系统、完整闪存和硬盘前部备份已保存并校验。请再复制一份备份目录到另一块盘。',
                'workspace': str(session.root), 'profile_supported': session.data['bootloader_profile_supported']}

    def prepare(self, serial, source):
        session = Session(self.root, serial); session.verified_backups()
        nor = (session.root / 'nor.original.PRIVATE.bin').read_bytes()
        if digest(nor[:0x40000]) != BOOTLOADER: raise ValueError('启动器不是已核对的 TEST 构建，禁止使用本升级方案')
        source = Path(source)
        original = source.read_bytes() if source.suffix.lower() != '.cab' else None
        if original is None:
            with tempfile.TemporaryDirectory(prefix='zune-stock-input-') as temporary:
                result = subprocess.run([str(Path(os.environ.get('WINDIR', 'C:/Windows')) / 'System32/expand.exe'), '-F:nk.bin', str(source), temporary], capture_output=True,
                                        creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
                if result.returncode: raise ValueError('CAB 解包失败；请选择你已有的原始 3.3 NK')
                matches = [p.read_bytes() for p in Path(temporary).rglob('*') if p.is_file() and digest(p.read_bytes()) == STOCK_SHA256]
                if len(matches) != 1: raise ValueError('CAB 中没有唯一匹配的官方 3.3 NK')
                original = matches[0]
        if digest(original) != STOCK_SHA256: raise ValueError('所选文件不是已经核对的官方 3.30.39 NK；没有改动设备')
        legacy = (session.root / 'vault.legacy.PRIVATE.bin').read_bytes()
        self.progress('离线构建本机 3.3 兼容镜像；不写设备', 25)
        decoder = load_decoder(BUNDLE / 'app' / 'vendor')
        packed = encode(legacy, decoder, Path(os.environ.get('WINDIR', 'C:/Windows')) / 'System32/makecab.exe')
        candidate, report = patch(original, legacy, secrets.token_bytes(16), packed, decoder)
        target = session.root / 'nk.upgrade.PRIVATE.bin'
        if target.exists():
            # Reuse an already prepared, checked image instead of silently replacing it.
            expected = session.data.get('candidate_sha256')
            if not expected or digest(target.read_bytes()) != expected: raise ValueError('已有候选镜像状态不明，已停止')
            return {'message': '已准备的本机镜像校验通过', 'prepared': True}
        write_once(target, candidate)
        atomic_json(session.root / 'build.PRIVATE.json', report)
        session.data.update(prepared=True, candidate_sha256=digest(candidate))
        session.save()
        return {'message': '本机私有 3.3 兼容镜像构建及校验完成，尚未安装', 'prepared': True}

    def upgrade(self, serial):
        session = Session(self.root, serial); session.verified_backups()
        if not session.data.get('recovery_writeback_observed'):
            raise ValueError('首次升级前，请先用“恢复原系统”在恢复接口写回原机 NK 并确认启动')
        if not session.data.get('prepared'): raise ValueError('尚未选择并校验原始 3.3 系统')
        payload = (session.root / 'nk.upgrade.PRIVATE.bin').read_bytes()
        if digest(payload) != session.data['candidate_sha256']: raise ValueError('候选镜像已改变')
        parse(payload)
        with self.connect(serial, writable=True) as (transport, _):
            FirmwareTransaction(transport, serial, session.root / 'upgrade.install.PRIVATE.json', progress=self.progress).run([
                ('qtk.exe', neutral_helper()), ('nk.bin', payload)])
        def boot(_, info):
            if info['firmware'] == '03.30.00039.00-00002': return {'firmware': info['firmware']}
            return None
        try:
            result = self._wait(serial, boot, '已提交升级，等待设备启动；不重复提交', seconds=150)
        except RuntimeError:
            return {'message': '升级已提交，但尚未确认启动。若黑屏，请点击“恢复原系统”，按提示进入恢复画面。', 'needs_recovery': True}
        session.data['upgrade_boot_version_observed'] = result['firmware']; session.save()
        return {'message': '电脑已检测到 3.3 接口。请确认设备进入主菜单，再验证重启和官方 Zune 软件识别。', 'firmware': result['firmware']}

    def restore(self, serial):
        session = Session(self.root, serial)
        payload = session.verified_original_nk().read_bytes()
        parse(payload)
        with self.connect(serial, writable=True) as (transport, info):
            recovery = info['firmware'] == RECOVERY
            if info['firmware'] not in (NORMAL, RECOVERY):
                raise ValueError('请先按窗口提示进入连接电脑恢复画面，再点击恢复')
            previous = session.data.get('restore_attempts', 0)
            if previous > session.data.get('restore_success_generation', 0):
                raise ValueError('上一轮恢复提交结果仍未确定；请先查看屏幕并检查连接，禁止重复提交')
            number = previous + 1
            session.data.update(restore_attempts=number, last_restore_was_recovery=recovery,
                                restore_waiting_for_boot=True)
            session.save()
            files = [('nk.bin', payload)] if recovery else [('qtk.exe', neutral_helper()), ('nk.bin', payload)]
            journal = session.root / f'restore-{number}.PRIVATE.json'
            try:
                FirmwareTransaction(transport, serial, journal, recovery=recovery, progress=self.progress).run(files)
            except Exception:
                if not read_json(journal, {}).get('commit_intent'):
                    session.data.update(restore_attempts=previous, restore_waiting_for_boot=False)
                    session.save()
                raise
        def boot(_, info):
            return {'firmware': info['firmware']} if info['firmware'] == NORMAL else None
        try:
            result = self._wait(serial, boot, '等待原机 1.0 启动；不重复提交', seconds=150)
            session.data.update(restore_success_generation=number, restore_waiting_for_boot=False)
            if recovery: session.data['recovery_writeback_observed'] = True
            session.save()
            return {'message': '已检测到原机 1.0 接口。请确认正常主菜单；USB 版本不等于完整文件回读。', **result}
        except RuntimeError:
            return {'message': '原机 NK 已提交，但尚未确认启动。请保留日志和备份，不要反复点击提交。', 'needs_recovery': True}
