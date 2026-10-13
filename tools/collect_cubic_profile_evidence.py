#!/usr/bin/env python3
"""Collect receipts for this native profiling pass from the Riven workspace."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil


def fingerprint(path):
    with path.open('rb') as source:
        digest = hashlib.file_digest(source, 'sha256').hexdigest()
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest}


def normalized_errors(errors, instance):
    result = Counter()
    for message, count in errors.items():
        # Different disposable roots and Java object identities are not different failures.
        message = message.replace(str(instance), '<instance>').replace(instance.as_posix(), '<instance>')
        message = re.sub(r'@[0-9a-f]{1,16}\b', '@<identity>', message)
        result[message] += count
    return dict(sorted(result.items()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--riven-workspace', type=Path, required=True)
    args = parser.parse_args()
    root = args.riven_workspace.resolve()
    out = Path(__file__).resolve().parents[1] / 'docs/measurements/cubic-profile-pass1/evidence'
    out.mkdir(parents=True, exist_ok=True)
    runs = []
    observations = {}
    for variant in ('baseline', 'candidate'):
        for loader in ('cleanroom', 'forge'):
            name = f'cubic-profile-{variant}-{loader}-01'
            instance = root / '.local/instances' / name
            receipt_path = instance / 'riven-instance.json'
            receipt = json.loads(receipt_path.read_text())
            cubic = next(mod for mod in receipt['mods'] if mod['slug'] == 'cubicchunks')
            for mode in ('write', 'read'):
                label = f'{loader}-{variant}-{mode}'
                result_path = instance / f'cubic-{mode}-result.json'
                result = json.loads(result_path.read_text())
                probe_path = instance / f'cubic-profile-{mode}.json'
                probe = json.loads(probe_path.read_text())
                if not result['passed'] or not probe['passed']:
                    raise ValueError(f'Unsuccessful qualification run: {label}')
                log_path = instance / f'cubic-{mode}-console.log'
                text = re.sub(r'\x1b\[[0-9;]*m', '', log_path.read_text(errors='replace'))
                errors = Counter(re.findall(r'\[[^\]\n]*/ERROR\] (.*)', text))
                data = {'label': label, 'instance': name, 'loader': loader, 'variant': variant,
                    'mode': mode, 'cubic': cubic, 'riven': receipt['riven'],
                    'receipt': fingerprint(receipt_path), 'result': result,
                    'probe': probe, 'log': fingerprint(log_path), 'errors': dict(sorted(errors.items())),
                    'normalized_errors': normalized_errors(errors, instance)}
                recording = instance / f'cubic-{mode}-profile.jfr'
                if recording.exists():
                    data['jfr'] = fingerprint(recording)
                saved = root / '.local/cubic-profile' / f'{variant}-{loader}-saved.json'
                data['saved_world'] = json.loads(saved.read_text())
                if not data['saved_world']['saved_fixture_checks_passed']:
                    raise ValueError(f'Saved-world checks failed: {label}')
                (out / f'{label}.json').write_text(json.dumps(data, indent=2) + '\n')
                observations[(variant, loader, mode)] = data
                runs.append({'label': label, 'artifact': cubic['sha256'], 'passed': True,
                    'probe_sha256': fingerprint(probe_path)['sha256']})
    harness = [root / 'tools/experiment_cubic.py',
        root / 'experiments/cubic/src/main/java/supersymmetry/riven/experiment/CubicProfileProbe.java',
        root / 'experiments/cubic/src/main/java/io/github/opencubicchunks/cubicchunks/core/server/chunkio/CubicSnapshotProbe.java']
    for source in harness:
        shutil.copy2(source, out / source.name)
    fields = ['seed', 'saved_cubes', 'block_counts', 'fixtures', 'lights', 'tiles', 'cube_y_counts']
    comparisons = []
    for loader in ('cleanroom', 'forge'):
        baseline = observations[('baseline', loader, 'write')]['saved_world']
        candidate = observations[('candidate', loader, 'write')]['saved_world']
        comparisons.append({'scope': f'{loader}: baseline vs candidate saved world',
            'fields_equal': {key: baseline[key] == candidate[key] for key in fields}})
        for mode in ('write', 'read'):
            baseline_errors = observations[('baseline', loader, mode)]['normalized_errors']
            candidate_errors = observations[('candidate', loader, mode)]['normalized_errors']
            comparisons.append({'scope': f'{loader}: baseline vs candidate {mode} errors',
                'signatures_and_counts_equal': baseline_errors == candidate_errors,
                'baseline_count': sum(baseline_errors.values()), 'candidate_count': sum(candidate_errors.values())})
    for variant in ('baseline', 'candidate'):
        cleanroom = observations[(variant, 'cleanroom', 'write')]['saved_world']
        forge = observations[(variant, 'forge', 'write')]['saved_world']
        comparisons.append({'scope': f'{variant}: Cleanroom vs Forge saved world',
            'fields_equal': {key: cleanroom[key] == forge[key] for key in fields}})
    (out / 'manifest.json').write_text(json.dumps({'runs': runs, 'comparisons': comparisons,
        'error_normalization': 'Replace each disposable instance root and Java object identity suffixes; preserve other message text and counts.',
        'harness': [fingerprint(source) for source in harness],
        'limits': ['One process per loader/variant/mode on one host; no controlled speedup claim.',
            'Three batches are different coordinates and JIT states, not independent runs.',
            'Save phases include all dirty loaded cubes and columns, including spawn.',
            'Callback and snapshot native fixtures run after the timed phases.',
            'Native async cancellation, client rendering and long-running stress remain unqualified.']}, indent=2) + '\n')
    print(out)


if __name__ == '__main__':
    main()
