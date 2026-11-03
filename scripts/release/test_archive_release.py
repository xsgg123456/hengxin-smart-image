"""Real filesystem archive switches, rollback guards and closed package verification."""
import gzip
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tarfile
import tempfile
import unittest
from unittest.mock import patch

sys.dont_write_bytecode = True
HERE = Path(__file__).parent
spec = importlib.util.spec_from_file_location('archive_deploy', HERE/'archive-deploy.py')
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
r = d.r


class ArchiveReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source, self.app, self.backup = (self.root/n for n in ('source','app','backup'))
        self.files = {'frontend/package.json':json.dumps({'version':r.VERSION}).encode(),
                      'frontend/dist/index.html':b'<script src="/assets/new-hash.js"></script>',
                      'frontend/dist/assets/new-hash.js':b'new frontend'}
        self.files['frontend/dist/index.html.gz'] = gzip.compress(self.files['frontend/dist/index.html'])
        for name in r.HELPERS:
            self.files['scripts/release/'+name+'.py'] = (HERE/(name+'.py')).read_bytes()
        for name, raw in self.files.items():
            self.write(self.source/name, raw)
        self.manifest = dict(version=r.VERSION,baseVersion=r.BASE_VERSION,baseImage=r.BASE_IMAGE,
                             mode='release',frontendOnly=True,commit='a'*40,candidateId='b'*64,
                             release='archive-20261103-aaaaaaa',
                             files={n:hashlib.sha256(v).hexdigest() for n,v in self.files.items()})
        self.save_manifest()
        self.write(self.app/'frontend/package.json',json.dumps({'version':r.BASE_VERSION}).encode())
        self.write(self.app/'frontend/dist/index.html',b'old index')
        self.write(self.app/'frontend/dist/index.html.gz',gzip.compress(b'old index'))
        self.write(self.app/'frontend/dist/assets/old-hash.js',b'old frontend')
        self.original = {n:(self.app/n).read_bytes() for n in r.ENTRIES if (self.app/n).exists()}

    def write(self, path, data):
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(data)

    def save_manifest(self):
        self.write(self.source/'release.json',json.dumps(self.manifest).encode())

    def assert_original(self):
        for name, raw in self.original.items():
            self.assertEqual((self.app/name).read_bytes(),raw)
        self.assertFalse((self.app/'FRONTEND_RELEASE.json').exists())

    def test_valid_package_and_dependencies_from_extracted_archive(self):
        common = r.helper('package-text')
        raw = common.archive_bytes({**self.files,'release.json':(self.source/'release.json').read_bytes()})
        archive = self.root/'release.tar.gz'
        archive.write_bytes(raw)
        extracted = self.root/'extracted'
        with tarfile.open(archive) as tar:
            tar.extractall(extracted,filter='data')
        self.assertEqual(r.verify_package(extracted),self.manifest)
        result = subprocess.run([sys.executable,'-B',str(extracted/'scripts/release/archive-deploy.py'),'--help'],
                                capture_output=True,text=True)
        self.assertEqual(result.returncode,0,result.stderr)

    def test_candidate_rejected(self):
        self.manifest['mode'] = 'candidate'
        self.save_manifest()
        with self.assertRaisesRegex(RuntimeError,'committed'):
            r.verify_package(self.source)

    def test_source_identity_required(self):
        self.manifest['candidateId'] = ''
        self.save_manifest()
        with self.assertRaisesRegex(RuntimeError,'identity'):
            r.verify_package(self.source)

    def test_scope_rejected(self):
        self.manifest['files']['backend/secret.py'] = 'f'*64
        self.save_manifest()
        with self.assertRaisesRegex(RuntimeError,'path'):
            r.verify_package(self.source)

    def test_unmanifested_file_rejected(self):
        self.write(self.source/'unexpected.db',b'data')
        with self.assertRaisesRegex(RuntimeError,'Unmanifested'):
            r.verify_package(self.source)

    def test_tampered_file_rejected(self):
        (self.source/'frontend/dist/assets/new-hash.js').write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'checksum'):
            r.verify_package(self.source)

    def test_missing_entry_asset(self):
        files = dict(self.files)
        del files['frontend/dist/assets/new-hash.js']
        with self.assertRaisesRegex(RuntimeError,'entry asset'):
            r.verify_frontend(files)

    def test_stale_gzip_rejected(self):
        with self.assertRaisesRegex(RuntimeError,'Compressed'):
            r.verify_frontend({**self.files,'frontend/dist/index.html.gz':gzip.compress(b'old')})

    def test_wrong_frontend_baseline_preserves_install(self):
        (self.app/'frontend/package.json').write_text('{"version":"0.2.60"}')
        with self.assertRaisesRegex(RuntimeError,'baseline'):
            d.switch(self.source,self.app,self.backup)
        self.assertFalse(self.backup.exists())

    def test_asset_collision_preserves_install(self):
        self.write(self.app/'frontend/dist/assets/new-hash.js',b'collision')
        with self.assertRaisesRegex(RuntimeError,'collision'):
            d.switch(self.source,self.app,self.backup)
        self.assert_original()
        self.assertFalse(self.backup.exists())

    def test_real_install_rollback_retains_both_asset_generations(self):
        d.switch(self.source,self.app,self.backup)
        for name in self.files:
            if name.startswith('frontend/'):
                self.assertEqual((self.app/name).read_bytes(),self.files[name])
        d.rollback(self.app,self.backup)
        self.assert_original()
        self.assertEqual((self.app/'frontend/dist/assets/old-hash.js').read_bytes(),b'old frontend')
        self.assertEqual((self.app/'frontend/dist/assets/new-hash.js').read_bytes(),b'new frontend')

    def test_online_failure_automatically_restores_old_entries(self):
        with patch.object(r,'baseline',return_value={'image':'same'}), \
             patch.object(r,'installed',side_effect=RuntimeError('HTTP mismatch')):
            with self.assertRaisesRegex(RuntimeError,'HTTP'):
                d.deploy(self.source,self.app,self.backup)
        self.assert_original()

    def test_service_restart_automatically_restores_old_entries(self):
        with patch.object(r,'baseline',side_effect=[{'pid':1},{'pid':2}]), \
             patch.object(r,'installed',return_value={'status':'ok'}):
            with self.assertRaisesRegex(RuntimeError,'changed'):
                d.deploy(self.source,self.app,self.backup)
        self.assert_original()

    def test_partial_switch_can_rollback(self):
        original = d.atomic_copy
        failed = False
        def interrupted(source,target):
            nonlocal failed
            if target == self.app/'frontend/package.json' and not failed:
                failed = True
                raise OSError('simulated write failure')
            return original(source,target)
        with patch.object(r,'baseline',return_value={}),patch.object(d,'atomic_copy',side_effect=interrupted):
            with self.assertRaisesRegex(OSError,'simulated'):
                d.deploy(self.source,self.app,self.backup)
        self.assert_original()

    def test_rollback_refuses_later_deployment(self):
        d.switch(self.source,self.app,self.backup)
        (self.app/'frontend/dist/index.html').write_bytes(b'later release')
        with self.assertRaisesRegex(RuntimeError,'changed'):
            d.rollback(self.app,self.backup)

    def test_internal_replace_failure_cleans_owned_temp_and_allows_retry(self):
        replace = d.os.replace
        failed = False
        def interrupted(source, target):
            nonlocal failed
            if target == self.app/'frontend/package.json' and not failed:
                failed = True
                raise OSError('one replace failure')
            return replace(source, target)
        with patch.object(r,'baseline',return_value={}),patch.object(d.os,'replace',side_effect=interrupted):
            with self.assertRaisesRegex(OSError,'one replace failure'):
                d.deploy(self.source,self.app,self.backup)
        self.assertTrue(failed)
        self.assert_original()
        self.assertEqual(list(self.app.rglob('*.archive-new')), [])
        retry_backup = self.root/'retry-backup'
        d.switch(self.source,self.app,retry_backup)
        d.rollback(self.app,retry_backup)
        self.assert_original()

    def test_atomic_copy_preserves_temp_it_did_not_create(self):
        destination = self.app/'frontend/package.json'
        temporary = destination.with_name(destination.name+'.archive-new')
        temporary.write_bytes(b'other operation')
        with self.assertRaises(FileExistsError):
            d.atomic_copy(self.source/'frontend/package.json',destination)
        self.assertEqual(temporary.read_bytes(),b'other operation')
        self.assert_original()

    def test_copy_read_failure_after_temp_creation_can_retry(self):
        source = self.source/'frontend/package.json'
        destination = self.app/'frontend/package.json'
        with patch.object(Path,'read_bytes',side_effect=OSError('source read failure')):
            with self.assertRaisesRegex(OSError,'source read failure'):
                d.atomic_copy(source,destination)
        self.assert_original()
        self.assertFalse(destination.with_name(destination.name+'.archive-new').exists())
        d.atomic_copy(source,destination)
        self.assertEqual(source.read_bytes(),destination.read_bytes())

    def test_rollback_refuses_corrupt_backup(self):
        d.switch(self.source,self.app,self.backup)
        (self.backup/'frontend/dist/index.html').write_bytes(b'corrupt')
        with self.assertRaisesRegex(RuntimeError,'backup drift'):
            d.rollback(self.app,self.backup)

    def test_privacy_scans_real_helpers(self):
        common = r.helper('package-delivery')
        for name in r.HELPERS:
            common.privacy_check(name,(HERE/(name+'.py')).read_bytes())


if __name__ == '__main__':
    unittest.main()
