"""Strict offline CE B000FF container reader. No device access."""
from dataclasses import dataclass
import struct

@dataclass(frozen=True)
class Record:
    address: int
    data: bytes

@dataclass(frozen=True)
class Image:
    base: int
    span: int
    entry: int
    records: tuple

    def flatten(self):
        result = bytearray(self.span)
        for record in self.records:
            start = record.address - self.base
            result[start:start + len(record.data)] = record.data
        return bytes(result)

def parse(data):
    if len(data) < 39 or data[:7] != b'B000FF\n':
        raise ValueError('Not a CE B000FF container')
    base, span = struct.unpack_from('<II', data, 7)
    if not 0 < span <= 32 * 1024 * 1024 or base + span > 0x100000000:
        raise ValueError('Invalid or unsupported image range')
    at, records, intervals = 15, [], []
    while at + 12 <= len(data):
        address, size, checksum = struct.unpack_from('<III', data, at)
        at += 12
        if address == 0:
            if checksum or at != len(data) or not base <= size < base + span or not records:
                raise ValueError('Invalid terminal record')
            return Image(base, span, size, tuple(records))
        if not size or not base <= address < address + size <= base + span or at + size > len(data):
            raise ValueError('Out-of-range or truncated record')
        if any(max(address, lo) < min(address + size, hi) for lo, hi in intervals):
            raise ValueError('Overlapping records')
        payload = data[at:at + size]
        if sum(payload) & 0xffffffff != checksum:
            raise ValueError('Record checksum mismatch')
        records.append(Record(address, payload))
        intervals.append((address, address + size))
        if len(records) > 4096:
            raise ValueError('Too many records')
        at += size
    raise ValueError('Missing terminal record')

def rebuild(original, flat):
    """Retain original record ranges, append new image bytes, recompute sums."""
    if len(flat) < original.span:
        raise ValueError('This builder does not shrink images')
    result = bytearray(b'B000FF\n' + struct.pack('<II', original.base, len(flat)))
    chunks = [(r.address, flat[r.address-original.base:r.address-original.base+len(r.data)])
              for r in original.records]
    if len(flat) > original.span:
        chunks.append((original.base + original.span, flat[original.span:]))
    for address, payload in chunks:
        result += struct.pack('<III', address, len(payload), sum(payload) & 0xffffffff) + payload
    result += struct.pack('<III', 0, original.entry, 0)
    checked = parse(bytes(result))
    if checked.flatten() != flat:
        raise ValueError('Reconstructed container differs from intended bytes')
    return bytes(result)
