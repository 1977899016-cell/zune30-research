"""Prepare an uncompressed CE default.fdf OFFLINE; never touches NK or USB.

This produces an intermediate registry artifact, not an installable firmware.
Compression, ROM layout, image verification and recovery remain separate work.
"""
import argparse
import json
import struct
from pathlib import Path

MAGIC = bytes.fromhex('b274831d')
LINK = r'Software\Microsoft\FontLink\SystemLink'
FACES = ('Zegoe UI', 'Zegoe UI Light', 'Zegoe UI Semibold')
FONT_PATH = r'\Hard Disk\Fonts\ZuneCJK_UI_20261027.ttf'
LOADER_PATH = r'\Hard Disk\Fonts\ZCJKBoot.exe'


def records(blob):
    if len(blob) < 8 or blob[:4] != MAGIC or struct.unpack_from('<I', blob, 4)[0] != len(blob):
        raise ValueError('Invalid uncompressed FDF header')
    pos, hive, key, result = 8, None, None, []
    while pos < len(blob):
        if pos + 4 > len(blob):
            raise ValueError('Truncated record header')
        size, kind = struct.unpack_from('<HH', blob, pos)
        end = pos + 4 + size
        if end > len(blob):
            raise ValueError('Truncated record body')
        body = blob[pos + 4:end]
        name = typ = data = None
        if kind == 1 and len(body) >= 4:
            hive, chars = struct.unpack_from('<HH', body)
            if hive not in range(4) or size != 4 + 2 * chars:
                raise ValueError('Invalid key record')
            key = body[4:].decode('utf-16-le').rstrip('\0')
        elif kind == 2 and len(body) >= 6 and key is not None:
            typ, chars, count = struct.unpack_from('<HHH', body)
            if size != 6 + 2 * chars + count:
                raise ValueError('Invalid value record')
            name = body[6:6 + 2 * chars].decode('utf-16-le').rstrip('\0')
            data = body[6 + 2 * chars:]
        else:
            raise ValueError('Unknown or misplaced FDF record')
        result.append(dict(raw=blob[pos:end], kind=kind, hive=hive, key=key,
                           name=name, type=typ, data=data))
        pos = end
    return result


def frame(kind, body):
    return struct.pack('<HH', len(body), kind) + body


def value(name, data, typ=1):
    name = (name + '\0').encode('utf-16-le')
    data = (data + '\0').encode('utf-16-le') if isinstance(data, str) else data
    return frame(2, struct.pack('<HHH', typ, len(name) // 2, len(data)) + name + data)


def key_record(hive, key):
    data = (key + '\0').encode('utf-16-le')
    return frame(1, struct.pack('<HH', hive, len(data) // 2) + data)


def pack(rows):
    body = b''.join(r['raw'] for r in rows)
    return MAGIC + struct.pack('<I', len(body) + 8) + body


def values(blob):
    result = {}
    for row in records(blob):
        if row['kind'] != 2:
            continue
        k = row['hive'], row['key'].lower(), row['name'].lower()
        if k in result:
            raise ValueError('Ambiguous duplicate registry value')
        result[k] = row['type'], row['data']
    return result


def init_graph(blob):
    launch, deps = {}, {}
    for (hive, key, name), (typ, data) in values(blob).items():
        if hive != 2 or key != 'init':
            continue
        if name.startswith('launch') and name[6:].isdigit():
            launch[int(name[6:])] = data.decode('utf-16-le').rstrip('\0')
        elif name.startswith('depend') and name[6:].isdigit():
            if typ != 3 or len(data) % 2:
                raise ValueError('Invalid Init dependency value')
            deps[int(name[6:])] = list(struct.unpack('<' + 'H' * (len(data) // 2), data))
    done, order = set(), []
    while True:
        ready = [n for n in sorted(launch) if n not in done and all(x in done for x in deps.get(n, []))]
        if not ready:
            break
        order += ready
        done.update(ready)
    blocked = {str(n): [x for x in deps.get(n, []) if x not in done] for n in launch if n not in done}
    return {'passed': not blocked, 'launch_order': order, 'blocked': blocked, 'dependencies': deps}


def update_key(blob, key, changes):
    rows = records(blob)
    starts = [i for i, r in enumerate(rows) if r['kind'] == 1 and r['hive'] == 2 and r['key'].lower() == key.lower()]
    if len(starts) > 1:
        raise ValueError('Ambiguous duplicate registry key')
    if not starts:
        return blob[:4] + struct.pack('<I', len(blob) + len(key_record(2, key)) + sum(map(len, changes.values()))) + blob[8:] + key_record(2, key) + b''.join(changes.values())
    start = starts[0]
    end = next((i for i in range(start + 1, len(rows)) if rows[i]['kind'] == 1), len(rows))
    seen = set()
    for row in rows[start + 1:end]:
        name = row['name'].lower()
        if name in changes:
            if name in seen:
                raise ValueError('Duplicate target value')
            row['raw'] = changes[name]
            seen.add(name)
    missing = [{'raw': data} for name, data in changes.items() if name not in seen]
    return pack(rows[:end] + missing + rows[end:])


def prepare(blob, family='Zune UI CJK'):
    original = values(blob)
    for n in (20, 30, 60):
        if (2, 'init', 'launch' + str(n)) not in original:
            raise ValueError('Expected original CE Init launch entry missing')
    existing = original.get((2, 'init', 'launch45'))
    if existing and existing != (1, (LOADER_PATH + '\0').encode('utf-16-le')):
        raise ValueError('Launch45 belongs to another program; refusing replacement')
    deps_type, deps_data = original.get((2, 'init', 'depend60'), (3, b''))
    if deps_type != 3 or len(deps_data) % 2:
        raise ValueError('Invalid Depend60')
    deps = list(struct.unpack('<' + 'H' * (len(deps_data) // 2), deps_data))
    deps = list(dict.fromkeys(deps + [20, 45]))
    result = update_key(blob, LINK, {face.lower(): value(face, FONT_PATH + ',' + family) for face in FACES})
    result = update_key(result, 'init', {
        'launch45': value('Launch45', LOADER_PATH),
        'depend45': value('Depend45', struct.pack('<H', 30), 3),
        'depend60': value('Depend60', struct.pack('<' + 'H' * len(deps), *deps), 3)})
    after = values(result)
    allowed = {(2, LINK.lower(), face.lower()) for face in FACES} | {(2, 'init', n) for n in ('launch45', 'depend45', 'depend60')}
    if any(after.get(k) != v for k, v in original.items() if k not in allowed):
        raise ValueError('Unrelated registry value changed')
    graph = init_graph(result)
    if not graph['passed']:
        raise ValueError('Startup dependency cycle or missing prerequisite: ' + str(graph['blocked']))
    return result, graph


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--family', default='Zune UI CJK')
    args = parser.parse_args()
    if args.output.exists() or args.source.resolve() == args.output.resolve():
        parser.error('Output must be a new file')
    data, graph = prepare(args.source.read_bytes(), args.family)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(data)
    print(json.dumps({'offline_only': True, 'installable_firmware': False, 'bytes': len(data), 'init_graph': graph}, indent=2))
