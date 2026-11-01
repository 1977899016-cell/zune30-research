"""Real upgrade/restore state machine with simulated MTP; no physical USB calls."""
import hashlib
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'app'))
from zzune.protocol import string, object_info, MtpError
from zzune.storage import Session, atomic_json, digest, read_json
from zzune.transfer import FirmwareTransaction, NORMAL, RECOVERY, UncertainCommit
from zzune.engine import Assistant, bound_helper, helper_manifest
from zzune import engine

SERIAL = 'SYNTHETIC-DEVICE-A'

def info(version=NORMAL, serial=SERIAL, recovery_formats=True):
    ops = [0x1001, 0x1007, 0x1008, 0x101b, 0x100c, 0x100d, 0x9204]
    array = lambda items: struct.pack('<I', len(items)) + b''.join(struct.pack('<H', n) for n in items)
    return (struct.pack('<HIH', 100, 6, 100) + string('fixture') + struct.pack('<H', 0)
            + array(ops) + array([]) * 3 + array([0x3000, 0xb802] if recovery_formats else [])
            + string('Microsoft') + string('Zune') + string(version) + string(serial))

class Device:
    def __init__(self, version=NORMAL, serial=SERIAL):
        self.version, self.serial = version, serial
        self.calls, self.objects = [], {}
        self.pending, self.handle, self.params = [], None, []
        self.bad_read = False
        self.disconnect_on_commit = False
        self.foreign_queue = False
        self.fail_upload = False
        self.recovery_formats = True
        self.fail_before_commit = False

    def __call__(self, device_id, writable=False):
        self.writable = writable
        return self

    def close(self): pass

    def operation(self, op, params=(), data=None, read=False):
        self.calls.append((op, tuple(params)))
        if op == 0x1001: return info(self.version, self.serial, self.recovery_formats)
        if op == 0x1007:
            queue = self.pending + ([0x0bad] if self.foreign_queue else [])
            return struct.pack('<I', len(queue)) + b''.join(struct.pack('<I', n) for n in queue)
        if op == 0x100c:
            if self.fail_before_commit: raise RuntimeError('synthetic precommit failure')
            self.handle = 0x0ff00000 if self.version == RECOVERY else 0x0ff00010 + len(self.objects)
            self.objects[self.handle] = {'info': data, 'data': b''}
            self.pending.append(self.handle); self.params = [0x10001, 0xffffffff, self.handle]
            return
        if op == 0x100d:
            if self.fail_upload: raise RuntimeError('synthetic upload failure')
            self.objects[self.handle]['data'] = data
            return
        if op == 0x1008:
            if self.version == RECOVERY: raise MtpError(0x2002)
            return self.objects[params[0]]['info']
        if op == 0x101b:
            if self.version == RECOVERY: raise MtpError(0x2002)
            handle, at, size = params
            output = self.objects[handle]['data'][at:at+size]
            return bytes([output[0] ^ 1]) + output[1:] if self.bad_read and output else output
        if op == 0x9204:
            if self.disconnect_on_commit: raise RuntimeError('synthetic USB disconnect')
            return 0x2001
        raise AssertionError(hex(op))

    @property
    def commits(self): return sum(op == 0x9204 for op, _ in self.calls)

class TransactionTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.device = Device()

    def tearDown(self): self.temporary.cleanup()

    def run_transaction(self, files=None, recovery=False):
        return FirmwareTransaction(self.device, SERIAL, self.root / 'transaction.json', recovery).run(files or [('nk.bin', b'fixture-image')])

    def test_exact_full_readback_and_queue_precede_one_commit(self):
        report = self.run_transaction([('qtk.exe', b'fixture-helper'), ('nk.bin', b'x' * 600000)])
        self.assertEqual(self.device.commits, 1)
        self.assertTrue(all(row['verification'] == 'full_byte_exact_readback' for row in report['files']))
        self.assertTrue(report['commit_intent'])
        self.assertGreaterEqual(sum(op == 0x101b for op, _ in self.device.calls), 4)

    def test_disconnect_after_commit_cannot_trigger_second_commit(self):
        self.device.disconnect_on_commit = True
        report = self.run_transaction()
        self.assertEqual(report['commit_response'], 'disconnected_or_uncertain_DO_NOT_RETRY')
        with self.assertRaises(UncertainCommit): self.run_transaction()
        self.assertEqual(self.device.commits, 1)

    def test_interrupted_process_with_durable_intent_cannot_retry(self):
        atomic_json(self.root / 'transaction.json', {'commit_intent': True})
        with self.assertRaises(UncertainCommit): self.run_transaction()
        self.assertEqual(self.device.calls, [])

    def test_wrong_device_never_receives_payload(self):
        self.device.serial = 'SYNTHETIC-DEVICE-B'
        with self.assertRaises(ValueError): self.run_transaction()
        self.assertFalse(any(op == 0x100c for op, _ in self.device.calls))

    def test_corrupted_staging_never_commits(self):
        self.device.bad_read = True
        with self.assertRaises(ValueError): self.run_transaction()
        self.assertEqual(self.device.commits, 0)

    def test_foreign_queue_never_receives_more_firmware(self):
        self.device.foreign_queue = True
        with self.assertRaises(ValueError): self.run_transaction()
        self.assertFalse(any(op == 0x100c for op, _ in self.device.calls))

    def test_source_upload_failure_never_commits(self):
        self.device.fail_upload = True
        with self.assertRaises(RuntimeError): self.run_transaction()
        self.assertEqual(self.device.commits, 0)

    def test_bootloader_or_recovery_binary_destination_is_forbidden(self):
        for name in ['eboot.bin', 'recovery.bin', '../nk.bin']:
            with self.assertRaises(ValueError): self.run_transaction([(name, b'fixture')])
        self.assertEqual(self.device.calls, [])

    def test_recovery_does_not_require_unadvertised_format_or_claim_readback(self):
        self.device.version = RECOVERY
        self.device.recovery_formats = False
        report = self.run_transaction(recovery=True)
        self.assertEqual(self.device.commits, 1)
        self.assertEqual(report['files'][0]['verification'], 'complete_transfer_ack_only_recovery_readback_unavailable')
        self.assertFalse(any(op in (0x1008, 0x101b) for op, _ in self.device.calls))

