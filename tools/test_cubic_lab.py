"""Control-plane regressions; these do not simulate Minecraft performance."""
import queue
import argparse
import json
from pathlib import Path
import tempfile
import unittest
import zipfile
import cubic_lab as lab

class LabControlTest(unittest.TestCase):
    def test_changed_prepared_runtime_is_rejected_before_launch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); directory = root / '.local/cubic-lab/check'
            directory.mkdir(parents=True)
            artifact = root / 'loader.jar'; artifact.write_bytes(b'reviewed loader bytes')
            manifest = {'runtimeArtifacts': {'client': {'path': str(artifact), 'sha256': lab.sha(artifact)}}}
            (directory / 'lab.json').write_text(json.dumps(manifest), encoding='utf-8')
            args = argparse.Namespace(riven_workspace=root, name='check')
            self.assertEqual(lab.load_lab(args)[1], manifest)
            artifact.write_bytes(b'changed loader bytes')
            with self.assertRaises(RuntimeError): lab.load_lab(args)

    def test_same_tag_asset_replacement_requires_review_before_installation(self):
        hashes = {'installer': 'a' * 64, 'universal': 'b' * 64, 'prism': 'c' * 64}
        release = {'assets': [
            {'name': 'cleanroom-0.7.0-alpha-installer.jar', 'digest': 'sha256:' + hashes['installer']},
            {'name': 'cleanroom-0.7.0-alpha-universal.jar', 'digest': 'sha256:' + hashes['universal']},
            {'name': 'cleanroom-0.7.0-alpha.zip', 'digest': 'sha256:' + hashes['prism']} ]}
        self.assertEqual(set(lab.runtime_assets(release, '0.7.0-alpha', hashes)), set(hashes))
        release['assets'][0]['digest'] = 'sha256:' + 'd' * 64
        with self.assertRaises(RuntimeError): lab.runtime_assets(release, '0.7.0-alpha', hashes)
        with self.assertRaises(RuntimeError): lab.runtime_assets(release, '0.7.0', hashes)

    def test_current_and_retained_070_versions_keep_their_compatibility_bridge(self):
        self.assertTrue(lab.needs_070_compat('0.7.0'))
        self.assertTrue(lab.needs_070_compat('0.7.0-alpha'))
        self.assertFalse(lab.needs_070_compat('0.6.13-alpha'))
        self.assertFalse(lab.needs_070_compat('0.8.0'))

    def test_color_coded_join_is_detected(self):
        messages = queue.Queue(); messages.put('\x1b[0;33;1mCubicLab\x1b[m\x1b[0;33;1m joined the game\x1b[m')
        self.assertIn('CubicLab joined the game', lab.await_line(messages, 'CubicLab joined the game', [], 1))
    def test_artifact_and_native_entries_merge_without_losing_java_classes(self):
        components = [{'libraries': [
            {'name': 'org.lwjgl:lwjgl:3.4.3', 'downloads': {'artifact': {'sha1': 'abc'}}},
            {'name': 'org.lwjgl:lwjgl:3.4.3', 'downloads': {'classifiers': {'natives-windows': {'sha1': 'def'}}},
             'natives': {'windows': 'natives-windows'}}]}]
        result = lab.merged_libraries(components, 'windows', 'x86_64')
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['downloads']['artifact']['sha1'], 'abc')
        self.assertEqual(result[0]['downloads']['classifiers']['natives-windows']['sha1'], 'def')
    def test_loader_library_overrides_base_version(self):
        components = [{'libraries': [{'name': 'a:b:1', 'downloads': {'artifact': {'sha1': 'old'}}}]},
                      {'libraries': [{'name': 'a:b:2', 'downloads': {'artifact': {'sha1': 'new'}}}]}]
        self.assertEqual(lab.merged_libraries(components, 'windows', 'x86_64')[0]['name'], 'a:b:2')
    def test_windows_x64_excludes_other_native_architectures(self):
        for suffix in ['natives-windows-arm64', 'natives-windows-x86']:
            self.assertFalse(lab.library_allowed({'name': 'org.lwjgl:lwjgl:3:' + suffix}, 'windows', 'x86_64'))
        self.assertTrue(lab.library_allowed({'name': 'org.lwjgl:lwjgl:3:natives-windows'}, 'windows', 'x86_64'))
    def test_generated_library_must_match_retained_embedded_bytes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary); mods = root / 'mods'; (mods / '1.12.2').mkdir(parents=True)
            payload = b'the exact embedded library bytes'
            with zipfile.ZipFile(mods / 'owner.jar', 'w') as archive:
                archive.writestr('lib/runtime.jar', payload)
            extracted = mods / '1.12.2/runtime.jar'; extracted.write_bytes(payload)
            manifest = {'server': str(root), 'client': str(root)}
            record = lab.record_generated_libraries(manifest)['client']['1.12.2/runtime.jar']
            self.assertEqual(record['owners'], [{'mod': 'owner.jar', 'embeddedEntry': 'lib/runtime.jar'}])
            extracted.write_bytes(b'a changed library must fail qualification')
            with self.assertRaises(RuntimeError): lab.record_generated_libraries(manifest)
    def test_client_addons_do_not_change_server_or_legacy_hash_contract(self):
        manifest = {'modHashes': {'core.jar': 'a'}, 'clientModHashes': {'core.jar': 'a', 'renderer.jar': 'b'}}
        self.assertEqual(lab.expected_mod_hashes(manifest, 'server'), {'core.jar': 'a'})
        self.assertEqual(lab.expected_mod_hashes(manifest, 'client'), {'core.jar': 'a', 'renderer.jar': 'b'})
        self.assertEqual(lab.expected_mod_hashes({'modHashes': {'core.jar': 'a'}}, 'client'), {'core.jar': 'a'})
    def test_combined_renderer_profile_includes_demonica_exact_pin(self):
        baseline = lab.read_client_profile('baseline')
        combined = lab.read_client_profile('celeritas-demonica')
        self.assertEqual(baseline['mods'], [])
        self.assertEqual([mod['slug'] for mod in combined['mods']], ['celeritas', 'demonica'])
        self.assertTrue(all(mod['side'] == 'client' for mod in combined['mods']))
        self.assertEqual(combined['mods'][0]['sha256'], '5bf123a6da6190f6e061cd3fd069a2bddcbf6ebf57894381b6c888c06a94f982')

if __name__ == '__main__': unittest.main()
