#!/usr/bin/env python3
"""Prepare and run isolated native Cleanroom clients/servers for the optional cube lab. Python 3.11+."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import importlib
import json
import os
from pathlib import Path
import platform
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
import zipfile

FORK = Path(__file__).resolve().parents[1]
PLAYER = 'CubicLab'


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + '\n', encoding='utf-8')


def sha(path, algorithm='sha256'):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, algorithm).hexdigest()


def fetch(url, target, expected, algorithm='sha1', candidates=()):
    if target.is_file() and sha(target, algorithm) == expected:
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    for candidate in candidates:
        if candidate.is_file() and sha(candidate, algorithm) == expected:
            temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.partial')
            shutil.copy2(candidate, temporary)
            temporary.replace(target)
            return target
    request = urllib.request.Request(url, headers={'User-Agent': 'CubicChunks-development-lab'})
    with urllib.request.urlopen(request, timeout=90) as response:
        data = response.read()
    if hashlib.new(algorithm, data).hexdigest() != expected:
        raise RuntimeError('Checksum mismatch: ' + url)
    temporary = target.with_name(target.name + '.' + uuid.uuid4().hex + '.partial')
    temporary.write_bytes(data)
    temporary.replace(target)
    return target


def latest():
    request = urllib.request.Request('https://api.github.com/repos/CleanroomMC/Cleanroom/releases/latest',
                                     headers={'User-Agent': 'CubicChunks-development-lab'})
    with urllib.request.urlopen(request, timeout=30) as response:
        release = json.load(response)
    return {key: release[key] for key in ['tag_name', 'published_at', 'html_url', 'assets']}


def reviewed_release(tag):
    request = urllib.request.Request('https://api.github.com/repos/CleanroomMC/Cleanroom/releases/tags/' + tag,
                                     headers={'User-Agent': 'CubicChunks-development-lab'})
    with urllib.request.urlopen(request, timeout=30) as response: release = json.load(response)
    return {key: release[key] for key in ['tag_name', 'published_at', 'html_url', 'assets']}


def settings(root):
    sys.path.insert(0, str(root / 'tools'))
    return importlib.import_module('dev'), importlib.import_module('experiment_cubic')


def library_allowed(library, system, architecture):
    allowed = not library.get('rules')
    for rule in library.get('rules', []):
        match = True
        spec = rule.get('os', {})
        if 'name' in spec:
            match = spec['name'] in (system, system + '-arm64' if architecture == 'aarch64' else system)
        if 'arch' in spec:
            match &= bool(re.search(spec['arch'], architecture))
        if 'version' in spec:
            match &= bool(re.search(spec['version'], platform.release()))
        if match:
            allowed = rule['action'] == 'allow'
    # MMC metadata can declare several native architectures under the same OS rule.
    classifier = library['name'].split(':')[3:]
    if classifier and classifier[0].startswith('natives-'):
        name = classifier[0]
        if architecture == 'x86_64' and (name.endswith('-x86') or '-arm' in name):
            return False
        if architecture == 'aarch64' and not name.endswith('-arm64'):
            return False
    return allowed


def merged_libraries(components, system, architecture):
    selected, priority = {}, {}
    for component_index, component in enumerate(components):
        for library in component.get('libraries', []):
            if not library_allowed(library, system, architecture): continue
            parts = library['name'].split(':'); key = (parts[0], parts[1], ':'.join(parts[3:]))
            prior = selected.get(key)
            if prior and prior['name'] == library['name']:
                library = dict(prior, **library)
                library['downloads'] = dict(prior.get('downloads', {}), **library.get('downloads', {}))
            selected[key] = library; priority[key] = component_index
    return [selected[key] for key in sorted(selected, key=lambda key: priority[key], reverse=True)]


def prepare_client(server, target, base_zip, root, java, release):
    target.mkdir(parents=True, exist_ok=False)
    for folder in ['mods', 'config']:
        shutil.copytree(server / folder, target / folder)
    with zipfile.ZipFile(base_zip) as archive:
        components = [json.loads(archive.read(name)) for name in archive.namelist()
                      if name.startswith('patches/') and name.endswith('.json')]
        embedded = {Path(name).name: archive.read(name) for name in archive.namelist() if name.startswith('libraries/') and name.endswith('.jar')}
    if not any(component.get('uid') == 'net.minecraft' for component in components):
        with urllib.request.urlopen('https://meta.prismlauncher.org/v1/net.minecraft/1.12.2.json', timeout=30) as response:
            components.insert(0, json.load(response))
    write_json(target / 'resolved-components.json', components)
    system = {'Windows': 'windows', 'Linux': 'linux', 'Darwin': 'osx'}[platform.system()]
    architecture = 'aarch64' if platform.machine().lower() in ('arm64', 'aarch64') else 'x86_64'
    cache = root / '.local/cubic-lab/cache'
    home = Path.home()
    caches = [root / '.local/instances/kernel/libraries', server / 'libraries',
              home / '.gradle/caches/modules-2/files-2.1',
              home / 'AppData/Roaming/PrismLauncher/libraries']
    by_name = {}
    for directory in caches:
        if directory.exists():
            for path in directory.rglob('*.jar'):
                by_name.setdefault(path.name, []).append(path)
    artifacts = {}
    for library in merged_libraries(components, system, architecture):
        name = library['name']; downloads = library.get('downloads', {})
        if library.get('MMC-hint') == 'local':
            parts = name.split(':'); filename = parts[1] + '-' + parts[2] + '.jar'
            body = embedded[filename]
            relative = parts[0].replace('.', '/') + '/' + parts[1] + '/' + parts[2] + '/' + filename
            path = cache / 'libraries' / relative; path.parent.mkdir(parents=True, exist_ok=True); path.write_bytes(body)
            artifacts[(name, hashlib.sha1(body).hexdigest())] = (name, {'url': path.as_uri(), 'sha1': hashlib.sha1(body).hexdigest(), 'path': relative})
            continue
        if 'artifact' in downloads:
            artifacts[(name, downloads['artifact']['sha1'])] = (name, downloads['artifact'])
        native_key = system + '-arm64' if architecture == 'aarch64' else system
        classifier = library.get('natives', {}).get(native_key)
        if classifier:
            classifier = classifier.replace('${arch}', '64')
            artifact = downloads['classifiers'][classifier]
            artifacts[(name + ':' + classifier, artifact['sha1'])] = (name + ':' + classifier, artifact)
    def library_job(item):
        name, artifact = item
        parts = name.split(':')
        relative = artifact.get('path') or '/'.join([parts[0].replace('.', '/'), parts[1], parts[2], artifact['url'].rsplit('/', 1)[-1]])
        path = fetch(artifact['url'], cache / 'libraries' / relative, artifact['sha1'],
                     candidates=by_name.get(Path(relative).name, []))
        return {'name': name, 'path': str(path), 'sha1': artifact['sha1']}
    with ThreadPoolExecutor(max_workers=8) as pool:
        libraries = list(pool.map(library_job, artifacts.values()))
    minecraft = next(c for c in components if c.get('uid') == 'net.minecraft')
    main_jar = minecraft['mainJar']['downloads']['artifact']
    jar = fetch(main_jar['url'], cache / 'minecraft-client-1.12.2.jar', main_jar['sha1'], candidates=[
        home / '.gradle/caches/unimined/net/minecraft/minecraft/1.12.2/minecraft-1.12.2-client.jar'])
    assets = cache / 'assets'
    asset_roots = [home / '.gradle/caches/unimined/assets', home / 'AppData/Roaming/PrismLauncher/assets']
    index = minecraft['assetIndex']
    index_path = fetch(index['url'], assets / 'indexes' / (index['id'] + '.json'), index['sha1'],
                       candidates=[p / 'indexes' / (index['id'] + '.json') for p in asset_roots])
    objects = json.loads(index_path.read_text())['objects']
    def asset_job(entry):
        digest = entry['hash']; relative = digest[:2] + '/' + digest
        return fetch('https://resources.download.minecraft.net/' + relative, assets / 'objects' / relative, digest,
                     candidates=[p / 'objects' / relative for p in asset_roots])
    with ThreadPoolExecutor(max_workers=12) as pool:
        list(pool.map(asset_job, {entry['hash']: entry for entry in objects.values()}.values()))
    natives = target / 'natives'; natives.mkdir()
    for library in libraries:
        if ':natives-' in library['name']:
            with zipfile.ZipFile(library['path']) as archive:
                for member in archive.namelist():
                    if member.lower().endswith(('.dll', '.so', '.dylib')):
                        (natives / Path(member).name).write_bytes(archive.read(member))
    (target / 'options.txt').write_text('renderDistance:3\nmaxFps:120\nenableVsync:false\nfancyGraphics:false\n'
        'renderClouds:false\nfullscreen:false\npauseOnLostFocus:false\nshowSubtitles:false\n', encoding='utf-8')
    result = {'schema': 1, 'java': java, 'release': release['tag_name'], 'libraries': libraries,
              'minecraft': str(jar), 'minecraft_sha1': main_jar['sha1'], 'assets': str(assets), 'assetIndex': index['id'],
              'natives': str(natives), 'system': system, 'architecture': architecture,
              'assetObjects': len(objects), 'mainClass': 'top.outlands.foundation.boot.Foundation',
              'authMode': 'offline local diagnostic; no account credentials used'}
    write_json(target / 'client-runtime.json', result)
    return result


def prepare(args):
    root = args.riven_workspace; dev, experiment = settings(root)
    client_profile = read_client_profile(args.client_profile)
    runtime_config = (FORK / 'lab/runtime.properties').read_text()
    pinned_tag = re.search(r'^release_tag=(.*)$', runtime_config, re.M)[1].strip()
    product_version = re.search(r'^runtime_version=(.*)$', runtime_config, re.M)[1].strip()
    if args.runtime_release:
        if args.runtime_release != '0.6.13-alpha': raise RuntimeError('Only the reviewed 0.6.13-alpha compatibility runtime override is supported')
        release = reviewed_release(args.runtime_release); product_version = args.runtime_release
        runtime_selection = 'Explicit supported-loader compatibility check; default latest-runtime profile is retained'
    else:
        release = latest()
        if release['tag_name'] != pinned_tag:
            raise RuntimeError(f'Latest release is {release["tag_name"]}; review and update lab/runtime.properties before preparing')
        runtime_selection = 'Reviewed latest release'
    version = release['tag_name']
    installer_asset = next(a for a in release['assets'] if a['name'].endswith('-installer.jar'))
    fetch(installer_asset['browser_download_url'], root / '.local/downloads' / installer_asset['name'], installer_asset['digest'].split(':')[1], 'sha256')
    # Only this lab process uses the selected release; the active Riven profile stays pinned.
    dev.CLEANROOM = product_version
    dev.ASSETS[installer_asset['name']] = installer_asset['digest'].split(':')[1]
    if tuple(int(x) for x in product_version.split('.')[:2]) >= (0, 7):
        def install_current(preparation):
            server = dev.instance(preparation.name)
            installer = root / '.local/downloads' / installer_asset['name']
            command = [dev.java('cleanroom'), '-jar', str(installer), 'server', '--dir', str(server),
                '--version', product_version, '--no-gui', '--yes', '--no-provision-java', '--java', dev.java('cleanroom'), '--memory', '6G']
            with (server / 'installer.log').open('w', encoding='utf-8') as output:
                subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, check=True)
            receipt_path = server / 'riven-instance.json'; receipt = json.loads(receipt_path.read_text())
            receipt['installer'] = {'file': installer.name, 'sha256': sha(installer), 'command': command}
            dev.write_json(receipt_path, receipt)
        dev.install = install_current
    base_name = 'cubic-lab-' + args.name
    target = root / '.local/cubic-lab' / args.name
    if target.exists() or dev.instance(base_name).exists():
        raise RuntimeError('Lab name already exists; preserve worlds/results and choose a new name')
    cubic = args.cubic_jar or next((FORK / 'cleanroom/build/cleanroom/libs').glob('*-cleanroom.jar'))
    lab = FORK / 'lab/build/cleanroom/libs/cubicchunks-lab-0.1.0-cleanroom.jar'
    if not lab.exists(): raise RuntimeError('Build the optional lab mod first')
    preparation = argparse.Namespace(name=base_name, loader='cleanroom', scope='kernel', generator='riven-cubic',
        map_probe=False, cubic_jar=cubic, cubic_source_checkout=FORK, profile='worldgen', pack=str(root / 'research/Supersymmetry'))
    experiment.prepare(preparation)
    server = dev.instance(base_name)
    shutil.copy2(lab, server / 'mods' / lab.name)
    receipt_path = server / 'riven-instance.json'; receipt = json.loads(receipt_path.read_text())
    receipt['mods'].append({'slug': 'cubiclab', 'reason': 'Optional in-game loading/storage performance instrumentation',
        'sha256': sha(lab), 'metadata': {'filename': lab.name}})
    dev.write_json(receipt_path, receipt)
    props = server / 'server.properties'
    text = props.read_text()
    overrides = {'server-ip': '127.0.0.1', 'server-port': str(args.port), 'online-mode': 'false',
        'gamemode': '3', 'difficulty': '0', 'spawn-monsters': 'false', 'spawn-animals': 'false', 'max-players': '4',
        'allow-flight': 'true', 'enable-rcon': 'false', 'view-distance': '3'}
    for key, value in overrides.items():
        text = re.sub(r'^' + re.escape(key) + r'=.*\n?', '', text, flags=re.M)
        text += key + '=' + value + '\n'
    props.write_text(text, encoding='utf-8')
    player_uuid = str(uuid.UUID(bytes=hashlib.md5(('OfflinePlayer:' + PLAYER).encode()).digest(), version=3))
    write_json(server / 'ops.json', [{'uuid': player_uuid, 'name': PLAYER, 'level': 2, 'bypassesPlayerLimit': False}])
    target.mkdir(parents=True)
    zip_asset = next(a for a in release['assets'] if a['name'].endswith('.zip'))
    base_zip = fetch(zip_asset['browser_download_url'], root / '.local/downloads' / zip_asset['name'],
                     zip_asset['digest'].split(':')[1], 'sha256')
    runtime = prepare_client(server, target / 'client', base_zip, root, dev.java('cleanroom'), release)
    for addon in client_profile['mods']:
        source = fetch(addon['url'], root / '.local/downloads/mods' / addon['filename'], addon['sha256'], 'sha256',
                       candidates=[root / '.local/cubic-lab/renderer-research' / addon['filename']])
        shutil.copy2(source, target / 'client/mods' / addon['filename'])
    export = target / 'CubicChunks-Lab-Prism.zip'
    manifest = {'schema': 1, 'name': args.name, 'server': str(server), 'client': str(target / 'client'),
        'port': args.port, 'release': release, 'runtimeVersion': product_version, 'releaseCheckedUtc': datetime.now(timezone.utc).isoformat(),
        'runtimeSelection': runtime_selection,
        'java': dev.java('cleanroom'), 'cubicJar': {'filename': cubic.name, 'sha256': sha(cubic)},
        'labJar': {'filename': lab.name, 'sha256': sha(lab)}, 'riven': receipt['riven'],
        'modHashes': {path.name: sha(path) for path in sorted((server / 'mods').glob('*.jar'))},
        'clientModHashes': {path.name: sha(path) for path in sorted((target / 'client/mods').glob('*.jar'))},
        'clientProfile': client_profile,
        'generatedLibraryHashes': {'server': {}, 'client': {}},
        'height': {'minY': -128, 'maxYExclusive': 384, 'verticalCubesPerColumn': 32},
        'compatibility': (['Lab-only field-access ABI bridge forwards Fugue 0.24.4 calls to ImagineBreaker 3.2, preserving target class initialization.',
            'Lab-only independently authored BlockStateContainer.Builder restores the missing Forge fluid API class through the loader transformer API; existing runtime classes are preserved.',
            'Lab-only ObjectHolderRef mixin initializes the declaring class before registry field injection, preventing later static initializers from clearing injected values.'] if product_version == '0.7.0' else []),
        'clientRuntime': runtime, 'prismImport': str(export)}
    package_client(target, manifest, base_zip)
    write_json(target / 'lab.json', manifest)
    print(json.dumps({'lab': str(target), 'prismImport': str(export), 'release': version,
        'libraries': len(runtime['libraries']), 'assetObjects': runtime['assetObjects']}, indent=2))


def read_client_profile(name):
    path = FORK / 'lab/profiles/client-renderers.json'
    data = json.loads(path.read_text(encoding='utf-8'))
    if name not in data['profiles']: raise RuntimeError('Unknown client profile: ' + name)
    selected = data['profiles'][name]
    mods = [dict(data['mods'][slug], slug=slug, side='client') for slug in selected]
    for mod in mods:
        if any(dependency not in selected for dependency in mod.get('requires', [])):
            raise RuntimeError('Client profile is missing a dependency for ' + mod['slug'])
    return {'name': name, 'definitionSha256': sha(path), 'mods': mods,
            'ownership': 'External unmodified runtime compatibility inputs; no source or responsibilities embedded into CubicChunks'}


def expected_mod_hashes(manifest, side):
    return manifest.get('clientModHashes', manifest['modHashes']) if side == 'client' else manifest['modHashes']


def package_client(target, manifest, base_zip):
    """Export owned client inputs, excluding worlds, caches, accounts and measurement outputs."""
    export = Path(manifest['prismImport'])
    if export.exists():
        retained = export.with_name('CubicChunks-Lab-Prism-unprimed.zip')
        if not retained.exists(): export.rename(retained)
    temporary = export.with_suffix('.partial')
    client = Path(manifest['client'])
    with zipfile.ZipFile(base_zip) as base, zipfile.ZipFile(temporary, 'w', zipfile.ZIP_DEFLATED) as output:
        for name in base.namelist():
            if not name.endswith('/') and name != 'instance.cfg': output.writestr(name, base.read(name))
        output.writestr('instance.cfg', 'InstanceType=OneSix\nname=CubicChunks Lab ' + manifest['name']
            + '\nOverrideJava=true\nJavaPath=' + manifest['java'].replace('\\', '/')
            + '\nOverrideMemory=true\nMinMemAlloc=1024\nMaxMemAlloc=6144\nOverrideJavaArgs=true\nJvmArgs='
            + ('-Dcubiclab.cleanroom070=true' if manifest.get('runtimeVersion') == '0.7.0' else '') + '\n')
        for folder in ['mods', 'config', 'groovy', 'local', 'resources', 'resourcepacks']:
            for path in sorted((client / folder).rglob('*')):
                if path.is_file(): output.write(path, 'minecraft/' + path.relative_to(client).as_posix())
        output.write(client / 'options.txt', 'minecraft/options.txt')
    temporary.replace(export)
    manifest['prismImportSha256'] = sha(export)
    manifest['prismImportPrimed'] = bool(manifest.get('primed'))


def record_inputs(manifest):
    inputs = {}
    for side in ['server', 'client']:
        directory = Path(manifest[side]); paths = []
        for folder in ['config', 'groovy', 'local', 'resources', 'resourcepacks']:
            paths.extend(path for path in (directory / folder).rglob('*') if path.is_file())
        paths.extend(path for path in [directory / 'options.txt', directory / 'server.properties'] if path.is_file())
        inputs[side] = {path.relative_to(directory).as_posix(): sha(path) for path in sorted(paths)}
    return inputs


def record_generated_libraries(manifest):
    """Accept startup-extracted libraries only when their bytes match a retained mod's embedded JAR."""
    result = {}
    for side in ['server', 'client']:
        directory = Path(manifest[side]) / 'mods'
        nested = [path for path in directory.rglob('*.jar') if path.parent != directory]
        owners = {}
        wanted = {path.name for path in nested}
        for owner in sorted(directory.glob('*.jar')):
            with zipfile.ZipFile(owner) as archive:
                for entry in archive.namelist():
                    if Path(entry).name in wanted:
                        digest = hashlib.sha256(archive.read(entry)).hexdigest()
                        owners.setdefault((Path(entry).name, digest), []).append({'mod': owner.name, 'embeddedEntry': entry})
        records = {}
        for path in sorted(nested):
            digest = sha(path); source = owners.get((path.name, digest))
            if not source: raise RuntimeError('Unowned nested mod/library JAR; create and review a new lab: ' + str(path))
            records[path.relative_to(directory).as_posix()] = {'sha256': digest, 'owners': source,
                'reason': 'Required library extracted unchanged by a retained startup integration'}
        result[side] = records
    return result


