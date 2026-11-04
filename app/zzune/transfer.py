"""Reviewed firmware transaction: verify exact queue/data, persist intent, commit once."""
from pathlib import Path
from .protocol import device_info, object_info, Reader, handles, MtpError
from .storage import atomic_json, read_json, digest, same_unit

NORMAL = '01.00.00186.00-02.04'
RECOVERY = '00.00.00000.00-00.00'

class UncertainCommit(RuntimeError):
    pass

def identify(transport, serial, version=None):
    info = device_info(transport.operation(0x1001, read=True))
    same_unit(serial, info)
    if info['manufacturer'] != 'Microsoft' or info['model'] != 'Zune':
        raise ValueError('不是本工具支持的 Zune 接口')
    if version and info['firmware'] != version:
        raise ValueError('当前设备状态不符合本步骤：' + info['firmware'])
    return info

def queue(transport):
    return handles(transport.operation(0x1007, [0x10001, 0xb802, 0], read=True))

def full_readback(transport, handle, payload, progress=lambda *_: None):
    for offset in range(0, len(payload), 262144):
        count = min(262144, len(payload) - offset)
        got = transport.operation(0x101b, [handle, offset, count], read=True)
        if got != payload[offset:offset + count]:
            raise ValueError('暂存文件回读不一致；未发送安装提交')
        progress('回读校验', int((offset + count) * 100 / len(payload)))

class FirmwareTransaction:
    def __init__(self, transport, serial, journal, recovery=False, progress=lambda *_: None):
        self.transport, self.serial = transport, serial
        self.path, self.recovery, self.progress = Path(journal), recovery, progress

    def run(self, files):
        if not files or (self.recovery and len(files) != 1):
            raise ValueError('恢复模式只允许一个原机 NK')
        if any(name not in ('qtk.exe', 'nk.bin') for name, _ in files):
            raise ValueError('禁止写入启动器、恢复程序或其他特殊文件')
        if len({name for name, _ in files}) != len(files):
            raise ValueError('重复目标文件')
        previous = read_json(self.path, {})
        if previous.get('commit_intent'):
            raise UncertainCommit('本事务已经提交或结果未确定，禁止再次提交；请检查设备或使用恢复功能')
        info = identify(self.transport, self.serial, RECOVERY if self.recovery else NORMAL)
        required = {0x1007, 0x100c, 0x100d, 0x9204}
        if not self.recovery: required |= {0x1008, 0x101b}
        if not required.issubset(info['operations']) or (not self.recovery and 0xb802 not in info['formats']):
            raise ValueError('设备未声明所需的固件传输能力')
        if queue(self.transport):
            raise ValueError('存在不明固件暂存项，已停止；不要提交旧队列')
        state = {'schema': 1, 'serial': self.serial, 'recovery': self.recovery,
                 'files': [], 'commit_intent': False, 'commit_response': None}
        atomic_json(self.path, state)
        staged = []
        for name, payload in files:
            self.progress('传输 ' + name, 0)
            self.transport.operation(0x100c, [0x10001, 0xffffffff], data=object_info(name, len(payload), 0xb802))
            params = self.transport.params
            if len(params) < 3 or params[0] != 0x10001:
                raise ValueError('固件暂存响应无效')
            handle = params[2]
            if handle in staged or handle in (0, 0xffffffff, 0x04000000, 0x04000001, 0x04000002):
                raise ValueError('固件暂存句柄无效')
            if self.recovery and handle != 0x0ff00000:
                raise ValueError('不是已分析恢复接收器的暂存句柄，已停止')
            self.transport.operation(0x100d, data=payload)
            verification = 'full_byte_exact_readback'
            if self.recovery:
                # Historical recovery cannot supply GetObjectInfo/partial reads.
                # Never claim that an acknowledged upload is a full readback.
                verification = 'complete_transfer_ack_only_recovery_readback_unavailable'
            else:
                meta = self.transport.operation(0x1008, [handle], read=True)
                if len(meta) < 53 or int.from_bytes(meta[8:12], 'little') != len(payload) or Reader(meta[52:]).string() != name:
                    raise ValueError('暂存名称或大小不符；未提交')
                full_readback(self.transport, handle, payload, self.progress)
            staged.append(handle)
            state['files'].append({'name': name, 'bytes': len(payload), 'sha256': digest(payload),
                                   'handle': handle, 'verification': verification})
            atomic_json(self.path, state)
        if not self.recovery and sorted(queue(self.transport)) != sorted(staged):
            raise ValueError('固件队列在校验后发生变化；未提交')
        identify(self.transport, self.serial, RECOVERY if self.recovery else NORMAL)
        state['commit_intent'] = True
        atomic_json(self.path, state)
        self.progress('已校验，正在提交一次安装；请保持连接', 100)
        try:
            self.transport.operation(0x9204)
            state['commit_response'] = 'acknowledged'
        except Exception as exc:
            state['commit_response'] = 'disconnected_or_uncertain_DO_NOT_RETRY'
            state['commit_error'] = {'type': type(exc).__name__, 'message': str(exc)[:1000]}
        atomic_json(self.path, state)
        return state
