#!/usr/bin/env python3
"""Independently inspect a stopped lab world's RegionLib headers, coordinates and saved markers.

Requires nbtlib. External overflow entries are deliberately rejected, not silently omitted.
"""
import argparse
from collections import Counter
import gzip
import hashlib
import io
import json
from pathlib import Path
import struct

import nbtlib


def inspect(world):
    regions = world / 'region3d'
    if list(regions.glob('*.ext')):
        raise ValueError('External overflow entries are unsupported by this reader')
    level = nbtlib.load(world / 'level.dat')
    metadata = nbtlib.load(world / 'data/cubicChunksData.dat')['data']
    registry = {int(entry['V']): str(entry['K']) for entry in level['FML']['Registries']['minecraft:blocks']['ids']}
    expected = {(x, y, z) for base_x in [128, 160] for x in range(base_x, base_x + 4)
                for z in range(128, 132) for y in range(-8, 24)}
    verified, heights, files = set(), Counter(), []
    for path in sorted(regions.glob('*.3dr')):
        region = tuple(map(int, path.stem.split('.')))
        body = path.read_bytes()
        if len(body) < 16384: raise ValueError('Truncated header: ' + str(path))
        files.append({'name': path.name, 'bytes': len(body), 'sha256': hashlib.sha256(body).hexdigest()})
        for index, (packed,) in enumerate(struct.iter_unpack('>I', body[:16384])):
            if not packed: continue
            offset, sectors = (packed >> 8) * 512, packed & 255
            if not sectors or offset < 16384 or offset + 4 > len(body):
                raise ValueError(f'Invalid entry: {path}:{index}')
            length, = struct.unpack_from('>I', body, offset)
            if length + 4 > sectors * 512 or offset + 4 + length > len(body):
                raise ValueError(f'Truncated payload: {path}:{index}')
            cube = nbtlib.File.parse(io.BytesIO(gzip.decompress(body[offset + 4:offset + 4 + length])))['Level']
            coords = tuple(int(cube[key]) for key in ['x', 'y', 'z'])
            indexed = (region[0] * 16 + (index >> 8), region[1] * 16 + ((index >> 4) & 15), region[2] * 16 + (index & 15))
            if coords != indexed: raise ValueError(f'Coordinate mismatch: {path}:{index}')
            heights[coords[1]] += 1
            if coords in expected:
                section, = cube['Sections']
                cell = (8 << 8) | (8 << 4) | 8
                block_id = int(section['Blocks'][cell]) & 255
                if 'Add' in section:
                    block_id |= ((int(section['Add'][cell // 2]) & 255) >> (4 * (cell & 1)) & 15) << 8
                if registry.get(block_id) != 'minecraft:gold_block':
                    raise ValueError('Saved marker missing at cube ' + str(coords))
                verified.add(coords)
    passed = (verified == expected and int(metadata['minHeight']) == -128
              and int(metadata['maxHeight']) == 384 and bool(metadata['isCubicChunks']))
    return {'schema': 'cubiclab.world-inspection.v1', 'passed': passed, 'world': str(world.resolve()),
            'generator': str(level['Data']['generatorName']), 'seed': int(level['Data']['RandomSeed']),
            'minY': int(metadata['minHeight']), 'maxYExclusive': int(metadata['maxHeight']),
            'storage': str(metadata['storageFormat']), 'expectedMarkers': len(expected), 'verifiedMarkers': len(verified),
            'savedCubes': sum(heights.values()), 'savedCubeCountsByY': dict(sorted(heights.items())), 'regions': files,
            'registeredSusyDeposits': 'susy:deposit_block' in registry.values(),
            'registeredSusyHostRock': 'susy:susy_stone_smooth' in registry.values(),
            'loadedModIds': sorted(str(entry['ModId']) for entry in level['FML']['ModList']),
            'limits': 'Stopped-world inspection. Verifies RegionLib coordinates and every lab gold marker; not terrain parity, biome correctness or progression balance.'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('world', type=Path)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inspect(args.world)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({key: result[key] for key in ['passed', 'savedCubes', 'verifiedMarkers']}))
    raise SystemExit(0 if result['passed'] else 1)