def export_client(args):
    target, manifest = load_lab(args)
    asset = next(a for a in manifest['release']['assets'] if a['name'].endswith('.zip'))
    base_zip = fetch(asset['browser_download_url'], args.riven_workspace / '.local/downloads' / asset['name'],
                     asset['digest'].split(':')[1], 'sha256')
    manifest['generatedInputHashes'] = record_inputs(manifest)
    manifest['generatedLibraryHashes'] = record_generated_libraries(manifest)
    manifest['generatedInputsRecordedUtc'] = datetime.now(timezone.utc).isoformat()
    holder_note = 'Lab-only ObjectHolderRef mixin initializes the declaring class before registry field injection, preventing later static initializers from clearing injected values.'
    if manifest.get('runtimeVersion') == '0.7.0' and holder_note not in manifest.get('compatibility', []):
        manifest.setdefault('compatibility', []).append(holder_note)
    package_client(target, manifest, base_zip)
    write_json(target / 'lab.json', manifest)
    print(manifest['prismImport'])


def load_lab(args):
    target = args.riven_workspace / '.local/cubic-lab' / args.name
    manifest = json.loads((target / 'lab.json').read_text())
    if 'modHashes' in manifest:
        for side in ['server', 'client']:
            actual = {path.name: sha(path) for path in Path(manifest[side]).joinpath('mods').glob('*.jar')}
            if actual != expected_mod_hashes(manifest, side): raise RuntimeError('Prepared ' + side + ' mod set changed; create a new lab revision before benchmarking')
    if 'generatedLibraryHashes' in manifest and record_generated_libraries(manifest) != manifest['generatedLibraryHashes']:
        raise RuntimeError('Generated mod library set changed; create a new lab revision before benchmarking')
    return target, manifest


