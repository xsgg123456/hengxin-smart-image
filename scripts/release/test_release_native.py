"""Filesystem tests for native release backup/install/rollback, no service access."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import subprocess
import sys

spec = importlib.util.spec_from_file_location('native_release', Path(__file__).with_name('image-inputs-native.py'))
native_release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(native_release)


class NativeReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.native = self.root / 'native'
        self.source = self.root / 'source'
        self.backup = self.root / 'backup'
        self.backup.mkdir()
        for name in native_release.FILES:
            path = self.source / 'backend' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('new:' + name)
        self.originals = native_release.FILES[:3]
        for name in self.originals:
            path = self.native / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('old:' + name)

    def assert_restored(self):
        for name in native_release.FILES:
            path = self.native / name
            if name in self.originals:
                self.assertEqual(path.read_text(), 'old:' + name)
            else:
                self.assertFalse(path.exists(), name)

    def test_existing_new_module_restored_and_absent_modules_removed(self):
        native_release.backup_files(self.native, self.backup)
        native_release.install_files(self.source, self.native)
        for name in native_release.FILES:
            self.assertEqual((self.native / name).read_text(), 'new:' + name)
        native_release.restore_files(self.native, self.backup)
        self.assert_restored()
        native_release.restore_files(self.native, self.backup)
        self.assert_restored()

    def test_partial_install_failure_can_restore(self):
        native_release.backup_files(self.native, self.backup)
        (self.source / 'backend' / native_release.FILES[-1]).unlink()
        with self.assertRaises(FileNotFoundError):
            native_release.install_files(self.source, self.native)
        native_release.restore_files(self.native, self.backup)
        self.assert_restored()
        self.assertFalse(list(self.native.rglob('*.release-new')))

    def test_backup_failure_does_not_modify_native(self):
        (self.backup / 'native-files').mkdir()
        with self.assertRaises(FileExistsError):
            native_release.backup_files(self.native, self.backup)
        self.assert_restored()
        self.assertFalse((self.backup / 'native-state.json').exists())

    def test_restore_rejects_paths_outside_whitelist(self):
        native_release.backup_files(self.native, self.backup)
        state = self.backup / 'native-state.json'
        value = json.loads(state.read_text())
        value['../outside'] = False
        state.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            native_release.restore_files(self.native, self.backup)
        self.assert_restored()

    def test_restore_rejects_invalid_presence_flags(self):
        native_release.backup_files(self.native, self.backup)
        state = self.backup / 'native-state.json'
        value = json.loads(state.read_text())
        value[native_release.FILES[0]] = 'false'
        state.write_text(json.dumps(value))
        with self.assertRaises(ValueError):
            native_release.restore_files(self.native, self.backup)

    def test_frontend_manifest_matches_seven_native_files(self):
        app = self.root / 'app'
        (app / 'frontend/dist').mkdir(parents=True)
        (self.source / 'frontend/dist').mkdir(parents=True)
        (self.source / 'frontend/dist/index.html').write_text('<html>release</html>')
        (self.source / 'frontend/package.json').write_text('{"version":"0.2.6"}')
        expected = {'backend/' + name: 'test-digest' for name in native_release.FILES}
        files = {**expected, 'backend/app/execution/prompts.py': 'unchanged'}
        (self.source / 'release.json').write_text(json.dumps({'files': files}))
        subprocess.run([sys.executable, str(Path(__file__).with_name('image-inputs-frontend.py')),
                        str(self.source), str(app), 'test-override.yaml'], check=True)
        manifest = json.loads((app / 'NATIVE_IMAGE_INPUTS_RELEASE.json').read_text())
        self.assertEqual(manifest['files'], expected)
        self.assertTrue(manifest['composeBaseOverlays'][-1].endswith('annotation-20260924-6b43b3c/api-override.yaml'))


if __name__ == '__main__':
    unittest.main()
