"""Assemble the historical RAM-only compatibility routine using LOCAL inputs.

No real vault bytes, private key or chip key are present in this source.
Addresses apply ONLY to the pinned 3.30.39 ROM used by build_upgrade.py.
"""
from pathlib import Path
import hashlib
import struct
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM

CAVE = 0x03e93844
REGIONS = [(0x3c0, 0x2b0), (0x670, 0x30)] + [
    (0x6a0 + i * 0x28, 0x28) for i in range(33)
] + [(0xbc8, 0x20), (0xbe8, 0x20), (0xc28, 0x18)]

def assemble(legacy, token):
    if len(legacy) != 65536 or len(token) != 16:
        raise ValueError('Expected a 64 KiB local legacy vault and 16-byte journal token')
    source = (Path(__file__).parent / 'rewrap_runtime.asm').read_text(encoding='utf-8')
    log_path = '\\Hard Disk2\\firmware\\a194_' + token.hex() + '.bin'
    rom_path = '\\Windows\\ZV194.dat'
    source += '\n' + ''.join(f'    .word {(size << 16) | offset}\n' for offset, size in REGIONS)
    paths = [(log_path + '\0').encode('utf-16-le'), (rom_path + '\0').encode('utf-16-le')]
    for label, data in zip(('file_path', 'source_path'), paths):
        source += label + ':\n    .space ' + str(len(data)) + '\n'
    raw = bytes(Ks(KS_ARCH_ARM, KS_MODE_ARM).asm(source, CAVE)[0])
    tail = hashlib.sha1(legacy).digest() + token
    tail += b''.join(struct.pack('<HH', offset, size) for offset, size in REGIONS) + b''.join(paths)
    if raw[-len(tail):] != bytes(36) + b''.join(
        struct.pack('<HH', offset, size) for offset, size in REGIONS
    ) + bytes(sum(map(len, paths))):
        raise ValueError('Assembler tail layout changed')
    result = raw[:-len(tail)] + tail
    if len(result) > 0x7bc:
        raise ValueError('Routine no longer fits the audited CEDDK page')
    return result