def argv(manifest, client, recording=None):
    directory = Path(manifest['client'] if client else manifest['server'])
    temporary = directory / 'java-tmp'; temporary.mkdir(exist_ok=True)
    result = [manifest['java'], '-Xms1G', '-Xmx6G', '-Djava.io.tmpdir=' + str(temporary), '-Dfile.encoding=UTF-8']
    if tuple(int(x) for x in manifest.get('runtimeVersion', '0.6.13').split('.')[:2]) >= (0, 7):
        result.append('-Dcubiclab.cleanroom070=true')
    if recording:
        repository = directory / 'jfr-repository'; repository.mkdir(exist_ok=True)
        result += ['-XX:FlightRecorderOptions=repository=' + str(repository),
                   '-XX:StartFlightRecording=filename=' + str(recording) + ',settings=profile,dumponexit=true']
    if not client:
        product_version = manifest.get('runtimeVersion', manifest['release']['tag_name'])
        modern_args = directory / 'libraries/com/cleanroommc/cleanroom' / product_version / ('win_args.txt' if os.name == 'nt' else 'unix_args.txt')
        if modern_args.exists():
            return result + ['-Djava.awt.headless=true', '@user_jvm_args.txt', '@' + str(modern_args), 'nogui']
        return result + ['-Djava.awt.headless=true', '-jar', 'cleanroom-' + manifest.get('runtimeVersion', manifest['release']['tag_name']) + '.jar', 'nogui']
    runtime = manifest['clientRuntime']
    classpath = os.pathsep.join([runtime['minecraft']] + [library['path'] for library in runtime['libraries']])
    player_uuid = str(uuid.UUID(bytes=hashlib.md5(('OfflinePlayer:' + PLAYER).encode()).digest(), version=3))
    return result + ['--enable-native-access=ALL-UNNAMED', '-Djava.library.path=' + runtime['natives'], '-cp', classpath,
        runtime['mainClass'], '--tweakClass', 'net.minecraftforge.fml.common.launcher.FMLTweaker',
        '--username', PLAYER, '--uuid', player_uuid, '--accessToken', '0', '--userType', 'legacy', '--versionType', 'custom',
        '--version', 'Cleanroom-' + manifest['release']['tag_name'], '--gameDir', str(directory),
        '--assetsDir', runtime['assets'], '--assetIndex', runtime['assetIndex'], '--width', '1280', '--height', '720',
        '--server', '127.0.0.1', '--port', str(manifest['port'])]


