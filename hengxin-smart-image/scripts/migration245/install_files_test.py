import hashlib
import io
import os
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import install_files as subject


def archive(entries):
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w') as out:
        for name, kind in entries:
            member = tarfile.TarInfo(name)
            member.type = kind
            if kind == tarfile.SYMTYPE:
                member.linkname = '/etc/passwd'
            out.addfile(member)
    stream.seek(0)
    return tarfile.open(fileobj=stream, mode='r')


class FileInstallationTests(unittest.TestCase):
    @unittest.skipUnless(os.name == 'posix', 'executable modes require the Linux integration run')
    def test_code_rejects_extra_files_and_changed_binary(self):
        with tempfile.TemporaryDirectory() as work:
            private = Path(work)
            stage = private / 'stage'
            roots = ['/opt/test-code/app.py']
            hashes = {}
            for relative in roots + list(subject.BINARIES):
                p = stage / relative.lstrip('/')
                p.parent.mkdir(parents=True, exist_ok=True)
                p.write_bytes(b'locked bytes')
                p.chmod(0o755)
                hashes[relative] = hashlib.sha256(p.read_bytes()).hexdigest()
            native = {roots[0]: {'sha256': hashes[roots[0]], 'size': 12, 'mode': 0o755}}
            (private / 'runtime-binaries.sha256').write_text(''.join(
                hashes[b] + '  ' + b + '\n' for b in subject.BINARIES))
            with patch.object(subject, 'PRIVATE', private):
                self.assertEqual(subject.verify(stage, 'code', {'native_hashes': native}), 1)
                extra = stage / 'opt/test-code/history.json'
                extra.write_text('{}')
                with self.assertRaisesRegex(RuntimeError, 'inventory mismatch'):
                    subject.verify(stage, 'code', {'native_hashes': native})
                extra.unlink()
                (stage / subject.BINARIES[0].lstrip('/')).write_bytes(b'tampered')
                with self.assertRaisesRegex(RuntimeError, 'runtime binary'):
                    subject.verify(stage, 'code', {'native_hashes': native})

    def test_archive_rejects_traversal_absolute_links_and_scope(self):
        for name, kind in [('../escape', tarfile.REGTYPE),
                           ('/allowed/file', tarfile.REGTYPE),
                           ('allowed/link', tarfile.SYMTYPE),
                           ('other/file', tarfile.REGTYPE),
                           ('allowed/device', tarfile.CHRTYPE)]:
            with self.subTest(name=name), archive([(name, kind)]) as candidate:
                with self.assertRaises(RuntimeError):
                    subject.safe_members(candidate, ['allowed'])

    def test_archive_accepts_scoped_files_and_rejects_duplicates(self):
        with archive([('allowed', tarfile.DIRTYPE), ('allowed/file', tarfile.REGTYPE)]) as a:
            self.assertEqual(len(subject.safe_members(a, ['allowed'])), 2)
        with archive([('allowed/file', tarfile.REGTYPE)] * 2) as a:
            with self.assertRaises(RuntimeError):
                subject.safe_members(a, ['allowed'])

    def test_frontend_requires_exact_manifest_and_bytes(self):
        with tempfile.TemporaryDirectory() as work:
            stage = Path(work)
            p = stage / 'frontend/dist/index.html'
            p.parent.mkdir(parents=True)
            p.write_bytes(b'approved build')
            runtime = {'frontend_release': {'files': {
                'frontend/dist/index.html': hashlib.sha256(p.read_bytes()).hexdigest()}}}
            self.assertEqual(subject.verify(stage, 'frontend', runtime), 1)
            p.write_bytes(b'changed build')
            with self.assertRaises(RuntimeError):
                subject.verify(stage, 'frontend', runtime)
            (p.parent / 'old-history.json').write_text('{}')
            with self.assertRaises(RuntimeError):
                subject.verify(stage, 'frontend', runtime)

    def test_skills_requires_unchanged_source_and_complete_hashes(self):
        with tempfile.TemporaryDirectory() as work:
            private = Path(work)
            stage = private / 'stage'
            p = stage / subject.SKILLS.lstrip('/') / 'packages/skill'
            p.parent.mkdir(parents=True)
            p.write_bytes(b'full skill contents')
            hashes = hashlib.sha256(p.read_bytes()).hexdigest() + '  ./packages/skill\n'
            (private / 'skills-before.sha256').write_text(hashes)
            after = private / 'skills-after.sha256'
            after.write_text(hashes)
            with patch.object(subject, 'PRIVATE', private):
                self.assertEqual(subject.verify(stage, 'skills', {}), 1)
                after.write_text(hashes + '\n')
                with self.assertRaises(RuntimeError):
                    subject.verify(stage, 'skills', {})
                after.write_text(hashes)
                p.write_bytes(b'corrupted')
                with self.assertRaises(RuntimeError):
                    subject.verify(stage, 'skills', {})

    def test_existing_destination_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as work:
            p = Path(work) / 'existing'
            p.write_bytes(b'keep')
            with self.assertRaises(RuntimeError):
                subject.validate_dest(p)
            self.assertEqual(p.read_bytes(), b'keep')

    def test_wrong_host_fails_before_accessing_target_paths(self):
        with patch.object(subject.socket, 'gethostname', return_value='racknerd-058889d'):
            with self.assertRaisesRegex(RuntimeError, 'target host mismatch'):
                subject.guard_private()


if __name__ == '__main__':
    unittest.main()
