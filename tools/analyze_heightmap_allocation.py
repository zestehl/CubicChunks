#!/usr/bin/env python3
"""Export a synthetic heightmap allocation diagnostic from mixed Gradle/JSONL logs.

Use --log cleanroom=heightmap-cleanroom.log --log forge=heightmap-forge.log.
This consumes TestServerHeightMapSerialization.main output. It does not run Java,
build the mod, or launch Minecraft. Matplotlib is needed for PNG/SVG exports.
"""

import argparse
from collections import defaultdict
import json
from pathlib import Path
from statistics import median

from analyze_cubic_profile import labeled_paths, provenance, write_csv, trim_svg


MODES = ('legacy_default32', 'current_presized')


def parse_log(path):
    metadata, observations = None, []
    for line in path.read_text(encoding='utf-8-sig').splitlines():
        line = line.strip()
        if not line.startswith('{'):
            continue
        row = json.loads(line)
        if row.get('diagnostic') == 'heightmap_serialization':
            if metadata is not None:
                raise ValueError('Multiple diagnostic runs in one log: ' + str(path))
            metadata = row
        elif 'fixture' in row:
            observations.append(row)
    if metadata is None or not observations:
        raise ValueError('Missing heightmap diagnostic records: ' + str(path))
    groups = defaultdict(list)
    for row in observations:
        if row['mode'] not in MODES or row['iterations'] != metadata['iterations']:
            raise ValueError('Inconsistent diagnostic mode or iteration count')
        if row['iterations'] <= 0 or row['thread_allocated_bytes'] < 0 or row['elapsed_ns'] < 0:
            raise ValueError('Invalid diagnostic counters')
        row['allocated_bytes_per_call'] = row['thread_allocated_bytes'] / row['iterations']
        row['elapsed_ns_per_call'] = row['elapsed_ns'] / row['iterations']
        groups[(row['fixture'], row['mode'])].append(row)
    fixtures = list(dict.fromkeys(row['fixture'] for row in observations))
    for fixture in fixtures:
        expected_sizes = set()
        for mode in MODES:
            group = groups[(fixture, mode)]
            if sorted(row['sample'] for row in group) != list(range(metadata['samples'])):
                raise ValueError('Incomplete or duplicate batches for ' + fixture + '/' + mode)
            expected_sizes.update(row['serialized_bytes'] for row in group)
        if len(expected_sizes) != 1:
            raise ValueError('Serialized output sizes disagree: ' + fixture)
    summaries = []
    for (fixture, mode), group in groups.items():
        values = [row['allocated_bytes_per_call'] for row in group]
        durations = [row['elapsed_ns_per_call'] for row in group]
        summaries.append({'fixture': fixture, 'mode': mode, 'samples': len(group),
                          'serialized_bytes': group[0]['serialized_bytes'],
                          'median_bytes_per_call': median(values), 'minimum_bytes_per_call': min(values),
                          'maximum_bytes_per_call': max(values), 'median_ns_per_call': median(durations),
                          'minimum_ns_per_call': min(durations), 'maximum_ns_per_call': max(durations)})
    return metadata, observations, summaries


