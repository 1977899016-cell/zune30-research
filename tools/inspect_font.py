"""Inspect a user-supplied font locally; no device access or font redistribution."""
import argparse
import hashlib
import json
import sys
from pathlib import Path


def inspect(path):
    from fontTools.ttLib import TTFont
    path = Path(path)
    with TTFont(path, fontNumber=0) as font:
        cmap = font.getBestCmap() or {}
        families = sorted({n.toUnicode() for n in font['name'].names if n.nameID in (1, 16)})
    ranges = {'han': (0x4e00, 0x9fff), 'hiragana': (0x3040, 0x309f),
              'katakana': (0x30a0, 0x30ff), 'hangul_syllables': (0xac00, 0xd7a3)}
    return {'filename': path.name, 'bytes': path.stat().st_size,
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'families': families,
            'mapped_codepoints': len(cmap),
            'coverage': {name: sum(start <= c <= end for c in cmap) for name, (start, end) in ranges.items()},
            'sample_coverage': {text: all(ord(c) in cmap for c in text)
                                for text in ('中文音乐', '日本語かなカナ', '한국어')},
            'note': 'Cmap coverage alone does not prove native device rendering.'}


if __name__ == '__main__':
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('font')
    args = parser.parse_args()
    print(json.dumps(inspect(args.font), ensure_ascii=False, indent=2))
