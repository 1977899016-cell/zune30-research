"""Check already-created LOCAL backups. This tool DOES NOT create device backups.

Outputs hashes and structure only; the inventory is private and stays local.
"""
import argparse
import hashlib
import json
from pathlib import Path
from ce_bin import parse

def check(nk, nor, disk_prefix, legacy):
    image = parse(nk)
    if len(nor) != 2 * 1024 * 1024:
        raise ValueError('Expected complete 2 MiB NOR from this research layout')
    if len(disk_prefix) < 1024 * 1024 or len(disk_prefix) % 512:
        raise ValueError('Expected sector-aligned disk prefix of at least 1 MiB')
    if len(legacy) != 65536 or nor[0x70000:0x80000] != legacy:
        raise ValueError('Legacy vault does not match the ORIGINAL NOR backup region')
    rows = {}
    for name, data in [('original_nk', nk), ('original_nor', nor),
                       ('original_disk_prefix', disk_prefix), ('original_legacy_vault', legacy)]:
        rows[name] = {'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
    return {
        'scope': 'Local backup structure/integrity check; does not prove physical origin or recoverability',
        'files': rows, 'nk_record_checksums_valid': True, 'nk_records': len(image.records),
        'vault_matches_original_nor_region': True, 'backup_created_by_this_tool': False,
        'physical_recovery_tested_by_this_tool': False, 'device_accessed': False,
        'owner_must_independently_confirm_same_unit': True, 'keep_this_inventory_private': True
    }

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--original-nk', type=Path, required=True)
    parser.add_argument('--nor', type=Path, required=True)
    parser.add_argument('--disk-prefix', type=Path, required=True)
    parser.add_argument('--legacy-vault', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Refusing to overwrite an existing inventory')
    result = check(args.original_nk.read_bytes(), args.nor.read_bytes(),
                   args.disk_prefix.read_bytes(), args.legacy_vault.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(result, stream, indent=2)
    print(json.dumps(result, indent=2))

if __name__ == '__main__':
    main()
