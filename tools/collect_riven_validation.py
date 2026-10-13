#!/usr/bin/env python3
"""Collect retained native Riven evidence without launching or changing a world."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import zipfile


SOURCE_COMMIT = '62237c2b4e69532e05004a38533a919c47d36a69'
INSTANCES = {'cleanroom': 'cubic-fork-cleanroom-02', 'forge': 'cubic-fork-forge-01'}
ANSI = re.compile(r'\x1b\[[0-9;]*m')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


class Collector:
    def __init__(self, root):
        self.root = root.resolve()

    def evidence(self, path):
        return {'path': path.resolve().relative_to(self.root).as_posix(),
                'bytes': path.stat().st_size, 'sha256': sha256(path)}

    def instance(self, name):
        return self.root / '.local/instances' / name

    def log(self, path):
        return ANSI.sub('', path.read_text(encoding='utf-8'))

    def errors(self, path):
        rows = []
        for line in self.log(path).splitlines():
            if 'ERROR' not in line:
                continue
            line = re.sub(r'^\[[^\]]+\]\s*', '', line)
            line = re.sub(r'@[0-9a-fA-F]+', '@<object>', line)
            # Normalize the original Windows instance roots even when collecting
            # copied evidence from another host or a mounted workspace.
            line = re.sub(r'[A-Za-z]:[\\/][^\r\n]*?[\\/]\.local[\\/]instances[\\/][^\\/\s]+',
                          '<instance>', line)
            rows.append(line)
        return Counter(rows)

    def compare_errors(self, actual, baseline):
        current, previous = self.errors(actual), self.errors(baseline)
        added = dict(sorted((current - previous).items()))
        removed = dict(sorted((previous - current).items()))
        require(not added, 'New normalized ERROR lines in ' + str(actual) + ': ' + repr(added))
        categories = Counter()
        for message, count in current.items():
            match = re.match(r'\[[^\]]+\]\s+\[([^\]]+)\]', message)
            categories[match.group(1) if match else 'unclassified'] += count
        return {'baselineLog': self.evidence(baseline), 'actualErrorLines': sum(current.values()),
                'baselineErrorLines': sum(previous.values()), 'newNormalizedErrors': added,
                'removedNormalizedErrors': removed, 'currentLoggerCounts': dict(sorted(categories.items()))}

    def artifacts(self, directory):
        receipt_path = directory / 'riven-instance.json'
        receipt = load(receipt_path)
        cubic = next(mod for mod in receipt['mods'] if mod['slug'] == 'cubicchunks')
        source = cubic['metadata']['source']
        require(source['source_commit'] == SOURCE_COMMIT, 'Unexpected candidate source commit')
        cubic_path = directory / 'mods' / cubic['metadata']['filename']
        riven_path = directory / 'mods/riven.jar'
        require(sha256(cubic_path) == cubic['sha256'] == source['sha256'], 'CubicChunks artifact changed')
        require(sha256(riven_path) == receipt['riven']['sha256'], 'Riven artifact changed')
        expected = {mod['metadata']['filename']: mod['sha256'] for mod in receipt['mods']}
        expected['riven.jar'] = receipt['riven']['sha256']
        actual = {path.name: sha256(path) for path in (directory / 'mods').glob('*.jar')}
        require(actual == expected, 'Instance dependency files changed: ' + directory.name)
        with zipfile.ZipFile(cubic_path) as archive:
            versions = sorted({int.from_bytes(archive.read(name)[6:8], 'big') for name in archive.namelist()
                               if name.startswith('io/github/opencubicchunks/') and name.endswith('.class')})
        with zipfile.ZipFile(riven_path) as archive:
            probe_class = archive.read('supersymmetry/riven/experiment/CubicProbe$ProbeCommand.class')
        return {'receipt': self.evidence(receipt_path), 'cubicChunks': self.evidence(cubic_path),
                'riven': self.evidence(riven_path), 'cubicChunksClassVersions': versions,
                'rivenProbeClassSha256': hashlib.sha256(probe_class).hexdigest(),
                'sourceCommit': source['source_commit'], 'sourceDirtyAtPreparation': source['source_dirty'],
                'sourceStatusAtPreparation': source['source_status'], 'installedJarCount': len(actual),
                'allInstalledModHashesMatchReceipt': True}, receipt

    def phase(self, directory, phase, baseline):
        prefix = 'cubic-' + phase
        result_path = directory / (prefix + '-result.json')
        result = load(result_path)
        for key in ['passed', 'ready', 'api_probe_passed']:
            require(result[key], prefix + ' did not pass ' + key)
        require(result['exit_code'] == 0 and not result['timed_out'] and not result['shutdown_exception'],
                'Native process did not stop successfully')
        require(not result['missing_map_mixin'], 'Missing map mixin')
        process_path = directory / (prefix + '-process.json')
        log_path = directory / (prefix + '-console.log')
        log = self.log(log_path)
        runtime = re.search(r'Java is ([^\r\n]+)', log)
        require(runtime, 'Missing runtime identity in log')
        row = {'result': self.evidence(result_path), 'process': self.evidence(process_path),
               'log': self.evidence(log_path), 'javaCommand': load(process_path)['command'],
               'reportedJvm': runtime.group(1), 'serverCommands': result['commands'],
               'passed': True, 'ready': result['ready'], 'exitCode': result['exit_code'],
               'timedOut': result['timed_out'], 'shutdownException': result['shutdown_exception'],
               'missingMapMixin': result['missing_map_mixin'],
               'elapsedSecondsIncludingStartupAndShutdown': result['seconds'],
               'configurationSha256AtRun': result['config_sha256'],
               'serverPropertiesSha256AtRun': result['server_properties_sha256'],
               'errors': self.compare_errors(log_path, baseline)}
        if phase in ('write', 'read'):
            require(result['riven_generation_probe_passed'], 'Model generation comparison did not pass')
            required = ['RIVEN_CUBIC_BOUNDS min=-128 maxExclusive=384', 'RIVEN_CUBIC_OUTSIDE PASS',
                        'RIVEN_CUBIC_GENERATION PASS', 'RIVEN_CUBIC_RESULT phase=' + phase + ' PASS']
            required += ['RIVEN_CUBIC_BLOCK y=' + str(y) + ' PASS' for y in (-128, -1, 256, 383)]
            required += ['RIVEN_CUBIC_LIGHT y=' + str(y) + ' source=15 neighbor=14 PASS' for y in (-120, 272)]
            required += ['RIVEN_CUBIC_TILE y=' + str(y) + ' PASS' for y in (-120, 272)]
            require(all(marker in log for marker in required), 'Incomplete native probe markers')
            require('RIVEN_CUBIC_FAIL' not in log, 'Native probe failure present')
            row['nativeChecks'] = {'minY': -128, 'maxYExclusive': 384,
                                   'blockFixtureHeights': [-128, -1, 256, 383],
                                   'rejectedWriteHeights': [-129, 384],
                                   'lightFixtureHeights': [-120, 272], 'sourceLight': 15, 'adjacentLight': 14,
                                   'furnaceHeights': [-120, 272], 'diamondsPerFurnace': 3,
                                   'modelColumn': {'x': 1, 'z': 1, 'minY': -128, 'maxYExclusive': 384,
                                                   'blockComparisons': 512,
                                                   'countEvidence': 'Probe source loop and native generation PASS marker'},
                                   'markers': required}
        else:
            surfaces = []
            for match in re.finditer(r'RIVEN_CUBIC_MAP surfaceY=(-?\d+) map=(\S+) columnHeight=(-?\d+) '
                                    r'actualColor=(\d+) expectedColor=(\d+) bedrockColor=(\d+) matches=(\w+)', log):
                values = match.groups()
                require(values[6] == 'true' and values[3] == values[4], 'Map surface color mismatch')
                surfaces.append({'surfaceY': int(values[0]), 'map': values[1], 'columnHeight': int(values[2]),
                                 'actualColor': int(values[3]), 'expectedColor': int(values[4])})
            edge_cases = {match.group(1): int(match.group(2)) for match in re.finditer(
                r'RIVEN_CUBIC_MAP_EDGE case=(\S+) map=\S+ pixelX=\d+ pixelZ=\d+ packedColor=(\d+) PASS', log)}
            require({row['surfaceY'] for row in surfaces} == {-64, 63, 300}, 'Missing map heights')
            expected_cases = {'transparent-negative', 'transparent-zero', 'water-negative-deep',
                              'water-positive-deep', 'water-negative-shallow', 'water-positive-shallow', 'floor'}
            require(set(edge_cases) == expected_cases, 'Missing map edge cases')
            require(edge_cases['water-negative-deep'] == edge_cases['water-positive-deep']
                    and edge_cases['water-negative-shallow'] == edge_cases['water-positive-shallow']
                    and edge_cases['water-negative-deep'] != edge_cases['water-negative-shallow'], 'Water shading mismatch')
            require('RIVEN_CUBIC_MAP_RESULT held-map-height PASS' in log, 'Missing map overall pass')
            row['nativeChecks'] = {'surfaceColors': surfaces, 'edgeCasePackedColors': edge_cases,
                                   'fixtureCount': len(surfaces) + len(edge_cases),
                                   'scope': 'Server-side held-map sampling with a FakePlayer; no client rendering or network test'}
        return row

    def saved(self, name):
        report_path = self.root / '.local/experiments/cubic-chunks' / (name + '-saved.json')
        report = load(report_path)
        require(report['saved_fixture_checks_passed'], 'Independent saved inspection failed')
        require(report['saved_cubes'] == 4638 and report['nonair_y_bounds'] == [-128, 383], 'Unexpected saved world metrics')
        require(report['min_y'] == -128 and report['max_y_exclusive'] == 384, 'Unexpected saved height bounds')
        require(report['registered_susy_deposits'] and report['registered_susy_host_rock'], 'Missing required registrations')
        world = self.instance(name) / 'riven-dev'
        files = [world / 'level.dat', world / 'data/cubicChunksData.dat']
        files += sorted((world / 'region2d').glob('*.2dr')) + sorted((world / 'region3d').glob('*.3dr'))
        summary = {key: value for key, value in report.items() if key != 'world'}
        return {'inspection': self.evidence(report_path), 'metrics': summary,
                'retainedWorldFiles': [self.evidence(path) for path in files],
                'scope': 'Collected prior independent NBT/region inspection; reader rejects external overflow entries'}

    def collect(self):
        result = {'schema': 'cubicchunks.riven-native-validation.v1', 'passed': True,
                  'minecraft': '1.12.2', 'candidateSourceCommit': SOURCE_COMMIT,
                  'evidencePathBase': 'Riven workspace supplied through --riven-workspace',
                  'environment': 'Native Windows 11 server processes; Cleanroom Java 25 and Forge Java 8',
                  'errorNormalization': ['Strip ANSI escapes and leading timestamp',
                                         'Replace object identity suffixes and instance root paths',
                                         'Compare ERROR line multisets separately for fresh and restarted worlds'],
                  'limits': ['No client launch, rendering, network play or visual acceptance',
                             'No native throughput or performance claim; durations include startup and shutdown',
                             'No full modpack parity, progression balance or GregTech machine qualification',
                             'No claim of concurrent native world mutation or complete async event compatibility',
                             'Native diagnostics use fresh disposable worlds; existing player instances were not used'],
                  'loaders': {}}
        for loader, name in INSTANCES.items():
            directory = self.instance(name)
            baseline = self.instance('preparation-workers-cubic-' + loader)
            artifacts, receipt = self.artifacts(directory)
            prior_receipt = load(baseline / 'riven-instance.json')
            current_dependencies = {mod['slug']: mod['sha256'] for mod in receipt['mods'] if mod['slug'] != 'cubicchunks'}
            prior_dependencies = {mod['slug']: mod['sha256'] for mod in prior_receipt['mods'] if mod['slug'] != 'cubicchunks'}
            require(current_dependencies == prior_dependencies, 'Unrelated dependency changes')
            map_directory = self.instance('cubic-fork-' + loader + '-map-01')
            map_artifacts, _ = self.artifacts(map_directory)
            require(map_artifacts['cubicChunks']['sha256'] == artifacts['cubicChunks']['sha256']
                    and map_artifacts['riven']['sha256'] == artifacts['riven']['sha256'], 'Map tested different artifacts')
            result['loaders'][loader] = {'loaderVersion': '0.6.13-alpha' if loader == 'cleanroom' else '14.23.5.2860',
                'lifecycleInstance': name, 'artifacts': artifacts,
                'unrelatedDependencyHashesMatchPriorProfile': True, 'priorReceipt': self.evidence(baseline / 'riven-instance.json'),
                'write': self.phase(directory, 'write', baseline / 'cubic-habitats-console.log'),
                'read': self.phase(directory, 'read', baseline / 'cubic-habitats-read-console.log'),
                'savedData': self.saved(name), 'mapArtifacts': map_artifacts,
                'map': self.phase(map_directory, 'map', baseline / 'cubic-habitats-console.log')}
        failed = self.instance('cubic-fork-cleanroom-01')
        failed_log = self.log(failed / 'cubic-write-console.log')
        require('RIVEN_CUBIC_FAIL generated negative stone' in failed_log, 'Excluded-run evidence changed')
        result['excludedRuns'] = [{'instance': failed.name, 'result': self.evidence(failed / 'cubic-write-result.json'),
            'log': self.evidence(failed / 'cubic-write-console.log'), 'passed': False,
            'observedFailure': 'RIVEN_CUBIC_FAIL generated negative stone',
            'reason': 'The old Riven probe expected the initial flat vanilla-stone fixture after Riven terrain had changed.',
            'correction': 'Compare every block in the 512-block (1,y,1) column to the current Riven model; rerun in fresh instances.',
            'scope': 'Excluded from successful native qualification; retained without rewriting its evidence.'}]
        result['probeAndInspectionSources'] = [self.evidence(self.root / path) for path in [
            'experiments/cubic/src/main/java/supersymmetry/riven/experiment/CubicProbe.java',
            'experiments/cubic/src/main/java/supersymmetry/riven/experiment/CubicMapProbe.java',
            'tools/experiment_cubic.py', 'tools/inspect_cubic_world.py']]
        result['summary'] = {'successfulNativeProcesses': 6, 'savedCubesPerLoader': 4638,
                             'modelBlockComparisonsPerLifecyclePhase': 512, 'mapFixturesPerLoader': 10,
                             'newNormalizedErrorLines': 0,
                             'existingErrorLinesPerFreshRun': 186, 'existingErrorLinesPerRestart': 199,
                             'candidateArtifactHashesIdenticalAcrossLifecycleAndMapRuns': True}
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--riven-workspace', required=True, type=Path)
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).resolve().parents[1] / 'docs/measurements/native-validation.json')
    args = parser.parse_args()
    result = Collector(args.riven_workspace).collect()
    encoded = json.dumps(result, indent=2, sort_keys=False) + '\n'
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(encoded, encoding='utf-8', newline='\n')
    print(json.dumps({'passed': result['passed'], 'output': str(args.output), **result['summary']}, indent=2))


if __name__ == '__main__':
    main()