def spawn(command, directory, log, messages):
    process = subprocess.Popen(command, cwd=directory, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
    def reader():
        with log.open('w', encoding='utf-8') as stream:
            for line in process.stdout:
                stream.write(line); stream.flush(); messages.put(line)
        messages.put(None)
    threading.Thread(target=reader, daemon=True).start()
    return process


def await_line(messages, needle, processes, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try: line = messages.get(timeout=.5)
        except queue.Empty:
            if any(p.poll() is not None for p in processes): raise RuntimeError('Native process exited before ' + needle)
            continue
        if line is not None:
            plain = re.sub(r'\x1b\[[0-9;]*m', '', line)
            if needle in plain: return plain
    raise TimeoutError('Timed out waiting for ' + needle)


def send(server, command):
    server.stdin.write(command + '\n'); server.stdin.flush()


def prime(args):
    target, manifest = load_lab(args)
    if manifest.get('primed'):
        return
    server_dir = Path(manifest['server']); props = server_dir / 'server.properties'
    original = props.read_text()
    temporary = re.sub(r'^level-name=.*$', 'level-name=cubiclab-bootstrap', original, flags=re.M)
    evidence = target / 'runs/prime'
    evidence.mkdir(parents=True, exist_ok=False)
    processes = []; result = {'purpose': 'Generate dependency-owned first-use inputs and restart both native processes', 'passed': False}
    try:
        props.write_text(temporary, encoding='utf-8')
        server_messages, client_messages = queue.Queue(), queue.Queue()
        server = spawn(argv(manifest, False), server_dir, evidence / 'server.log', server_messages); processes.append(server)
        await_line(server_messages, 'Done (', processes, 240)
        client = spawn(argv(manifest, True), Path(manifest['client']), evidence / 'client.log', client_messages); processes.append(client)
        await_line(server_messages, PLAYER + ' joined the game', processes, 240)
        result['initialScreen'] = await_line(client_messages, 'CUBICLAB_CLIENT_VIEW screen=', processes, 30).strip()
        send(server, 'cubiclab quit'); client.wait(timeout=45)
        send(server, 'save-all'); send(server, 'stop'); server.wait(timeout=90)
        if client.returncode != 0 or server.returncode != 0: raise RuntimeError('Priming processes did not exit cleanly')
        result['passed'] = True
        manifest['primed'] = True
        manifest['generatedLibraryHashes'] = record_generated_libraries(manifest)
        write_json(target / 'lab.json', manifest)
        print('First-use client/server priming completed; generated inputs retained.', flush=True)
    except Exception as error:
        result['failure'] = str(error)
        raise
    finally:
        if processes and processes[0].poll() is None:
            try: send(processes[0], 'stop'); processes[0].wait(timeout=45)
            except (OSError, subprocess.TimeoutExpired): pass
        for process in reversed(processes):
            if process.poll() is None: process.terminate(); process.wait(timeout=15)
        props.write_text(original, encoding='utf-8')
        result['processExitCodes'] = [process.returncode for process in processes]
        write_json(evidence / 'result.json', result)
    export_client(args)


def run(args):
    prime(args)
    target, manifest = load_lab(args)
    server_dir, client_dir = Path(manifest['server']), Path(manifest['client'])
    phase = args.phase
    if phase == 'write' and (server_dir / 'riven-dev/level.dat').exists(): raise RuntimeError('Write requires a fresh world')
    if phase == 'read' and not (server_dir / 'riven-dev/level.dat').exists(): raise RuntimeError('Read requires a saved fixture')
    evidence = target / 'runs' / phase
    evidence.mkdir(parents=True, exist_ok=False)
    server_messages, client_messages = queue.Queue(), queue.Queue()
    processes = []; result = {'schema': 1, 'phase': phase, 'passed': False, 'scenarios': [], 'jfr': args.jfr,
        'inputHashesBeforeLaunch': record_inputs(manifest)}
    try:
        server_command = argv(manifest, False, evidence / 'server.jfr' if args.jfr else None)
        server = spawn(server_command, server_dir, evidence / 'server.log', server_messages); processes.append(server)
        write_json(evidence / 'server-process.json', {'pid': server.pid, 'command': server_command})
        await_line(server_messages, 'Done (', processes, 240)
        client_command = argv(manifest, True, evidence / 'client.jfr' if args.jfr else None)
        client = spawn(client_command, client_dir, evidence / 'client.log', client_messages); processes.append(client)
        write_json(evidence / 'client-process.json', {'pid': client.pid, 'command': client_command})
        await_line(server_messages, PLAYER + ' joined the game', processes, 240)
        await_line(client_messages, 'CUBICLAB_CLIENT_VIEW screen=none', processes, 45)
        print('Real native client joined the loopback server.', flush=True)
        scenarios = args.scenarios.split(',') if args.scenarios else (
            ['idle', 'generate', 'resident', 'save', 'horizontal', 'vertical'] if phase == 'write' else ['idle', 'load-sync', 'load-async', 'resident'])
        for scenario in scenarios:
            send(server, 'cubiclab run ' + scenario)
            started = await_line(server_messages, 'CUBICLAB_STARTED', processes, 10)
            run_id = re.search(r'runId=([0-9a-f-]{36})', started)[1]
            ended = await_line(server_messages, 'CUBICLAB_SERVER_RESULT runId=' + run_id, processes, 210)
            if ' PASS' not in ended: raise RuntimeError('Scenario failed: ' + ended.strip())
            await_line(server_messages, 'CUBICLAB_CLIENT_RESULT runId=' + run_id, processes, 30)
            server_data = json.loads((server_dir / 'cubiclab-results' / run_id / 'server.json').read_text())
            client_data = json.loads((client_dir / 'cubiclab-results' / run_id / 'client.json').read_text())
            if not client_data['frameIntervals']['count']: raise RuntimeError('No real rendered frames captured')
            if client_data['framesWithGui']: raise RuntimeError('A GUI covered the world during measurement; preserve this run and resolve first-use setup')
            if scenario in ('horizontal', 'vertical') and not client_data['packets']['cubeCount']:
                raise RuntimeError('Streaming test received no cubes')
            row = {'scenario': scenario, 'runId': run_id, 'server': server_data, 'client': client_data}
            result['scenarios'].append(row)
            print(f'{scenario}: PASS; server tick p95={server_data["serverTicks"]["p95Ms"]:.2f} ms, '
                  f'frame p95={client_data["frameIntervals"]["p95Ms"]:.2f} ms, cubes={client_data["packets"]["cubeCount"]}', flush=True)
        send(server, 'tp ' + PLAYER + ' 0 80 0'); time.sleep(2)
        send(server, 'cubiclab quit'); client.wait(timeout=45)
        send(server, 'save-all'); send(server, 'stop'); server.wait(timeout=90)
        result['clientExitCode'] = client.returncode; result['serverExitCode'] = server.returncode
        result['passed'] = client.returncode == 0 and server.returncode == 0
    except Exception as error:
        result['failure'] = str(error)
        raise
    finally:
        if processes and processes[0].poll() is None:
            try:
                send(processes[0], 'cubiclab cancel'); time.sleep(.15)
                send(processes[0], 'cubiclab quit'); send(processes[0], 'save-all'); send(processes[0], 'stop')
                processes[0].wait(timeout=45)
            except (OSError, subprocess.TimeoutExpired): pass
        for process in reversed(processes):
            if process.poll() is None:
                process.terminate()
                try: process.wait(timeout=15)
                except subprocess.TimeoutExpired: process.kill(); process.wait()
        write_json(evidence / 'result.json', result)
    print(evidence / 'result.json')
    return 0 if result['passed'] else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['prepare', 'prime', 'export', 'run', 'server', 'client'])
    parser.add_argument('--riven-workspace', type=Path, default=FORK.parents[1])
    parser.add_argument('--name', required=True)
    parser.add_argument('--cubic-jar', type=Path)
    parser.add_argument('--client-profile', default='baseline', help='Optional client-only renderer profile: baseline, celeritas, celeritas-demonica')
    parser.add_argument('--runtime-release', help='Explicit compatibility runtime override: 0.6.13-alpha. Default preparation still verifies the reviewed latest release.')
    parser.add_argument('--port', type=int, default=25590)
    parser.add_argument('--phase', choices=['write', 'read'], default='write')
    parser.add_argument('--scenarios', help='Comma-separated scenario override; prerequisites still apply')
    parser.add_argument('--jfr', action='store_true')
    args = parser.parse_args(); args.riven_workspace = args.riven_workspace.resolve()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,63}', args.name): parser.error('Invalid lab name')
    if args.scenarios and any(s not in ['idle', 'generate', 'resident', 'save', 'load-sync', 'load-async', 'horizontal', 'vertical'] for s in args.scenarios.split(',')):
        parser.error('Unknown scenario in --scenarios')
    if args.command == 'prepare': prepare(args); return
    if args.command == 'prime': prime(args); return
    if args.command == 'export': export_client(args); return
    if args.command == 'run': raise SystemExit(run(args))
    _, manifest = load_lab(args)
    client = args.command == 'client'
    raise SystemExit(subprocess.call(argv(manifest, client), cwd=manifest['client' if client else 'server']))


if __name__ == '__main__': main()
