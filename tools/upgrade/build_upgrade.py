"""Reconstruct the AUTH196 research image OFFLINE from the owner's local inputs.

Creates a PRIVATE per-device, stock-3.3-derived diagnostic image. It is not
unmodified Microsoft firmware and does not install, authenticate or contact USB.
Generated output embeds the local encrypted vault and must never be published.
"""
import argparse
import hashlib
import json
import secrets
import struct
from pathlib import Path
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM
from ce_bin import parse, rebuild
from ce_lzx import load_decoder, encode, decode
from runtime import assemble, CAVE

STOCK_SHA256 = '81951eaf10feb868e2f2818aea64d15f0b2b6484458454c2655efd0668c13a11'
BASE = 0x88200000

def require(condition, message):
    if not condition:
        raise ValueError(message)

def sha(data):
    return hashlib.sha256(data).hexdigest()

def cstring(flat, pointer):
    offset = pointer - BASE
    require(0 <= offset < len(flat), 'String pointer outside ROM')
    end = flat.find(b'\0', offset, offset + 256)
    require(end >= offset, 'Missing ROM string terminator')
    return flat[offset:end].decode('ascii')

def modules(flat, toc):
    count = struct.unpack_from('<I', flat, toc + 16)[0]
    result = {}
    for i in range(count):
        row = struct.unpack_from('<8I', flat, toc + 84 + i * 32)
        name = cstring(flat, row[4]).lower()
        require(name not in result, 'Duplicate module name')
        result[name] = row
    return result

