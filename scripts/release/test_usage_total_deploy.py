"""Isolated release failure tests: no Docker, network or production access."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch

spec = importlib.util.spec_from_file_location('usage_total_deploy', Path(__file__).with_name('usage-total-deploy.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


class DeployTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.source = self.work / 'src'
        self.source.mkdir()
        self.manifest = {'release': 'usage-total-20261010-abcdef0', 'migration': '0026',
                         'frontendVersion': '0.2.21', 'files': {'frontend/dist/index.html': 'abc'}}
        (self.source / 'release.json').write_text(json.dumps(self.manifest))
        (self.source / 'frontend').mkdir()
        (self.source / 'frontend/package.json').write_text('{"version":"0.2.21"}')
        (self.work / 'INSTALL_TEST_IMAGE_ID').write_text('new-id')
        self.image = 'new-image'
        self.old = {'Image': 'old-id', 'Config': {'Image': 'old-image'}}
        self.new = {'Image': 'new-id', 'Config': {'Image': self.image}}
        self.runtime = Mock()
        self.runtime.prepare.return_value = (['original.yml'], self.image, self.old)
        self.runtime.inspect.return_value = self.new
        self.runtime.api_settings.return_value = {'settings': 'preserved'}
        self.runtime.identity.return_value = {'workers': 'original'}
        self.runtime.run.side_effect = lambda *a, **kw: 'old-id' if a[-1] == 'old-image' else 'new-id'
        self.addCleanup(patch.stopall)
        patch.object(d, 'r', self.runtime).start()
        (self.work / 'INSTALL_TEST_EVIDENCE.json').write_text(json.dumps(d.evidence(self.source, self.image)))

    def deploy(self):
        d.deploy(self.work, self.source, self.work / 'backup', self.manifest, self.image)

    def test_success_replaces_only_api_and_verifies_twice(self):
        self.deploy()
        calls = self.runtime.compose.call_args_list
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0].args[1:], ('up', '-d', '--no-deps', '--wait', '--timeout', '120', 'api'))
        verifies = [c.args for c in self.runtime.run.call_args_list if c.args[0] == 'python3']
        self.assertEqual(len(verifies), 2)
        self.assertEqual(verifies[0][-1], '--api-only')
        self.runtime.restore.assert_not_called()

    def test_all_post_switch_failures_rollback_api_and_raise(self):
        for failure in ('compose', 'ready', 'reload_nginx', 'publish'):
            with self.subTest(failure=failure):
                self.runtime.reset_mock(side_effect=True)
                self.runtime.run.side_effect = lambda *a, **kw: 'old-id' if a[-1] == 'old-image' else 'new-id'
                self.runtime.inspect.side_effect = [self.new, self.old] if failure != 'compose' else [self.old]
                getattr(self.runtime, failure).side_effect = [RuntimeError('injected'), None]
                with self.assertRaises(RuntimeError): self.deploy()
                self.assertEqual(self.runtime.compose.call_args_list[-1].args[0], ['original.yml'])
                self.assertTrue(all(c.args[-1] == 'api' for c in self.runtime.compose.call_args_list))
                self.runtime.unchanged.assert_called_with({'workers': 'original'})

    def test_final_verify_failure_restores_frontend(self):
        def command(*args, **kwargs):
            if args[0] == 'python3' and args[-1] != '--api-only': raise RuntimeError('verify failed')
            return 'old-id' if args[-1] == 'old-image' else 'new-id'
        self.runtime.run.side_effect = command
        self.runtime.inspect.side_effect = [self.new, self.old]
        with self.assertRaises(RuntimeError): self.deploy()
        self.runtime.restore.assert_called_once()

    def test_api_rollback_failure_still_restores_frontend_and_checks_workers(self):
        self.runtime.publish.side_effect = RuntimeError('partial publish')
        self.runtime.compose.side_effect = [None, RuntimeError('rollback api failed')]
        with self.assertRaisesRegex(RuntimeError, 'rollback incomplete'): self.deploy()
        self.runtime.restore.assert_called_once()
        self.runtime.unchanged.assert_called_with({'workers': 'original'})

    def test_runtime_settings_drift_rolls_back(self):
        self.runtime.api_settings.side_effect = ['new-settings', 'old-settings', 'old-settings', 'old-settings']
        self.runtime.inspect.side_effect = [self.new, self.old]
        with self.assertRaisesRegex(AssertionError, 'runtime settings drifted'): self.deploy()
        self.assertEqual(self.runtime.compose.call_args_list[-1].args[0], ['original.yml'])

    def test_worker_drift_before_switch_refuses_update(self):
        self.runtime.unchanged.side_effect = AssertionError('worker drift')
        with self.assertRaises(AssertionError): self.deploy()
        self.runtime.compose.assert_not_called()

    def test_install_receipt_manifest_and_image_are_bound(self):
        (self.source / 'release.json').write_text('{}')
        with self.assertRaises(AssertionError): self.deploy()
        self.runtime.prepare.assert_not_called()

    def test_missing_receipt_refuses_update(self):
        (self.work / 'INSTALL_TEST_IMAGE_ID').unlink()
        with self.assertRaises(FileNotFoundError): self.deploy()
        self.runtime.compose.assert_not_called()

    def test_version_and_release_validation(self):
        d.manifest_for(self.source, self.manifest['release'])
        for release in ('../../bad', 'management-20261010-abcdef0'):
            with self.assertRaises(AssertionError): d.manifest_for(self.source, release)
        (self.source / 'frontend/package.json').write_text('{"version":"0.2.20"}')
        with self.assertRaises(AssertionError): d.manifest_for(self.source, self.manifest['release'])

    def test_build_uses_immutable_image_and_disconnected_network(self):
        with patch.object(d.subprocess, 'run') as process:
            d.build(self.work, self.source, self.image)
        command = process.call_args.args[0]
        self.assertEqual(command[command.index('--network') + 1], 'none')
        self.assertIn('new-id', command)
        self.assertNotIn(self.image, command)
        self.assertEqual((self.work / 'INSTALL_TEST_IMAGE_ID').read_text(), 'new-id')

    def test_build_failure_removes_stale_credentials(self):
        self.runtime.run.side_effect = RuntimeError('build failed')
        with self.assertRaises(RuntimeError): d.build(self.work, self.source, self.image)
        self.assertFalse((self.work / 'INSTALL_TEST_IMAGE_ID').exists())
        self.assertFalse((self.work / 'INSTALL_TEST_EVIDENCE.json').exists())


class RuntimeTests(unittest.TestCase):
    def test_prepare_generates_api_only_override_and_keeps_migrate(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            original = root / 'original.yml'
            original.write_text('original')
            live = {'Config': {'Image': d.r.OLD_IMAGE, 'Env': ['A=B'], 'Cmd': ['serve'],
                              'Labels': {'com.docker.compose.project.config_files': str(original)}}}
            config = {'services': {'api': {'image': d.r.OLD_IMAGE, 'environment': {'A': 'B'},
                                          'command': ['serve']}, 'migrate': {'image': 'old-migrate'}}}
            def compose(paths, *args, **kwargs):
                result = json.loads(json.dumps(config))
                if len(paths) == 2:
                    override = json.loads(Path(paths[1]).read_text())
                    self.assertEqual(set(override['services']), {'api'})
                    result['services']['api'].update(override['services']['api'])
                return json.dumps(result)
            with patch.object(d.r, 'hashes'), patch.object(d.r, 'sql', return_value='0026'), \
                    patch.object(d.r, 'inspect', return_value=live), patch.object(d.r, 'ready'), \
                    patch.object(d.r, 'compose', side_effect=compose):
                paths, image, old = d.r.prepare(root, {'release': 'usage-total-20261010-abcdef0'})
            self.assertEqual(paths, [str(original)])
            saved = json.loads((root / 'old-compose.private.json').read_text())
            self.assertEqual(saved, config)
            self.assertEqual(old, live)
            self.assertTrue(image.endswith('abcdef0'))

    def test_identity_drift_rejected(self):
        with patch.object(d.r, 'identity', return_value={'worker': ['new-id', 'new-start']}):
            with self.assertRaisesRegex(AssertionError, 'identity'):
                d.r.unchanged({'worker': ['old-id', 'old-start']})

    def test_publish_and_restore_only_three_markers_keep_assets_and_nginx(self):
        with tempfile.TemporaryDirectory() as root:
            root = Path(root)
            app, src, backup = root / 'app', root / 'src', root / 'backup'
            for path in (app / 'frontend/dist/assets', src / 'frontend/dist/assets', backup): path.mkdir(parents=True)
            (app / 'frontend/dist/assets/old.js').write_text('old asset')
            (app / 'API_IMAGE_RELEASE.json').write_text('executor unchanged')
            (src / 'frontend/dist/assets/new.js').write_text('new asset')
            (src / 'frontend/dist/index.html').write_text('new index')
            (src / 'frontend/package.json').write_text('{"version":"0.2.21"}')
            (backup / 'index.html').write_text('old index')
            (backup / 'frontend-package.json').write_text('{"version":"0.2.20"}')
            (backup / 'COMPLETE').touch()
            with patch.object(d.r, 'APP', app):
                d.r.publish(src, root, {'release': 'test'}, ['old.yml'])
                self.assertEqual((app / 'frontend/dist/index.html').read_text(), 'new index')
                self.assertEqual(set(p.name for p in app.glob('*RELEASE.json')),
                                 set(d.r.MARKERS) | {'API_IMAGE_RELEASE.json'})
                d.r.restore(backup)
            self.assertEqual((app / 'frontend/dist/index.html').read_text(), 'old index')
            self.assertEqual((app / 'API_IMAGE_RELEASE.json').read_text(), 'executor unchanged')
            self.assertTrue((app / 'frontend/dist/assets/old.js').exists())
            self.assertTrue((app / 'frontend/dist/assets/new.js').exists())

    def test_backup_never_overwrites_existing_directory(self):
        with tempfile.TemporaryDirectory() as root:
            with self.assertRaises(FileExistsError): d.r.backup(Path(root), Path(root), {})


if __name__ == '__main__':
    unittest.main()
