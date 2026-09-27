"""Offline release/rollback and archive boundary tests."""
import importlib.util
import json
from pathlib import Path
import os
import tarfile
import tempfile
import unittest

spec = importlib.util.spec_from_file_location('delivery_native', Path(__file__).with_name('delivery-native.py'))
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


class DeliveryNativeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.native, self.source, self.backup = [self.root / n for n in ('native', 'source', 'backup')]
        self.backup.mkdir()
        for index, name in enumerate(release.FILES):
            src, dst = self.source / 'backend' / name, self.native / name
            src.parent.mkdir(parents=True, exist_ok=True)
            dst.parent.mkdir(parents=True, exist_ok=True)
            src.write_text('new:' + name)
            if index % 2 == 0:
                dst.write_text('old:' + name)
        (self.native / '.venv/lib').mkdir(parents=True)
        (self.native / '.venv/lib/dependency').write_text('original dependency')
        (self.native / 'runtime/auth').mkdir(parents=True)
        (self.native / 'runtime/auth/secret').write_text('unchanged')

    def test_source_new_files_and_dependencies_roll_back(self):
        release.backup_files(self.native, self.backup)
        release.install_files(self.source, self.native)
        for name in release.FILES:
            self.assertEqual((self.native / name).read_text(), 'new:' + name)
        (self.native / '.venv/lib/dependency').write_text('updated dependency')
        (self.native / '.venv/lib/new').write_text('new dependency')
        release.restore_files(self.native, self.backup)
        for index, name in enumerate(release.FILES):
            if index % 2 == 0:
                self.assertEqual((self.native / name).read_text(), 'old:' + name)
            else:
                self.assertFalse((self.native / name).exists())
        self.assertEqual((self.native / '.venv/lib/dependency').read_text(), 'original dependency')
        self.assertFalse((self.native / '.venv/lib/new').exists())
        self.assertEqual((self.backup / 'failed-venv/lib/dependency').read_text(), 'updated dependency')
        self.assertEqual((self.native / 'runtime/auth/secret').read_text(), 'unchanged')

    def test_invalid_whitelist_and_metadata_rejected(self):
        release.backup_files(self.native, self.backup)
        path = self.backup / 'native-state.json'
        state = json.loads(path.read_text())
        state['files']['../auth'] = None
        path.write_text(json.dumps(state))
        with self.assertRaises(ValueError):
            release.restore_files(self.native, self.backup)
        with self.assertRaises(ValueError):
            release.safe_path(self.native, 'runtime/auth/secret')

    def test_incomplete_install_does_not_mutate(self):
        (self.source / 'backend' / release.FILES[-1]).unlink()
        with self.assertRaises(FileNotFoundError):
            release.install_files(self.source, self.native)
        self.assertEqual((self.native / release.FILES[0]).read_text(), 'old:' + release.FILES[0])

    def test_reject_nested_backup(self):
        inside = self.native / 'backup'
        inside.mkdir()
        with self.assertRaises(ValueError):
            release.backup_files(self.native, inside)

    def test_checksum_corruption_does_not_modify_native(self):
        release.backup_files(self.native, self.backup)
        with (self.backup / 'native-venv.tar').open('ab') as stream:
            stream.write(b'corruption')
        with self.assertRaises(ValueError):
            release.restore_files(self.native, self.backup)
        self.assertFalse((self.backup / 'failed-venv').exists())

    def test_malicious_archive_rejected_before_any_native_mutation(self):
        release.backup_files(self.native, self.backup)
        archive = self.backup / 'native-venv.tar'
        with tarfile.open(archive, 'w') as stream:
            stream.addfile(tarfile.TarInfo('.venv/../../outside'))
        path = self.backup / 'native-state.json'
        state = json.loads(path.read_text())
        state['venv_sha256'] = release.digest(archive)
        path.write_text(json.dumps(state))
        with self.assertRaises(ValueError):
            release.restore_files(self.native, self.backup)
        self.assertFalse((self.backup / 'failed-venv').exists())
        self.assertFalse((self.root / 'outside').exists())

    def test_source_metadata_saved_and_restored(self):
        original = self.native / release.FILES[0]
        attrs = release.metadata(original)
        release.backup_files(self.native, self.backup)
        state = json.loads((self.backup / 'native-state.json').read_text())
        self.assertEqual(state['files'][release.FILES[0]], attrs)
        release.install_files(self.source, self.native)
        self.assertEqual(release.metadata(original), attrs)
        release.restore_files(self.native, self.backup)
        self.assertEqual(release.metadata(original), attrs)

    def test_archive_member_boundaries(self):
        root = tarfile.TarInfo('.venv')
        root.type = tarfile.DIRTYPE
        for name in ('/tmp/outside', '.venv/../outside', 'runtime/auth', '.venv\\evil'):
            with self.subTest(name=name), self.assertRaises(ValueError):
                release.validate_members([root, tarfile.TarInfo(name)])
        link = tarfile.TarInfo('.venv/lib/link')
        link.type, link.linkname = tarfile.SYMTYPE, '/tmp/outside'
        with self.assertRaises(ValueError):
            release.validate_members([root, link])
        link.linkname = '../lib'
        with self.assertRaises(ValueError):
            release.validate_members([root, link, tarfile.TarInfo('.venv/lib/link/child')])
        link.type = tarfile.LNKTYPE
        with self.assertRaises(ValueError):
            release.validate_members([root, link])

    def test_python_and_internal_symlink_members_allowed(self):
        root = tarfile.TarInfo('.venv')
        root.type = tarfile.DIRTYPE
        links = []
        for name, target in (('.venv/bin/python', '/usr/bin/python3.12'),
                             ('.venv/bin/python3', 'python'), ('.venv/lib64', 'lib')):
            member = tarfile.TarInfo(name)
            member.type, member.linkname = tarfile.SYMTYPE, target
            links.append(member)
        release.validate_members([root, *links])

    def test_symlink_parent_escape_rejected(self):
        outside = self.root / 'outside'
        outside.mkdir()
        linked = self.root / 'linked'
        try:
            linked.symlink_to(outside, target_is_directory=True)
        except OSError as error:
            self.skipTest(str(error))
        with self.assertRaises(ValueError):
            release.safe_path(linked, release.FILES[0])

    def test_hardlinked_dependencies_backed_up_as_files(self):
        os.link(self.native / '.venv/lib/dependency', self.native / '.venv/lib/second')
        release.backup_files(self.native, self.backup)
        with tarfile.open(self.backup / 'native-venv.tar') as archive:
            self.assertTrue(all(not member.islnk() for member in archive.getmembers()))
        release.restore_files(self.native, self.backup)
        self.assertEqual((self.native / '.venv/lib/second').read_text(), 'original dependency')


if __name__ == '__main__':
    unittest.main()