def plot(report, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10, 'text.color': '#262626',
                         'axes.labelcolor': '#262626', 'svg.fonttype': 'none'})
    fig, axes = plt.subplots(1, len(report['runs']), figsize=(7 * len(report['runs']), 6),
                             squeeze=False, layout='constrained')
    fig.get_layout_engine().set(rect=(0, .25, 1, .75))
    maximum = max(row['maximum_bytes_per_call'] for run in report['runs'] for row in run['summaries']) * 1.25
    for axis, run in zip(axes[0], report['runs']):
        fixtures = list(dict.fromkeys(row['fixture'] for row in run['summaries']))
        grouped = {(row['fixture'], row['mode']): row for row in run['summaries']}
        for mode, offset, color, label in (
            ('legacy_default32', -.18, '#aaaaaa', 'Legacy default 32-byte buffer'),
            ('current_presized', .18, '#2f6690', 'Current presized buffer')):
            entries = [grouped[(fixture, mode)] for fixture in fixtures]
            values = [row['median_bytes_per_call'] for row in entries]
            positions = [index + offset for index in range(len(fixtures))]
            lower = [row['median_bytes_per_call'] - row['minimum_bytes_per_call'] for row in entries]
            upper = [row['maximum_bytes_per_call'] - row['median_bytes_per_call'] for row in entries]
            axis.barh(positions, values, height=.32, color=color, label=label, xerr=[lower, upper],
                      capsize=3, error_kw={'ecolor': '#262626', 'linewidth': 1})
            for position, value in zip(positions, values):
                axis.annotate(f'{value:,.0f} B', (value, position), xytext=(4, 0),
                              textcoords='offset points', va='center', fontsize=9)
        labels = [fixture.replace('_', ' ') + '\n' + f"{grouped[(fixture, MODES[0])]['serialized_bytes']:,} B output"
                  for fixture in fixtures]
        axis.set_yticks(range(len(fixtures)), labels)
        axis.invert_yaxis()
        axis.set_xlim(0, maximum)
        axis.ticklabel_format(axis='x', style='plain')
        axis.set_xlabel('Thread-allocated bytes per serialization call')
        axis.set_title(run['label'].title() + ' / Java ' + run['metadata']['java'], loc='left', fontweight='bold')
        axis.spines[['top', 'right']].set_visible(False)
        axis.grid(axis='x', alpha=.2)
        axis.set_axisbelow(True)
    handles, labels = axes[0][0].get_legend_handles_labels()
    legend = fig.legend(handles, labels, loc='lower center', bbox_to_anchor=(.5, .15), ncols=2, frameon=False)
    legend.set_in_layout(False)
    fig.suptitle('Heightmap serialization allocation\nSynthetic fixture diagnostic; median and full observed range of measured batches',
                 x=.01, ha='left', fontsize=14)
    settings = '; '.join(run['label'] + ': ' + str(run['metadata']['samples']) + ' batches × '
                         + format(run['metadata']['iterations'], ',') + ' calls after '
                         + format(run['metadata']['warmup'], ',') + ' warmups per mode' for run in report['runs'])
    fig.text(.01, .025, settings + '\nThreadMXBean counter deltas, not JFR samples or retained heap. Same writer; legacy buffer policy recreated in a MethodHandle wrapper.\n'
             'Results escape; order alternates. Output byte equality checked by the diagnostic. No native-world throughput or overall speedup claim.', fontsize=8.5)
    for extension in ('png', 'svg'):
        fig.savefig(output / ('heightmap-allocation.' + extension), dpi=160, bbox_inches='tight')
        trim_svg(output / ('heightmap-allocation.' + extension))
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--log', action='append', required=True, metavar='LABEL=LOG')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--no-chart', action='store_true')
    args = parser.parse_args()
    report = {'schema': 'cubicchunks.heightmap-allocation-diagnostic.v1', 'runs': [],
              'scope': 'Synthetic standalone mapped-API heightmap fixtures; no Minecraft server or player world.',
              'semantics': 'ThreadMXBean counter deltas divided by measured calls. Includes wrapper and result allocation. '
                           'Not JFR sample weights, retained heap, or a controlled whole-server speedup. '
                           'Three batches in one JVM per runtime; legacy uses unchanged writer through a MethodHandle.',
              'analyzer': provenance(Path(__file__))}
    for label, paths in labeled_paths(args.log).items():
        if len(paths) != 1:
            raise ValueError('One diagnostic log per label is required')
        metadata, observations, summaries = parse_log(paths[0])
        report['runs'].append({'label': label, 'input': provenance(paths[0]), 'metadata': metadata,
                               'observations': observations, 'summaries': summaries})
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sample_rows = [dict(row, run=run['label'], java=run['metadata']['java'])
                   for run in report['runs'] for row in run['observations']]
    summary_rows = [dict(row, run=run['label'], java=run['metadata']['java'])
                    for run in report['runs'] for row in run['summaries']]
    write_csv(output / 'heightmap-allocation-samples.csv', sample_rows,
              ['run', 'java', 'fixture', 'mode', 'sample', 'serialized_bytes', 'iterations',
               'thread_allocated_bytes', 'elapsed_ns', 'allocated_bytes_per_call', 'elapsed_ns_per_call'])
    write_csv(output / 'heightmap-allocation-summary.csv', summary_rows,
              ['run', 'java', 'fixture', 'mode', 'samples', 'serialized_bytes', 'median_bytes_per_call',
               'minimum_bytes_per_call', 'maximum_bytes_per_call', 'median_ns_per_call', 'minimum_ns_per_call', 'maximum_ns_per_call'])
    (output / 'heightmap-allocation.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    if not args.no_chart:
        plot(report, output)
    print(json.dumps({'runs': len(report['runs']), 'observations': len(sample_rows), 'output': str(output)}))


if __name__ == '__main__':
    main()