class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.device = Device(RECOVERY)
        self.assistant = Assistant(self.root, transport_factory=self.device, enumerate_devices=lambda: ['fixture'])
        self.session = Session(self.root, SERIAL)
        blob = b'B000FF\n' + struct.pack('<II', 0x88200000, 4096) + struct.pack('<III', 0x88200000, 3, 294) + b'abc' + struct.pack('<III', 0, 0x88200000, 0)
        names = ['nk.original.PRIVATE.bin', 'nor.original.PRIVATE.bin', 'disk-prefix.original.PRIVATE.bin', 'vault.legacy.PRIVATE.bin']
        self.session.data['backup_files'] = {}
        for name in names:
            data = blob if name.startswith('nk.') else b'synthetic-backup'
            (self.session.root / name).write_bytes(data)
            self.session.data['backup_files'][name] = {'sha256': digest(data)}
        self.session.data['backups_complete'] = True; self.session.save()

    def tearDown(self): self.temporary.cleanup()

    def test_replaced_backup_blocks_recovery_before_USB_upload(self):
        (self.session.root / 'nk.original.PRIVATE.bin').write_bytes(b'changed')
        with self.assertRaises(ValueError): self.assistant.restore(SERIAL)
        self.assertEqual(self.device.calls, [])

    def test_partial_backup_keeps_original_nk_recovery_available(self):
        self.session.data['backups_complete'] = False
        self.session.data['original_nk_sha256'] = self.session.data['backup_files']['nk.original.PRIVATE.bin']['sha256']
        self.session.data.pop('backup_files'); self.session.save()
        self.assertTrue(self.assistant.inspect()['restore_available'])
        with self.assertRaises(ValueError): self.session.verified_backups()
        # Reaching the intentionally failed upload proves recovery was not blocked
        # by the incomplete raw backup, while no installation commit is sent.
        self.device.fail_before_commit = True
        with self.assertRaisesRegex(RuntimeError, 'precommit'):
            self.assistant.restore(SERIAL)
        self.assertEqual(self.device.commits, 0)

    def test_precommit_restore_failure_cannot_certify_recovery(self):
        self.device.fail_before_commit = True
        with self.assertRaises(RuntimeError): self.assistant.restore(SERIAL)
        self.device.version = NORMAL
        self.assistant.inspect()
        session = Session(self.root, SERIAL)
        self.assertFalse(session.data.get('recovery_writeback_observed', False))

    def test_pending_restore_cannot_repeat_without_observed_boot(self):
        self.session.data.update(restore_attempts=1, restore_success_generation=0)
        self.session.save()
        with self.assertRaises(ValueError): self.assistant.restore(SERIAL)
        self.assertEqual(self.device.commits, 0)

    def test_upgrade_requires_completed_recovery_gate(self):
        with self.assertRaisesRegex(ValueError, '首次升级前'):
            self.assistant.upgrade(SERIAL)
        self.assertEqual(self.device.calls, [])

    def test_bound_native_helper_replaces_only_the_64_byte_owner_header(self):
        for role in ('backup-nk', 'backup-raw'):
            row = helper_manifest()[role]
            original = (ROOT / 'app' / 'assets' / row['filename']).read_bytes()
            header = struct.pack('<16s16s8I', row['magic'].encode(), b'fixture-token-16', row['version'], row['capacity'], 0x040000ee, 0, 0, 0, 0, 0)
            bound = bound_helper(role, header); offset = row['binding_offset']
            self.assertEqual(original[:offset], bound[:offset])
            self.assertEqual(original[offset+64:], bound[offset+64:])
            self.assertEqual(bound[offset:offset+64], header)

