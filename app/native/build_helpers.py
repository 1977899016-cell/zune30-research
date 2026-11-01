"""Build original CE backup templates from C using a locally supplied 1.0 DLL.

Compiler and Microsoft DLL are build inputs only, never distributed. The helper
is bound to a random owned carrier by the application before installation.
"""
import argparse
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from ce_pe import make_imports, build, BASE, CODE, DATA
from keystone import Ks, KS_ARCH_ARM, KS_MODE_ARM

TOKEN = b'ZZUNE-FIXTURE-001'
OBJECT = 0x040000a5
NAMES = ['SignalStarted', 'Sleep', 'LoadLibraryW', 'GetProcAddressW', 'CreateFileW',
         'GetFileSize', 'ReadFile', 'SetFilePointer', 'WriteFile', 'FlushFileBuffers',
         'CloseHandle', 'GetCurrentPermissions', 'LocalAlloc', 'LocalFree', 'ExitThread']
RAW_NAMES = NAMES + ['CeGetCurrentTrust', 'SetKMode', 'SetProcPermissions', 'ReadProcessMemory', 'DeviceIoControl']

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--coredll', type=Path, help='Optional local original DLL; defaults to published ordinal metadata')
    parser.add_argument('--imports-manifest', type=Path, default=ROOT/'app/assets/helpers.json')
    parser.add_argument('--zig', type=Path, required=True)
    parser.add_argument('--work-dir', type=Path, required=True)
    parser.add_argument('--output-dir', type=Path, required=True)
    args = parser.parse_args()
    args.work_dir.mkdir(parents=True, exist_ok=False)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    export_ordinals = None
    if args.coredll is None:
        metadata = json.loads(args.imports_manifest.read_text(encoding='utf-8'))
        export_ordinals = {name: int(ordinal) for ordinal, name in metadata['files']['backup-raw']['ordinals'].items()}
    def imports_for(names):
        if args.coredll is not None:
            return make_imports(names, args.coredll)
        # Rebuild import metadata only, with no Microsoft DLL input or code.
        raw = bytearray(40); ilt = 0x5000 + len(raw)
        thunks = b''.join(struct.pack('<I', export_ordinals[name] | 0x80000000) for name in names) + bytes(4)
        raw += thunks; iat = 0x5000 + len(raw); raw += thunks
        dll = 0x5000 + len(raw); raw += b'coredll.dll\0'
        struct.pack_into('<5I', raw, 0, ilt, 0, 0, dll, iat)
        return bytes(raw), iat, {name: BASE + iat + index*4 for index, name in enumerate(names)}
    original = (Path(__file__).parent / 'backup_nk.c').read_text()
    prefix = original.split('static U copy_nk(void)')[0]
    raw = prefix.replace('config104.h', 'config104.h').replace('"ZTEST1BACKUP104",TOKEN104,104', '"ZTEST1RAW109",TOKEN104,109')
    raw += (Path(__file__).parent / 'backup_raw.inc').read_text().replace('CAPACITY104', 'CAPACITY104')
    manifest = {'schema': 1, 'original_project_code_only': True, 'files': {}}
    for name, source, names, capacity, magic, version in [
        ('backup-nk', original, NAMES, 16*1024*1024, b'ZTEST1BACKUP104', 104),
        ('backup-raw', raw, RAW_NAMES, 4*1024*1024, b'ZTEST1RAW109', 109)
    ]:
        folder = args.work_dir / name; folder.mkdir()
        idata, iat, imports = imports_for(names)
        (folder / 'ce_imports.h').write_text(''.join('#define IAT_' + n + ' ' + hex(a) + 'u\n' for n, a in imports.items()))
        (folder / 'config104.h').write_text('#define TOKEN104 {' + ','.join(str(n) for n in TOKEN) + '}\n'
            + f'#define CAPACITY104 {capacity}u\n#define OBJECT104 {OBJECT}u\n')
        (folder / 'helper.c').write_text(source)
        (folder / 'layout.ld').write_text('ENTRY(entry)\nSECTIONS { .text 0x11000 : { KEEP(*(.text.entry)) *(.text*) } .data 0x13000 : { *(.rodata*) *(.data*) *(.bss*) *(COMMON) } /DISCARD/ : { *(.ARM.exidx*) *(.ARM.extab*) *(.eh_frame*) *(.comment*) *(.note*) } }\n')
        elf_path = folder / 'helper.elf'
        subprocess.run([str(args.zig), 'cc', '-target', 'arm-freestanding-eabi', '-mcpu=arm1136jf_s',
            '-marm', '-Oz', '-ffreestanding', '-fno-builtin', '-fno-stack-protector', '-fshort-wchar',
            '-fno-unwind-tables', '-fno-asynchronous-unwind-tables', '-nostdlib', '-mno-unaligned-access',
            '-Wl,-T,' + str(folder / 'layout.ld'), '-Wl,-e,entry', '-Wl,--build-id=none',
            str(folder / 'helper.c'), '-o', str(elf_path)], check=True, capture_output=True)
        elf = elf_path.read_bytes()
        offset = struct.unpack_from('<I', elf, 32)[0]
        size, count, strings = struct.unpack_from('<HHH', elf, 46)
        sections = [struct.unpack_from('<10I', elf, offset + i*size) for i in range(count)]
        string_section = sections[strings]
        labels = elf[string_section[4]:string_section[4]+string_section[5]]
        blobs = {}
        for row in sections:
            label = labels[row[0]:].split(b'\0')[0].decode()
            if label in ('.text', '.data'):
                blobs[label] = (row[3], elf[row[4]:row[4]+row[5]])
        if blobs['.text'][0] != BASE+CODE or blobs['.data'][0] != BASE+DATA:
            raise ValueError('Unexpected linker layout')
        image = bytes(build(blobs['.text'][1], blobs['.data'][1], idata, iat, len(names)))
        marker = struct.pack('<16s16s8I', magic, TOKEN, version, capacity, OBJECT, 0, 0, 0, 0, 0)
        if image.count(marker) != 1:
            raise ValueError('Carrier binding marker is not unique')
        filename = name + '.template.exe'
        (args.output_dir / filename).write_bytes(image)
        # Import names/ordinals are public metadata; DLL bytes are not copied.
        import pefile
        pe = pefile.PE(data=image)
        ordinals = {str(imp.ordinal): names[i] for i, imp in enumerate(pe.DIRECTORY_ENTRY_IMPORT[0].imports)}
        manifest['files'][name] = {'filename': filename, 'sha256': hashlib.sha256(image).hexdigest(),
            'bytes': len(image), 'binding_offset': image.index(marker), 'template_header_hex': marker.hex(),
            'capacity': capacity, 'version': version, 'magic': magic.decode(), 'ordinals': ordinals}
    idata, iat, imports = imports_for(['SignalStarted', 'ExitThread'])
    assembly = f'mov r0, #85; ldr ip, ={imports["SignalStarted"]}; ldr ip, [ip]; blx ip; mov r0, #0; ldr ip, ={imports["ExitThread"]}; ldr ip, [ip]; blx ip; b .'
    machine = bytes(Ks(KS_ARCH_ARM, KS_MODE_ARM).asm(assembly, BASE+CODE)[0])
    neutral = bytes(build(machine, b'\0', idata, iat, 2))
    (args.output_dir / 'neutral-qtk.exe').write_bytes(neutral)
    manifest['files']['neutral-qtk'] = {'filename': 'neutral-qtk.exe', 'bytes': len(neutral), 'sha256': hashlib.sha256(neutral).hexdigest()}
    (args.output_dir / 'helpers.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(json.dumps({k: {'bytes': v['bytes'], 'sha256': v['sha256']} for k, v in manifest['files'].items()}, indent=2))

if __name__ == '__main__':
    main()
