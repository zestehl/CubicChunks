"""Prepare and probe isolated CubicChunks instances without changing the active profile."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import re
import shutil
import subprocess
import threading
import time
import zipfile

import dev

SPEC_PATH = dev.ROOT / 'dev/experiments/cubic-chunks.json'
PROBES = [(-128, 'diamond_block'), (-1, 'emerald_block'),
          (256, 'gold_block'), (383, 'lapis_block')]


def fetch():
    spec = json.loads(SPEC_PATH.read_text())
    path = dev.download(spec['url'], dev.LOCAL / 'downloads/mods' / spec['filename'], spec['sha256'])
    print(path)
    return path


def prepare(args):
    spec = json.loads(SPEC_PATH.read_text())
    local_artifact = getattr(args, 'cubic_jar', None)
    if local_artifact:
        source = Path(local_artifact).resolve(strict=True)
        checkout = Path(args.cubic_source_checkout).resolve(strict=True) if getattr(args, 'cubic_source_checkout', None) else None
        if checkout is None:
            raise RuntimeError('--cubic-source-checkout is required for a locally built CubicChunks artifact')
        with zipfile.ZipFile(source) as jar:
            names = set(jar.namelist())
            required = {'mcmod.info', 'cubicchunks.mixins.core.json',
                'io/github/opencubicchunks/cubicchunks/core/CubicChunks.class'}
            if not required <= names:
                raise RuntimeError('Local artifact is not a complete CubicChunks mod JAR')
            manifest = jar.read('META-INF/MANIFEST.MF').decode('utf-8').replace('\r\n ', '')
        commit = subprocess.check_output(['git', '-C', str(checkout), 'rev-parse', 'HEAD'], text=True).strip()
        status = subprocess.check_output(['git', '-C', str(checkout), 'status', '--porcelain'], text=True)
        spec = {'source': 'local-source-build', 'artifact': str(source),
            'source_checkout': str(checkout), 'source_commit': commit,
            'source_dirty': bool(status.strip()), 'source_status': status.splitlines(),
            'filename': source.name, 'sha256': dev.digest(source),
            'manifest': manifest, 'upstream_reference': spec}
    else:
        source = dev.download(spec['url'], dev.LOCAL / 'downloads/mods' / spec['filename'], spec['sha256'])
    artifacts = list((dev.ROOT / f'build/{args.loader}-cubic-experiment/libs').glob(f'riven-*-{args.loader}.jar'))
    if len(artifacts) != 1:
        raise RuntimeError('Build with -PrivenCubicExperiment=true first')
    args.profile = 'standalone' if args.scope == 'baseline' else 'worldgen'
    args.pack = str(dev.ROOT / 'research/Supersymmetry')
    dev.prepare(args)
    target = dev.instance(args.name)
    receipt = json.loads((target / 'riven-instance.json').read_text())
    receipt['base_profile'] = receipt['profile']
    receipt['profile'] = 'cubic-experiment'
    receipt['stage'] = 'height-feasibility'
    receipt['experiment_scope'] = args.scope
    receipt['experiment_generator'] = args.generator
    receipt['map_probe'] = args.map_probe
    receipt['experiment_spec_sha256'] = dev.digest(SPEC_PATH)
    receipt['mods'].append({'slug': 'cubicchunks',
        'reason': 'Experimental vertical storage and height backend; isolated from the active profile',
        'sha256': spec['sha256'], 'metadata': {'filename': spec['filename'], 'source': spec}})
    shutil.copy2(source, target / 'mods' / spec['filename'])
    shutil.copy2(artifacts[0], target / 'mods/riven.jar')
    receipt['riven'] = {'artifact': str(artifacts[0].relative_to(dev.ROOT)), 'sha256': dev.digest(artifacts[0])}
    config = target / 'config/cubicchunks.cfg'
    config.parent.mkdir(exist_ok=True)
    config.write_text('''general {
    I:defaultMinHeight=-128
    I:defaultMaxHeight=384
    S:forceLoadCubicChunks=NEW_WORLD
    S:excludedDimensions <
        -100000:-1
        1:100000
     >
    B:useVanillaChunkWorldGenerators=false
    I:spawnGenerateDistanceXZ=2
    I:spawnGenerateDistanceY=2
    I:spawnLoadDistanceXZ=2
    I:spawnLoadDistanceY=2
}
''', encoding='utf-8')
    receipt['experiment_config_initial_sha256'] = dev.digest(config)
    props = target / 'server.properties'
    prop_text = re.sub(r'level-type=.*', 'level-type=' + ('riven_cubic' if args.generator == 'riven-cubic' else 'DEFAULT'), props.read_text())
    props.write_text(prop_text.replace('view-distance=6', 'view-distance=3')
        .replace('server-port=25575', 'server-port=25585')
        .replace('server-port=25576', 'server-port=25586') + 'allow-nether=true\n', encoding='utf-8')
    if args.generator == 'riven-cubic':
        text = re.sub(r'^generator-settings=.*\n?', '', props.read_text(), flags=re.MULTILINE)
        props.write_text(text + 'generator-settings=' + json.dumps(dev.regional_settings(True), separators=(',', ':')) + '\n', encoding='utf-8')
    dev.write_json(target / 'riven-instance.json', receipt)
    dev.validate(args)
    dev.install(args)


def run(args):
    target = dev.instance(args.name)
    receipt = json.loads((target / 'riven-instance.json').read_text())
    if receipt['profile'] != 'cubic-experiment':
        raise RuntimeError('Only instances prepared by this experiment may be run')
    if 'installer' not in receipt:
        raise RuntimeError('Wait for successful instance installation before running the probe')
    dev.validate(args)
    if not (target / 'eula.txt').exists():
        raise RuntimeError('No previously accepted EULA was provided')
    phase = args.phase
    if (phase in ('write', 'map', 'regions', 'landscape', 'foundation', 'habitats')) == (target / 'riven-dev/level.dat').exists():
        raise RuntimeError('Write requires a fresh world; read requires the saved experimental world')
    prefix = f'cubic-{phase}' + (f'-{args.attempt}' if args.attempt else '')
    log_path = target / f'{prefix}-console.log'
    if log_path.exists():
        raise RuntimeError('Probe log already exists; preserve evidence and use a new instance')
    loader = receipt['loader']
    jar = f'cleanroom-{dev.CLEANROOM}.jar' if loader == 'cleanroom' else f'forge-1.12.2-{dev.FORGE}.jar'
    command = [dev.java(loader), '-Xms1G', '-Xmx6G', '-Djava.awt.headless=true',
               '-Driven.traceWorldgen=true', '-jar', jar, 'nogui']
    profile = getattr(args, 'profile_cubes', False)
    recording = target / f'{prefix}-profile.jfr'
    if profile:
        if phase not in ('write', 'read'):
            raise RuntimeError('--profile-cubes requires write or read')
        if recording.exists() or (target / f'cubic-profile-{phase}.json').exists():
            raise RuntimeError('Profile evidence exists; use a new instance')
        if loader == 'cleanroom':
            repository = target / 'jfr-repository'
            repository.mkdir(exist_ok=True)
            command[1:1] = [f'-XX:FlightRecorderOptions=repository={repository}',
                f'-XX:StartFlightRecording=filename={recording},settings=profile,dumponexit=true']
    if receipt.get('map_probe'):
        command.insert(4, '-Driven.cubicMapProbe=true')
    commands = ['riven_cubic_probe ' + phase]
    for y, block in PROBES:
        commands.append(f'say RIVEN_CUBIC_PROBE y={y}')
        if phase == 'write':
            commands.append(f'setblock 0 {y} 0 minecraft:{block}')
        commands.append(f'testforblock 0 {y} 0 minecraft:{block}')
    if phase == 'write':
        for y in [-129, 384]:
            commands.extend([f'say RIVEN_CUBIC_OUTSIDE y={y}', f'setblock 0 {y} 0 minecraft:diamond_block'])
    commands.extend(['save-all', 'say RIVEN_CUBIC_PROBE_COMPLETE', 'stop'])
    if phase == 'map':
        if not receipt.get('map_probe') or receipt.get('experiment_generator') != 'riven-cubic':
            raise RuntimeError('Map probe requires a fresh map fixture instance with the Riven cube generator')
        commands = ['riven_cubic_map_probe', 'save-all', 'stop']
    if phase in ('regions', 'regions-read'):
        commands = ['riven_regions verify', 'save-all', 'stop']
    if phase in ('landscape', 'landscape-read'):
        commands = ['riven_regions verify', 'riven_landscape verify', 'save-all', 'stop']
    if phase in ('foundation', 'foundation-read'):
        commands = ['riven_regions verify', 'riven_landscape verify', 'riven_foundation verify', 'save-all', 'stop']
    if phase in ('habitats', 'habitats-read'):
        commands = ['riven_regions verify', 'riven_landscape verify', 'riven_foundation verify', 'riven_habitats verify', 'save-all', 'stop']
    extra_probes = getattr(args, 'probe_command', [])
    if profile:
        extra_probes = list(extra_probes) + [f'riven_cubic_profile {phase} {loader}'
            + (' callbacks' if args.profile_callbacks else '')]
    save_index = commands.index('save-all')
    commands[save_index:save_index] = extra_probes
    started = time.monotonic()
    child = subprocess.Popen(command, cwd=target, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    dev.write_json(target / f'{prefix}-process.json', {'pid': child.pid, 'command': command})
    lines = queue.Queue()

    def read_output():
        for line in child.stdout:
            lines.put(line)
        lines.put(None)

    threading.Thread(target=read_output, daemon=True).start()
    ready = False
    probe_at = None
    commands_sent = False
    timed_out = False
    transcript = []
    try:
        with log_path.open('w', encoding='utf-8') as log:
            while True:
                if probe_at is not None and not commands_sent and time.monotonic() >= probe_at:
                    child.stdin.write('\n'.join(commands) + '\n')
                    child.stdin.flush()
                    commands_sent = True
                if time.monotonic() - started > args.timeout:
                    timed_out = True
                    child.terminate()
                    break
                try:
                    line = lines.get(timeout=1)
                except queue.Empty:
                    continue
                if line is None:
                    break
                log.write(line)
                log.flush()
                transcript.append(line)
                if 'Done (' in line and not ready:
                    ready = True
                    probe_at = time.monotonic() + args.settle
    finally:
        try:
            code = child.wait(timeout=30)
        except subprocess.TimeoutExpired:
            child.kill()
            code = child.wait()
    content = ''.join(transcript)
    checks = {str(y): f'RIVEN_CUBIC_BLOCK y={y} PASS' in content for y, _ in PROBES}
    probe_passed = f'RIVEN_CUBIC_RESULT phase={phase} PASS' in content
    generation_passed = ('RIVEN_CUBIC_GENERATION PASS' in content) if receipt.get('experiment_generator') == 'riven-cubic' else None
    shutdown_exception = 'Exception stopping the server' in content
    missing_map_mixin = "specified mixin 'io.github.opencubicchunks.cubicchunks.core.asm.mixin.fixes.common.MixinItemMap' was not found" in content
    if phase == 'map':
        checks = {}
        generation_passed = None
        probe_passed = 'RIVEN_CUBIC_MAP_RESULT held-map-height PASS' in content
    if phase in ('regions', 'regions-read'):
        checks = {}
        generation_passed = None
        probe_passed = 'RIVEN_REGIONS_RESULT signature=' in content
    if phase in ('landscape', 'landscape-read'):
        checks = {}
        generation_passed = None
        probe_passed = 'RIVEN_REGIONS_RESULT signature=' in content and 'RIVEN_LANDSCAPE_RESULT signature=' in content
    if phase in ('foundation', 'foundation-read'):
        checks = {}; generation_passed = None
        probe_passed = all(marker in content for marker in ['RIVEN_REGIONS_RESULT signature=', 'RIVEN_LANDSCAPE_RESULT signature=', 'RIVEN_FOUNDATION_RESULT signature=', 'RIVEN_PHYSIOGRAPHY_RESULT version=1 signature='])
    if phase in ('habitats', 'habitats-read'):
        checks = {}; generation_passed = None
        probe_passed = all(marker in content for marker in ['RIVEN_REGIONS_RESULT signature=', 'RIVEN_LANDSCAPE_RESULT signature=', 'RIVEN_FOUNDATION_RESULT signature=', 'RIVEN_PHYSIOGRAPHY_RESULT version=1 signature=', 'RIVEN_HABITATS_RESULT version=1 signature='])
        marker = re.search(r'RIVEN_HABITATS_READY version=1 envelopes=\d+ fingerprint=[a-f0-9]{64} sampledProfiles=0 terrainColumns=0', content)
        probe_passed = probe_passed and bool(marker) and marker.start() < content.index('RIVEN_WORLDGEN stage=chunk-generator dimension=0')
    result = {'loader': loader, 'scope': receipt['experiment_scope'], 'phase': phase,
        'ready': ready, 'exit_code': code, 'timed_out': timed_out,
        'block_checks': checks, 'seconds': round(time.monotonic() - started, 2),
        'api_probe_passed': probe_passed,
        'riven_generation_probe_passed': generation_passed,
        'settle_seconds': args.settle, 'shutdown_exception': shutdown_exception,
        'missing_map_mixin': missing_map_mixin,
        'config_sha256': dev.digest(target / 'config/cubicchunks.cfg'),
        'server_properties_sha256': dev.digest(target / 'server.properties'),
        'log': str(log_path), 'commands': commands,
        'passed': ready and code == 0 and not timed_out and all(checks.values()) and probe_passed
            and generation_passed is not False and not shutdown_exception}
    if profile:
        profile_path = target / f'cubic-profile-{phase}.json'
        data = json.loads(profile_path.read_text()) if profile_path.exists() else {}
        result['cube_profile'] = {'path': str(profile_path), 'passed': data.get('passed') is True,
            'jfr': str(recording) if loader == 'cleanroom' else None}
        result['passed'] = result['passed'] and data.get('passed') is True \
            and f'RIVEN_CUBIC_PROFILE_RESULT mode={phase} PASS' in content \
            and (loader != 'cleanroom' or (recording.exists() and recording.stat().st_size > 0))
    dev.write_json(target / f'{prefix}-result.json', result)
    print(json.dumps(result, indent=2))
    return 0 if result['passed'] else 1


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['fetch', 'prepare', 'run'])
    parser.add_argument('--name')
    parser.add_argument('--loader', choices=['cleanroom', 'forge'], default='cleanroom')
    parser.add_argument('--scope', choices=['baseline', 'kernel'], default='baseline')
    parser.add_argument('--generator', choices=['compatibility', 'riven-cubic'], default='compatibility')
    parser.add_argument('--phase', choices=['write', 'read', 'map', 'regions', 'regions-read', 'landscape', 'landscape-read', 'foundation', 'foundation-read', 'habitats', 'habitats-read'], default='write')
    parser.add_argument('--map-probe', action='store_true')
    parser.add_argument('--cubic-jar', type=Path, help='Use a locally built fork only in this fresh experiment instance')
    parser.add_argument('--cubic-source-checkout', type=Path, help='Source checkout recorded with the local CubicChunks artifact')
    parser.add_argument('--timeout', type=int, default=240)
    parser.add_argument('--attempt', type=int, default=0)
    parser.add_argument('--settle', type=float, default=5.0)
    parser.add_argument('--probe-command', action='append', default=[], help='Additional diagnostic server command before saving and stopping')
    parser.add_argument('--profile-cubes', action='store_true', help='Measure isolated cube workloads; capture JFR on Cleanroom')
    parser.add_argument('--profile-callbacks', action='store_true', help='Assert cached population/lighting async callbacks in profile')
    args = parser.parse_args()
    if args.command == 'fetch':
        fetch()
    else:
        if not args.name:
            parser.error('--name is required for prepare and run')
        raise SystemExit(prepare(args) if args.command == 'prepare' else run(args))