class WorkflowDevice(Device):
    """Simulated CE results; ARM behavior is independently tested in native_fixture."""
    def __init__(self, nk, nor, disk):
        super().__init__()
        self.nk, self.nor, self.disk = nk, nor, disk
        self.next_data = 0x04000100

    def operation(self, op, params=(), data=None, read=False):
        if op == 0x100c and int.from_bytes(data[4:6], 'little') == 0x3000:
            self.calls.append((op, tuple(params)))
            self.handle = self.next_data; self.next_data += 1
            self.objects[self.handle] = {'info': data, 'data': b''}
            self.params = [0x10001, 0xffffffff, self.handle]
            return
        if op == 0x9204:
            for handle in self.pending:
                metadata, payload = self.objects[handle]['info'], self.objects[handle]['data']
                name = engine.Reader(metadata[52:]).string()
                if name == 'qtk.exe':
                    for role, row in helper_manifest().items():
                        if role == 'neutral-qtk' or len(payload) != row['bytes']: continue
                        header = payload[row['binding_offset']:row['binding_offset']+64]
                        if header[:16] != row['magic'].encode().ljust(16, b'\0'): continue
                        fields = list(struct.unpack('<16s16s8I', header))
                        capacity, carrier = fields[3], fields[4]
                        initial = self.objects[carrier]['data']
                        if header != initial[:64]: raise AssertionError('Wrong synthetic carrier binding')
                        if role == 'backup-nk': body = self.nk
                        else:
                            body = struct.pack('<16s12I', b'ZTEST1RAW109', 109, 2, 0x21, 0, 1,
                                len(self.nor), len(self.disk), sum(self.nor)&0xffffffff, sum(self.disk)&0xffffffff, 0, 0, 0)
                            body += self.nor + self.disk
                        output = bytearray(initial)
                        fields[5:9] = [2, len(body), 0, sum(body) & 0xffffffff]
                        output[:64] = struct.pack('<16s16s8I', *fields)
                        output[64:64+len(body)] = bytes(a^b for a,b in zip(body, initial[64:64+len(body)]))
                        self.objects[carrier]['data'] = bytes(output)
                elif name == 'nk.bin':
                    self.version = NORMAL if payload == self.nk else '03.30.00039.00-00002'
                    self.recovery_formats = True
            self.calls.append((op, tuple(params))); self.pending.clear(); return 0x2001
        return super().operation(op, params, data, read)

class FullWorkflowTests(unittest.TestCase):
    def test_real_assistant_backup_recovery_gate_upgrade_and_restore_sequence(self):
        nk = b'B000FF\n' + struct.pack('<II', 0x88200000, 4096) + struct.pack('<III', 0x88200000, 3, 294) + b'abc' + struct.pack('<III', 0, 0x88200000, 0)
        nor, disk = bytes(0x200000), bytes([7]) * 0x100000
        device = WorkflowDevice(nk, nor, disk)
        with tempfile.TemporaryDirectory() as temporary, patch.object(engine, 'ORIGINAL_NK', digest(nk)), patch.object(engine, 'BOOTLOADER', digest(nor[:0x40000])):
            assistant = Assistant(temporary, transport_factory=device, enumerate_devices=lambda: ['fixture'], sleep=lambda _: None)
            assistant.backup(SERIAL)
            session = Session(temporary, SERIAL); session.verified_backups()
            self.assertEqual((session.root/'nk.original.PRIVATE.bin').read_bytes(), nk)
            self.assertEqual((session.root/'nor.original.PRIVATE.bin').read_bytes(), nor)
            self.assertEqual((session.root/'disk-prefix.original.PRIVATE.bin').read_bytes(), disk)
            self.assertEqual(device.commits, 2)
            # First use must demonstrate the actual recovery->normal transition.
            device.version = RECOVERY; device.recovery_formats = False
            assistant.restore(SERIAL)
            session = Session(temporary, SERIAL)
            self.assertTrue(session.data['recovery_writeback_observed'])
            candidate = nk.replace(b'abc', b'acb')  # Same valid additive checksum.
            (session.root/'nk.upgrade.PRIVATE.bin').write_bytes(candidate)
            session.data.update(prepared=True, candidate_sha256=digest(candidate)); session.save()
            assistant.upgrade(SERIAL)
            self.assertEqual(device.version, '03.30.00039.00-00002')
            device.version = RECOVERY
            assistant.restore(SERIAL)
            self.assertEqual(device.version, NORMAL)
            self.assertEqual(device.commits, 5)
            self.assertTrue(all(op in (0x1001,0x1007,0x1008,0x101b,0x100c,0x100d,0x9204) for op,_ in device.calls))

if __name__ == '__main__': unittest.main()
