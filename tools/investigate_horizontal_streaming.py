#!/usr/bin/env python3
"""Retain streaming source/profile evidence and synthetic request-order diagnostics; starts no game."""
import argparse
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess

FORK = Path(__file__).resolve().parents[1]


def fingerprint(path):
    return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'bytes': path.stat().st_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--riven-workspace', type=Path, default=FORK.parents[1])
    parser.add_argument('--riven-jar', type=Path, required=True, help='Retained Riven binary; its cache is exercised without loading Minecraft')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); root = args.riven_workspace.resolve(); output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    classes = root / '.local/cubic-lab' / (output.name + '-cache-probe')
    classes.mkdir(parents=True, exist_ok=False)
    settings = json.loads((root / '.local/settings.json').read_text(encoding='utf-8-sig'))
    java = settings['java25']; javac = str(Path(java).with_name('javac.exe' if os.name == 'nt' else 'javac'))
    binary = args.riven_jar.resolve(strict=True); source = FORK / 'tools/diagnostics/RivenAreaCacheDiagnostic.java'
    compile_command = [javac, '--release', '8', '-encoding', 'UTF-8', '-cp', str(binary), '-d', str(classes), str(source)]
    subprocess.run(compile_command, check=True)
    command = [java, '-cp', os.pathsep.join([str(classes), str(binary)]), 'supersymmetry.riven.tools.RivenAreaCacheDiagnostic']
    completed = subprocess.run(command, check=True, capture_output=True, text=True)
    cache_rows = list(csv.DictReader(io.StringIO(completed.stdout)))
    (output / 'area-cache-request-orders.csv').write_text(completed.stdout, encoding='utf-8')

    historical = FORK / 'docs/measurements/lighting-current-runtime'
    report_file = historical / 'results.json'; profile_file = historical / 'jfr/summary.json'
    report = json.loads(report_file.read_text()); profile = json.loads(profile_file.read_text())
    server_profile = next(run for run in profile['runs'] if run['label'] == 'write-server')
    scopes = [scope for scope in server_profile['scopes'] if scope['name'] in ['horizontal', 'vertical']]
    observations = []
    for run in report['runs']:
        for scenario in run['result']['scenarios']:
            if scenario['scenario'] not in ['horizontal', 'vertical']: continue
            server = scenario['server']; scope = next(s for s in scopes if s['name'] == scenario['scenario'])
            observations.append({'scenario': scenario['scenario'], 'ticks': server['serverTicks'],
                                 'operations': server['operations'], 'cubeDataSaveEvents': server['cubeDataSaveEvents'],
                                 'packets': server['packets'], 'execution': scope['execution'], 'gc': scope['gc']})

    # Exact inclusive boxes used by CuboidalCubeSelector. This is geometry, not generated-cube telemetry.
    def visible(center):
        x, y, z = center
        return {(a, b, c) for a in range(x - 3, x + 4) for b in range(y - 3, y + 4) for c in range(z - 3, z + 4)}
    old = visible((0, 0, 0)); old_columns = {(x, z) for x, y, z in old}
    geometry = []
    for name, position in [('one_cube_horizontal', (1, 0, 0)), ('one_cube_vertical', (0, 1, 0)),
                           ('horizontal_lab_teleport', (16, 0, 0))]:
        new = visible(position); new_columns = {(x, z) for x, y, z in new}
        geometry.append({'movement': name, 'new_visible_cubes': len(new - old),
                         'new_visible_columns': len(new_columns - old_columns), 'visible_cubes': 343, 'visible_columns': 49})
    with (output / 'visibility-geometry.csv').open('w', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, geometry[0]); writer.writeheader(); writer.writerows(geometry)

    paths = ['src/main/java/io/github/opencubicchunks/cubicchunks/core/server/PlayerCubeMap.java',
             'src/main/java/io/github/opencubicchunks/cubicchunks/core/server/CubeWatcher.java',
             'src/main/java/io/github/opencubicchunks/cubicchunks/core/server/CubeProviderServer.java',
             'src/main/java/io/github/opencubicchunks/cubicchunks/core/server/chunkio/async/forge/AsyncWorldIOExecutor.java',
             'src/main/java/io/github/opencubicchunks/cubicchunks/core/server/chunkio/async/forge/AsyncTaskCompletion.java',
             'src/main/java/io/github/opencubicchunks/cubicchunks/core/visibility/CuboidalCubeSelector.java',
             'CubicChunksAPI/src/main/java/io/github/opencubicchunks/cubicchunks/api/worldgen/ICubeGenerator.java']
    riven_paths = ['experiments/cubic/src/main/java/supersymmetry/riven/experiment/CubicProbeWorldType.java',
                   'src/main/java/supersymmetry/riven/world/RivenBiomeProvider.java',
                   'src/main/java/supersymmetry/riven/model/preparation/TerrainPreparation.java',
                   'src/main/java/supersymmetry/riven/model/preparation/PreparationService.java',
                   'src/main/java/supersymmetry/riven/model/preparation/SessionPreparationCache.java']
    evidence = {'schema': 'cubiclab.horizontal-source-audit.v1', 'capturedUtc': datetime.now(timezone.utc).isoformat(),
                'sourceRevision': subprocess.check_output(['git', '-C', str(FORK), 'rev-parse', 'HEAD'], text=True).strip(),
                'source': [fingerprint(FORK / path) for path in paths],
                'rivenSource': [fingerprint(root / path) for path in riven_paths],
                'frozenRiven': fingerprint(binary), 'cacheProbe': fingerprint(source),
                'compileCommand': compile_command, 'command': command,
                'historicalReport': fingerprint(report_file), 'historicalProfile': fingerprint(profile_file),
                'historicalRuntime': report['environment']['runtimeVersion'],
                'historicalRiven': report['environment']['riven'], 'observations': observations,
                'visibilityGeometry': geometry,
                'limits': ['Historical streaming run predates storage pacing and the frozen Riven preparation-worker binary.',
                           'Cache diagnostic uses the real selected cache with synthetic values/orders; no native cache-miss telemetry or timings.',
                           'Visibility geometry describes requests, not actual cube generations or costs; vertical lab route has different displacement and prior-area reuse.',
                           'JFR stack-path samples are not exclusive CPU time; no new game run, production patch or build.']}
    (output / 'evidence.json').write_text(json.dumps(evidence, indent=2) + '\n', encoding='utf-8')

    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 2, figsize=(12, 5.5))
    fig.subplots_adjust(left=.09, right=.97, top=.82, bottom=.28, wspace=.55)
    labels = ['Horizontal', 'Vertical']; ys = [0, 1]
    axes[0].barh(ys, [o['ticks']['p95Ms'] for o in observations], color='#2f6690', height=.5)
    axes[0].scatter([o['ticks']['maxMs'] for o in observations], ys, color='#a85b3b', marker='D', label='Maximum', zorder=3)
    axes[0].set_yticks(ys, labels); axes[0].invert_yaxis(); axes[0].axvline(50, color='#777', linestyle='--')
    axes[0].set_title('Retained in-game tick p95 and maximum', loc='left'); axes[0].set_xlabel('Milliseconds')
    axes[0].set_xlim(0, 145); axes[0].legend(frameon=False, loc='upper right')
    patterns = [('columns_then_level_sweeps', 'Columns first, then level sweeps', '#a85b3b'),
                ('columns_then_column_groups', 'Columns first, then cube groups', '#2f6690'),
                ('column_then_its_cubes', 'Each column, then its cubes', '#4a8059')]
    for key, label, color in patterns:
        rows = [row for row in cache_rows if row['pattern'] == key]
        axes[1].plot([int(row['capacity']) for row in rows], [int(row['area_preparations']) for row in rows],
                     marker='o', color=color, label=label)
    axes[1].axvline(32, color='#777', linestyle='--'); axes[1].set_xlabel('Retained prepared-area capacity')
    axes[1].set_ylabel('Area loader invocations'); axes[1].set_title('Synthetic orders: 49 areas, 7 cube levels', loc='left')
    axes[1].set_ylim(bottom=0); axes[1].legend(frameon=False, fontsize=8)
    for axis in axes:
        axis.spines[['top', 'right']].set_visible(False); axis.grid(alpha=.2); axis.set_axisbelow(True)
    fig.suptitle('Horizontal streaming: measured tails and a cache-reuse hypothesis', x=.02, ha='left')
    fig.text(.02, .035, 'Left: retained Cleanroom 0.7.0-alpha run, 240 ticks/route, earlier Riven binary; bars=p95, diamonds=max, line=50 ms.\n'
             'Right: selected Riven binary cache with synthetic request order; line=32 areas. This is not native miss telemetry or a speedup.\n'
             'The two panels have independent units and evidence scopes; current production behavior was not modified.', fontsize=9)
    for suffix in ['png', 'svg']:
        path = output / ('horizontal-investigation.' + suffix)
        fig.savefig(path, dpi=160, bbox_inches='tight', metadata={'Date': None} if suffix == 'svg' else None)
        if suffix == 'svg': path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines()) + '\n')
    plt.close(fig)
    print(json.dumps({'historicalScenarios': len(observations), 'cacheOrders': len(cache_rows), 'output': str(output)}))


if __name__ == '__main__':
    main()
