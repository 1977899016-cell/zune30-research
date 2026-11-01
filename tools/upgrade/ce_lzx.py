"""Local Windows MakeCAB encoder, independently checked by a supplied CE decoder.

The decoder is external; no Microsoft tool or third-party decoder is bundled.
Temporary chunks contain private encrypted device data and remain local.
"""
from pathlib import Path
import importlib.util
import struct
import subprocess
import tempfile

def load_decoder(directory):
    path = Path(directory) / 'wincedecompr.py'
    if not path.is_file():
        path = Path(directory) / 'wince_decompr' / 'wincedecompr.py'
    if not path.is_file():
        raise ValueError('Expected wincedecompr.py or wince_decompr/wincedecompr.py')
    spec = importlib.util.spec_from_file_location('local_ce_decoder', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.CEDecompressROM

def decode(packed, length, decoder):
    output = bytearray(length + 4096)
    count = decoder(packed, len(packed), output, length, 0, 1, 4096)
    if count != length:
        raise ValueError('CE decompression length mismatch')
    return bytes(output[:length])

def encode(data, decoder, makecab):
    chunks = []
    with tempfile.TemporaryDirectory(prefix='zune-local-private-') as temporary:
        root = Path(temporary)
        for index in range(0, len(data), 4096):
            block = data[index:index + 4096]
            source, target = root / 'input.dat', root / 'output.cab'
            source.write_bytes(block)
            if target.exists():
                target.unlink()
            result = subprocess.run([
                str(makecab), '/D', 'CompressionType=LZX', '/D', 'CompressionMemory=15',
                str(source), str(target)
            ], capture_output=True, creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
            if result.returncode:
                raise ValueError('MakeCAB failed: ' + str(result.returncode))
            cab = target.read_bytes()
            if cab[:4] != b'MSCF' or struct.unpack_from('<I', cab, 8)[0] != len(cab):
                raise ValueError('Invalid CAB header')
            if struct.unpack_from('<3H', cab, 26) != (1, 1, 0):
                raise ValueError('Unexpected CAB folder/file/flags')
            offset, blocks, compression = struct.unpack_from('<IHH', cab, 36)
            if blocks != 1 or compression != (15 << 8) | 3:
                raise ValueError('Unexpected LZX CAB block')
            _, compressed, uncompressed = struct.unpack_from('<IHH', cab, offset)
            payload = cab[offset + 8:offset + 8 + compressed]
            if uncompressed != len(block) or len(payload) != compressed:
                raise ValueError('CAB payload length mismatch')
            chunks.append(struct.pack('<4I', 15, len(block), len(payload), len(block)) + payload)
    position = (len(chunks) + 1) * 3
    table = [len(data)]
    for chunk in chunks:
        position += len(chunk)
        table.append(position)
    packed = b''.join(n.to_bytes(3, 'little') for n in table) + b''.join(chunks)
    if decode(packed, len(data), decoder) != data:
        raise ValueError('CE compression roundtrip differs from source')
    return packed
