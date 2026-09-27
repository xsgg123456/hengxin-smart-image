"""Regression checks for release allowlisting, provenance and privacy."""
import importlib.util
import json
import subprocess
import tarfile
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('package_delivery', Path(__file__).with_name('package-delivery.py'))
package = importlib.util.module_from_spec(spec)
spec.loader.exec_module(package)


class PackagingTests(unittest.TestCase):
    def test_closed_allowlist(self):
        for name in ('backend/app/a.py', 'backend/tests/test_a.py',
                     'backend/migrations/versions/0017_a.py', 'backend/uv.lock'):
            self.assertEqual(package.selected(package.APP + name), name)
        for name in ('backend/app/auth.json', 'backend/app/cache.pyc', 'backend/.env',
                     'frontend/src/a.py', 'backend/app/private.key', 'backend/data.db'):
            self.assertIsNone(package.selected(package.APP + name))
        self.assertIsNone(package.selected('scripts/release/unknown.py'))

    def test_privacy_blocks_real_credentials_and_personal_paths(self):
        for value in ('sk' + '-proj-' + 'a' * 32, 'sk' + '-' + 'a' * 32,
                      '-----BEGIN ' + 'RSA PRIVATE KEY-----',
                      'C:/' + 'Users/alice/file', '/' + 'Users/alice/file',
                      '/home/' + 'alice/.codex/auth.json'):
            with self.subTest(value=value[:5]), self.assertRaises(ValueError):
                package.privacy_check('backend/tests/test_any.py', value.encode())
        package.privacy_check('backend/app/a.py', b'/home/runner/.codex/generated_images/a.png')

    def test_fixture_exemptions_are_exact_and_still_scan_other_content(self):
        for name, fixtures in package.FIXTURES.items():
            for fixture in fixtures:
                self.assertTrue(package.privacy_check(name, fixture.encode()))
                with self.assertRaises(ValueError):
                    package.privacy_check('backend/tests/other.py', fixture.encode())
                with self.assertRaises(ValueError):
                    package.privacy_check(name, (fixture + 'sk' + '-proj-' + 'a' * 32).encode())
                with self.assertRaises(ValueError):
                    package.privacy_check(name, (fixture * 2).encode())

    def test_archive_and_guards(self):
        with tempfile.TemporaryDirectory() as directory:
            repo = Path(directory)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=repo, stderr=subprocess.DEVNULL)
            git('init')
            names = {package.APP + name for name in package.EXACT}
            names |= {'scripts/release/' + name for name in package.SCRIPTS}
            names |= {package.APP + 'backend/migrations/versions/0017_sample.py',
                      'scripts/release/package-delivery.py'}
            for name in names:
                target = repo / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(b'# safe source\r\n')
            git('add', '.')
            git('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid',
                '-c', 'core.hooksPath=/dev/null', 'commit', '-m', 'test')
            (repo / 'notes.md').write_text('untracked notes')
            approved = {'approved': True, 'currentId': 'candidate-test'}
            with patch.object(package, 'reviewed_status', return_value=approved):
                result = package.build(repo)
                root = repo / 'output/release' / result['release']
                manifest = json.loads((root / 'src/release.json').read_text())
                self.assertNotIn('release.json', manifest['files'])
                self.assertTrue(manifest['backendOnly'])
                self.assertEqual(manifest['candidateId'], 'candidate-test')
                self.assertTrue(result['archiveVerified'])
                with tarfile.open(root / 'release.tar.gz') as archive:
                    for member in archive.getmembers():
                        self.assertEqual((member.uid, member.gid, member.uname, member.gname),
                                         (0, 0, 'root', 'root'))
                        self.assertNotIn(b'\r', archive.extractfile(member).read())
                source = repo / package.APP / 'backend/pyproject.toml'
                source.write_bytes(b'dirty')
                with self.assertRaisesRegex(ValueError, 'clean and committed'):
                    package.build(repo)
                git('add', package.APP + 'backend/pyproject.toml')
                with self.assertRaisesRegex(ValueError, 'clean and committed'):
                    package.build(repo)

    def test_missing_review_is_rejected(self):
        with patch.object(package.subprocess, 'check_output', return_value=b'{"approved": false}'):
            with self.assertRaisesRegex(ValueError, 'approved snapshot'):
                package.reviewed_status(Path('.'))


if __name__ == '__main__':
    unittest.main()