def patch(original, legacy, token, packed, decoder):
    require(sha(original) == STOCK_SHA256, 'Unsupported stock NK hash; offsets must not be reused on another image')
    require(len(legacy) == 65536, 'Legacy vault must be exactly 65536 bytes')
    require(decode(packed, len(legacy), decoder) == legacy, 'Packed ROM file is not the local legacy backup')
    container = parse(original)
    require(container.base == BASE, 'Unexpected ROM base')
    flat = container.flatten()
    image = bytearray(flat)
    toc = struct.unpack_from('<I', flat, 0x44)[0] - BASE
    table = modules(flat, toc)
    code = assemble(legacy, token)
    row = table['ceddk.dll']
    section_offset = row[6] - BASE
    section = struct.unpack_from('<6I', flat, section_offset)
    require(section == (0x2844, 0x1000, 0x2a00, 0x883e1000, 0x03e91000, 0x60000020), 'Unexpected CEDDK section')
    new_text = flat[section[3] - BASE:section[3] - BASE + section[0]] + code
    vsize = len(new_text)
    require(vsize <= 0x3000 and section[4] + section[0] == CAVE, 'Code exceeds audited executable gap')
    for name, module in table.items():
        count = struct.unpack_from('<H', flat, module[5] - BASE)[0]
        for index in range(count):
            current = struct.unpack_from('<6I', flat, module[6] - BASE + index * 24)
            collision = max(current[4], CAVE) < min(current[4] + current[0], CAVE + len(code))
            require(not collision, 'Runtime overlap: ' + name)
    new_text += bytes(0x3000 - vsize)
    new_address = (BASE + len(flat) + 4095) & ~4095
    image += bytes(new_address - BASE - len(image)) + new_text
    struct.pack_into('<6I', image, section_offset, vsize, section[1], len(new_text), new_address, section[4], section[5])
    key = table['keyvault.dll']
    key_section = struct.unpack_from('<6I', flat, key[6] - BASE)
    hook_offset = key_section[3] + 0x02fc5afc - key_section[4] - BASE
    arm = Ks(KS_ARCH_ARM, KS_MODE_ARM)
    branch = lambda target: bytes(arm.asm(f'bl #{target}', 0x02fc5afc)[0])
    require(flat[hook_offset:hook_offset+4] == branch(0x02fc7510), 'Original KeyVault call mismatch')
    image[hook_offset:hook_offset+4] = branch(CAVE)
    nk = table['nk.exe']
    nk_section = struct.unpack_from('<6I', flat, nk[6] - BASE)
    deny_offset = nk_section[3] + 0x882417b0 - nk_section[4] - BASE
    require(flat[deny_offset:deny_offset+8] == bytes.fromhex('f0412de90260a0e1'), 'Security-write handler mismatch')
    image[deny_offset:deny_offset+8] = bytes.fromhex('0000a0e31eff2fe1')
    file_count = struct.unpack_from('<I', flat, toc + 48)[0]
    found = []
    for i in range(file_count):
        offset = toc + 84 + len(table) * 32 + i * 28
        entry = list(struct.unpack_from('<7I', flat, offset))
        if cstring(flat, entry[5]) == 'ceconfig.h':
            found.append((offset, entry))
    require(len(found) == 1, 'Expected one unused ceconfig.h ROM data slot')
    file_offset, entry = found[0]
    name_offset = entry[5] - BASE
    image[name_offset:name_offset+11] = b'ZV194.dat\0\0'
    require((BASE + len(image)) % 4 == 0, 'Unaligned new ROM data')
    entry[0] |= 0x800
    entry[3], entry[4], entry[6] = len(legacy), len(packed), BASE + len(image)
    image += packed + bytes((-len(packed)) % 4)
    struct.pack_into('<7I', image, file_offset, *entry)
    ram_start = struct.unpack_from('<I', flat, toc + 20)[0]
    require(BASE + len(image) < ram_start, 'New ROM data overlaps fixed RAM start')
    struct.pack_into('<I', image, toc + 12, BASE + len(image))
    allowed = [(section_offset, section_offset+24), (hook_offset, hook_offset+4),
               (deny_offset, deny_offset+8), (toc+12, toc+16),
               (file_offset, file_offset+28), (name_offset, name_offset+11)]
    for i, (before, after) in enumerate(zip(flat, image)):
        require(before == after or any(lo <= i < hi for lo, hi in allowed), 'Unexpected original-ROM mutation')
    result = rebuild(container, bytes(image))
    report = {
        'scope': 'PRIVATE AUTH196-derived RAM-only compatibility image; offline reconstruction, not an installer',
        'source_stock_sha256': STOCK_SHA256, 'image_bytes': len(result), 'image_sha256': sha(result),
        'runtime_bytes': len(code), 'runtime_sha256': sha(code),
        'rom_legacy_file_roundtrip_verified': True, 'runtime_module_overlap': False,
        'remaining_rom_ram_gap_bytes': ram_start - BASE - len(image),
        'original_ceddk_code_preserved': True, 'container_records': len(parse(result).records),
        'security_write_handler_stub': '0000a0e31eff2fe1',
        'persistent_security_write_implemented': False,
        'bootloader_sig_or_partitions_changed_by_this_tool': False,
        'device_operations_performed': False,
        'new_device_hardware_boot_verified': False,
        'contains_owner_specific_encrypted_identity_material': True,
        'publish_generated_output': False
    }
    return result, report

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-nk', type=Path, required=True)
    parser.add_argument('--legacy-vault', type=Path, required=True)
    parser.add_argument('--vault-sha256', required=True, help='SHA256 from your OWN original backup inventory')
    parser.add_argument('--decompressor-dir', type=Path, required=True)
    parser.add_argument('--makecab', type=Path, default=Path('C:/Windows/System32/makecab.exe'))
    parser.add_argument('--output-dir', type=Path, required=True, help='New LOCAL PRIVATE output folder; must not exist')
    parser.add_argument('--journal-token', help='Optional 32 hexadecimal digits for exact local historical reproduction')
    args = parser.parse_args()
    if args.output_dir.exists():
        parser.error('Output folder exists; refusing to overwrite')
    original = args.stock_nk.read_bytes()
    legacy = args.legacy_vault.read_bytes()
    require(sha(original) == STOCK_SHA256, 'Stock NK SHA256 mismatch')
    require(len(legacy) == 65536 and sha(legacy) == args.vault_sha256.lower(), 'Local legacy backup size/hash mismatch')
    token = bytes.fromhex(args.journal_token) if args.journal_token else secrets.token_bytes(16)
    require(len(token) == 16, 'Journal token must be 16 bytes')
    decoder = load_decoder(args.decompressor_dir)
    packed = encode(legacy, decoder, args.makecab)
    candidate, report = patch(original, legacy, token, packed, decoder)
    args.output_dir.mkdir(parents=True, exist_ok=False)
    (args.output_dir / 'nk.AUTH196.PRIVATE.bin').write_bytes(candidate)
    (args.output_dir / 'runtime.PRIVATE.bin').write_bytes(assemble(legacy, token))
    (args.output_dir / 'build.PRIVATE.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
    print(json.dumps(report, indent=2))

if __name__ == '__main__':
    main()
