import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('frontend_static', Path(__file__).with_name('frontend-static.py'))
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class StaticReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source, self.app, self.backup = (self.root / n for n in ('source', 'app', 'backup'))
        files = {'frontend/dist/index.html': b'new entry',
                 'frontend/dist/assets/new.js': b'new asset',
                 'frontend/package.json': b'{"version":"0.2.18"}'}
        for name, value in files.items():
            self.write(self.source / name, value)
        self.write(self.source / 'release.json', json.dumps(dict(release='test', frontendVersion='0.2.18',
            files={n: hashlib.sha256(b).hexdigest() for n, b in files.items()})).encode())
        self.write(self.app / 'frontend/dist/index.html', b'old entry')
        self.write(self.app / 'frontend/dist/index.html.gz', b'old compressed entry')
        self.write(self.app / 'frontend/dist/assets/old.js', b'old asset')
        self.write(self.app / 'frontend/package.json', b'{"version":"0.2.17"}')
        self.write(self.app / 'API_RELEASE.json', b'backend unchanged')

    def write(self, path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)

    def test_install_preserves_backend_and_old_assets(self):
        release.deploy(self.source, self.app, self.backup)
        self.assertEqual((self.app / 'frontend/dist/index.html').read_bytes(), b'new entry')
        self.assertFalse((self.app / 'frontend/dist/index.html.gz').exists())
        self.assertEqual((self.app / 'frontend/dist/assets/old.js').read_bytes(), b'old asset')
        self.assertEqual((self.app / 'API_RELEASE.json').read_bytes(), b'backend unchanged')
        self.assertEqual((self.backup / 'frontend/dist/index.html').read_bytes(), b'old entry')

    def test_corrupt_archive_rejected_before_backup(self):
        (self.source / 'frontend/dist/index.html').write_bytes(b'corrupted')
        with self.assertRaises(AssertionError):
            release.deploy(self.source, self.app, self.backup)
        self.assertFalse(self.backup.exists())

    def test_same_asset_path_changed_rejected(self):
        self.write(self.app / 'frontend/dist/assets/new.js', b'different previous asset')
        with self.assertRaises(AssertionError):
            release.deploy(self.source, self.app, self.backup)
        self.assertEqual((self.app / 'frontend/dist/index.html').read_bytes(), b'old entry')

    def test_failure_after_switch_restores_old_entry_and_metadata(self):
        original = release.verify
        def fail_installed(path, manifest):
            if path == self.app:
                raise RuntimeError('simulated installed hash failure')
            return original(path, manifest)
        with patch.object(release, 'verify', side_effect=fail_installed):
            with self.assertRaises(RuntimeError):
                release.deploy(self.source, self.app, self.backup)
        self.assertEqual((self.app / 'frontend/dist/index.html').read_bytes(), b'old entry')
        self.assertEqual((self.app / 'frontend/dist/index.html.gz').read_bytes(), b'old compressed entry')
        self.assertEqual(json.loads((self.app / 'frontend/package.json').read_text())['version'], '0.2.17')
        self.assertFalse((self.app / 'FRONTEND_RELEASE.json').exists())


if __name__ == '__main__':
    unittest.main()
