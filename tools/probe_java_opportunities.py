#!/usr/bin/env python3
"""Observe collection/NBT contracts in the existing named builds on Java 8 and 25.

This starts ordinary JVMs, not Minecraft. Build both main artifacts first. Output is
diagnostic evidence, not a regression suite or an in-game compatibility/performance test.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

FORK = Path(__file__).resolve().parents[1]
CLASSES = [
    'core/util/world/CubeSplitTickSet', 'core/util/world/CubeSplitTickList',
    'core/lighting/phosphor/PooledLightUpdateQueue', 'core/world/ServerHeightMap',
]


def fingerprint(path):
    with path.open('rb') as stream:
        return {'path': str(path), 'sha256': hashlib.file_digest(stream, 'sha256').hexdigest()}


def single(paths, description):
    paths = list(paths)
    if len(paths) != 1: raise RuntimeError(f'Expected one {description}, found {len(paths)}')
    return paths[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--riven-workspace', type=Path, default=FORK.parents[1])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(); output = args.output.resolve(); output.mkdir(parents=True, exist_ok=False)
    settings = json.loads((args.riven_workspace / '.local/settings.json').read_text(encoding='utf-8'))
    cache = Path.home() / '.gradle/caches'
    libraries = [single((cache / 'modules-2/files-2.1' / group / version).rglob('*.jar'), group) for group, version in [
        ('com.google.guava/guava', '21.0'), ('org.apache.logging.log4j/log4j-api', '2.15.0'),
        ('org.apache.logging.log4j/log4j-core', '2.15.0')]]
    minecraft = cache / 'unimined/net/minecraft/minecraft/1.12.2'
    properties = (FORK / 'cleanroom/gradle.properties').read_text(encoding='utf-8')
    forge_version = re.search(r'^forge_version=(.*)$', properties, re.M)[1].strip()
    cleanroom_version = re.search(r'^cleanroom_version=(.*)$', properties, re.M)[1].strip()
    variants = [('forge-java8', 'forge', 'java8', 'MinecraftForge-FG3/1.12.2-' + forge_version),
                ('cleanroom-java25', 'cleanroom', 'java25', 'Cleanroom-FG3/' + cleanroom_version)]
    named = {loader: single((minecraft / location).rglob('*fixForge+asmFixes-mcp-at.jar'), loader + ' named Minecraft JAR')
             for label, loader, java, location in variants}
    source = FORK / 'tools/diagnostics/JavaOpportunityProbe.java'
    classes = output / 'probe-classes'; classes.mkdir()
    forge_classes = FORK / 'cleanroom/build/forge/classes/java/main'
    compile_classpath = os.pathsep.join(map(str, [forge_classes, named['forge'], *libraries]))
    javac = str(Path(settings['java25']).with_name('javac.exe' if os.name == 'nt' else 'javac'))
    compile_command = [javac, '--release', '8', '-encoding', 'UTF-8', '-cp', compile_classpath, '-d', str(classes), str(source)]
    subprocess.run(compile_command, check=True)
    report = {'scope': 'Isolated existing named-class contracts; no game/coremod/world or speedup qualification',
              'capturedUtc': datetime.now(timezone.utc).isoformat(),
              'sourceCommit': subprocess.check_output(['git', '-C', str(FORK), 'rev-parse', 'HEAD'], text=True).strip(),
              'sourceStatus': subprocess.check_output(['git', '-C', str(FORK), 'status', '--porcelain'], text=True).splitlines(),
              'probe': fingerprint(source), 'compileCommand': compile_command, 'libraries': [fingerprint(p) for p in libraries], 'runs': []}
    for label, loader, java, location in variants:
        production = FORK / 'cleanroom/build' / loader / 'classes/java/main'
        classpath = os.pathsep.join(map(str, [classes, production, named[loader], *libraries]))
        command = [settings[java], '-cp', classpath, 'JavaOpportunityProbe']
        completed = subprocess.run(command, text=True, capture_output=True, timeout=30)
        (output / (label + '.log')).write_text(completed.stdout + completed.stderr, encoding='utf-8')
        if completed.returncode: raise RuntimeError('Probe failed to run; inspect ' + label + '.log')
        observations = {line.split('=', 1)[0]: line.split('=', 1)[1] for line in completed.stdout.splitlines() if '=' in line}
        hashes = []
        for name in CLASSES:
            base = production / ('io/github/opencubicchunks/cubicchunks/' + name)
            hashes.extend(fingerprint(path) for path in sorted(base.parent.glob(base.name + '*.class')))
        hashes.append(fingerprint(production / 'io/github/opencubicchunks/cubicchunks/api/world/storage/ICubicStorage.class'))
        report['runs'].append({'label': label, 'command': command, 'minecraft': fingerprint(named[loader]),
                               'compiledClasses': hashes, 'observations': observations})
        print(label + ': ' + json.dumps(observations), flush=True)
    (output / 'observations.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__': main()
