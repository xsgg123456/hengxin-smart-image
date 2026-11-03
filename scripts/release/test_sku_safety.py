"""Boundary tests: exact package, restore evidence, and pre-switch rejection."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


r = load('sku-runtime')
d = load('sku-deploy')
db = load('sku-database')


class SafetyTests(unittest.TestCase):
    def package(self, root):
        paths = {'api/'+n for n in r.FILES} | {'tests/'+n for n in ('conftest.py', *r.TESTS)} | {
            'frontend/package.json', 'frontend/dist/index.html'} | {'scripts/release/'+n+'.py' for n in r.HELPERS}
        for name in paths:
            path = root/name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"version":"0.2.60"}' if name.endswith('package.json') else 'content')
        files = {n:r.digest(root/n) for n in paths}
        manifest = {'release':'sku-20261102-test', 'version':r.VERSION,
                    'commit':'a'*40, 'candidateId':'b'*64,
                    'native':{'units':{unit:{'files':{n:'b'*64 for n in r.NATIVE_FILES}} for unit in r.UNITS}},
                    'api':{'image':r.BASE_IMAGE, 'files':{
                        n:{'baseline':'a'*64, 'sha256':files['api/'+n]} for n in r.FILES}}, 'files':files}
        (root/'release.json').write_text(json.dumps(manifest))
        return manifest

    def test_package_rejects_extra_unhashed_content_and_patch_hash_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = self.package(root)
            self.assertEqual(r.verify_package(root), manifest)
            (root/'extra.py').write_text('unexpected')
            with self.assertRaisesRegex(RuntimeError, 'Unmanifested'):
                r.verify_package(root)
            (root/'extra.py').unlink()
            manifest['api']['files']['app/overseas/tasks/schemas.py']['sha256'] = 'b'*64
            (root/'release.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError, 'Patch checksum'):
                r.verify_package(root)

    def test_package_requires_review_identity_and_exact_helper_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = self.package(root)
            del manifest['candidateId']
            (root/'release.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError,'reviewed commit'):
                r.verify_package(root)
            manifest = self.package(root)
            path = root/'scripts/release/unrelated.py'
            path.write_text('content')
            manifest['files']['scripts/release/unrelated.py'] = r.digest(path)
            (root/'release.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError,'helper scope'):
                r.verify_package(root)

    def test_native_manifest_rejects_missing_unit_extra_file_and_malformed_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for corruption in ('unit','file','hash'):
                manifest = self.package(root)
                units = manifest['native']['units']
                if corruption == 'unit':
                    del units[r.UNITS[0]]
                elif corruption == 'file':
                    units[r.UNITS[0]]['files']['app/unrelated.py'] = None
                else:
                    units[r.UNITS[0]]['files'][sorted(r.NATIVE_FILES)[0]] = 'unknown'
                (root/'release.json').write_text(json.dumps(manifest))
                with self.assertRaisesRegex(RuntimeError,'native baseline'):
                    r.verify_package(root)

    def test_prepared_native_baseline_must_remain_bound_to_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            work = Path(folder)
            source = work/'source'
            manifest = self.package(source)
            data = {'source':str(source), 'manifest':r.digest(source/'release.json'),
                    'native':manifest['native'], 'patch':manifest['api']['files']}
            data['native']['units'][r.UNITS[0]]['files'][sorted(r.NATIVE_FILES)[0]] = 'c'*64
            (work/'prepared.json').write_text(json.dumps(data))
            with patch.object(d.r,'hashes') as hashes, self.assertRaisesRegex(RuntimeError,'Prepared source baseline drift'):
                d.state(work)
            hashes.assert_not_called()

    def test_package_rejects_parent_traversal_even_with_correct_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)/'package'
            root.mkdir()
            manifest = self.package(root)
            outside = root.parent/'outside'
            outside.write_text('content')
            manifest['files']['../outside'] = r.digest(outside)
            (root/'release.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError, 'Unsafe package'):
                r.verify_package(root)

    def test_package_requires_measured_image_and_all_three_installed_tests(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = self.package(root)
            manifest['api']['image'] = 'sha256:other'
            (root/'release.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError, 'baseline'):
                r.verify_package(root)
            manifest['api']['image'] = r.BASE_IMAGE
            del manifest['files']['tests/test_overseas_materials.py']
            (root/'release.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError, 'Incomplete'):
                r.verify_package(root)

    def test_new_migration_accepts_null_baseline_but_requires_new_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            manifest = self.package(root)
            name = 'migrations/overseas/versions/0026_requirement_drafts.py'
            manifest['api']['files'][name]['baseline'] = None
            (root/'release.json').write_text(json.dumps(manifest))
            self.assertEqual(r.verify_package(root),manifest)
            manifest['api']['files'][name]['sha256'] = 'bad'
            (root/'release.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(RuntimeError,'Patch checksum'):
                r.verify_package(root)

    def test_live_api_prevents_backup_and_worker_pause(self):
        with patch.object(db.r, 'inspect', return_value={'Id':'old', 'State':{'Running':True}}), \
             patch.object(db.r, 'worker') as worker, patch.object(db.subprocess, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'stopped'):
                db.backup(Path('unused'), {'oldId':'old'})
            worker.assert_not_called()
            run.assert_not_called()

    def test_missing_restore_evidence_prevents_api_switch(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            database = SimpleNamespace(closed_gate=lambda *args: None,
                                       backup_verified=lambda *args: (_ for _ in ()).throw(RuntimeError('restore absent')))
            with patch.object(d, 'state', return_value=({}, None)), \
                 patch.object(d.r, 'helper', return_value=database), patch.object(d.r.a, 'compose') as compose:
                with self.assertRaisesRegex(RuntimeError, 'Verified migration and native'):
                    d.api(root)
                compose.assert_not_called()
            self.assertFalse((root/'API_SWITCH_STARTED').exists())

    def test_installed_tests_use_image_with_isolated_postgres_and_required_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            data = {'manifest':'abc', 'image':'release-image'}
            def run(*args, **kwargs):
                return '[{"Image":"postgres-image"}]' if args[:2] == ('docker','inspect') else ''
            with patch.object(d, 'state', return_value=(data, root)), \
                 patch.object(d.r, 'run', side_effect=run) as host, \
                 patch.object(d, 'installed_pytest', return_value='48 passed') as pytest:
                d.test(root)
            host.assert_any_call('docker', 'exec', 'hx-sku-tests-abc', 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres', timeout=4)
            host.assert_any_call('docker', 'exec', 'hx-sku-tests-abc', 'createdb', '-h', '127.0.0.1', '-U', 'postgres', 'sku_test')
            command = pytest.call_args.args[0]
            self.assertIn('release-image', command)
            self.assertIn('container:hx-sku-tests-abc', command)
            self.assertIn('--read-only', command)
            self.assertTrue(all('/app/tests/'+name in command for name in r.TESTS))
            mounts = [value for value in command if value.startswith('type=bind')]
            self.assertEqual(mounts, ['type=bind,src='+str(root/'tests')+',dst=/app/tests,readonly'])
            self.assertIn('TEST_OVERSEAS_DATABASE_URL=postgresql+psycopg://postgres@127.0.0.1/sku_test', command)
            self.assertEqual(host.call_args.args, ('docker','rm','-f','-v','hx-sku-tests-abc'))
            self.assertEqual(json.loads((root/'INSTALL_TESTS_PASSED').read_text()), data)

    def test_failed_installed_tests_cleanup_without_passing_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'INSTALL_TESTS_PASSED').write_text('stale earlier success')
            with patch.object(d, 'state', return_value=({'manifest':'abc', 'image':'new'}, root)), \
                 patch.object(d.r, 'run', return_value='[{"Image":"pg"}]') as run, \
                 patch.object(d, 'installed_pytest', side_effect=RuntimeError('tests failed')):
                with self.assertRaisesRegex(RuntimeError, 'tests failed'):
                    d.test(root)
            self.assertEqual(run.call_args.args, ('docker','rm','-f','-v','hx-sku-tests-abc'))
            self.assertFalse((root/'INSTALL_TESTS_PASSED').exists())

    def test_restore_uses_separate_database_and_cleans_it_on_failure(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dump = root/'dump'
            dump.write_bytes(b'private dump')
            calls = []
            def run(*args, **kwargs):
                calls.append(args)
                return '[{"Image":"postgres-image"}]' if args[:2] == ('docker', 'inspect') else ''
            with patch.object(db.r, 'run', side_effect=run), \
                 patch.object(db.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1)), \
                 patch.object(db.r, 'fingerprints') as fingerprints:
                with self.assertRaisesRegex(RuntimeError, 'Isolated restore failed'):
                    db.restore_test(root, {'manifest':'abc', 'image':'new'}, dump, {}, 'columns')
                fingerprints.assert_not_called()
            create = next(args for args in calls if args[:2] == ('docker', 'run'))
            self.assertEqual(create[create.index('--network')+1], 'none')
            self.assertEqual(calls[-1], ('docker','rm','-f','-v','hx-sku-restore-abc'))
            self.assertFalse((root/'restore-proof.json').exists())

    def test_successful_restore_proves_migration_twice_in_same_name_database(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            dump = root/'dump'
            dump.write_bytes(b'private dump')
            with patch.object(db.r, 'run', return_value='[{"Image":"postgres-image"}]') as run, \
                 patch.object(db.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)), \
                 patch.object(db.r, 'fingerprints', return_value={'jobs':['hash']}) as fingerprints, \
                 patch.object(db.r, 'columns', return_value='columns'), \
                 patch.object(db.r, 'sql', return_value=r.OLD_REVISION), \
                 patch.object(db.r,'verify_new_tables'), patch.object(db.r,'draft_schema',return_value={}), \
                 patch.object(db,'migrated'), \
                 patch.object(db.r,'migration_fingerprints',return_value={'jobs':['hash']}):
                db.restore_test(root, {'manifest':'abc', 'image':'new'}, dump, {'jobs':['hash']}, 'columns')
            self.assertEqual(fingerprints.call_count,3)
            run.assert_any_call('docker', 'exec', 'hx-sku-restore-abc', 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres', timeout=4)
            run.assert_any_call('docker', 'exec', 'hx-sku-restore-abc', 'createdb', '-h', '127.0.0.1', '-U', 'postgres', db.r.DB[2])
            migrations = [call for call in run.call_args_list if 'alembic' in call.args]
            self.assertEqual(len(migrations),2)
            self.assertTrue(all('container:hx-sku-restore-abc' in call.args for call in migrations))
            self.assertTrue(json.loads((root/'restore-proof.json').read_text())['restored'])

    def test_row_or_dump_drift_rejects_backup_proof(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root/'backup').mkdir()
            dump = root/'backup/overseas.dump'
            dump.write_bytes(b'dump')
            data = {'manifest':'m', 'image':'new'}
            r.private(root/'draft-schema.json', {})
            r.private(root/'restore-proof.json', {**data, 'dumpSha256':r.digest(dump), 'restored':True,
                                                'draftSchemaSha256':r.digest(root/'draft-schema.json'),
                                                'migration':r.REVISION,'repeatStable':True})
            r.private(root/'backup/COMPLETE', {'manifest':'m', 'dumpSha256':r.digest(dump)})
            r.private(root/'backup/fingerprints.json', {'tasks':['old']})
            with patch.object(db.r, 'fingerprints', return_value={'tasks':['changed']}):
                with self.assertRaisesRegex(RuntimeError, 'changed since backup'):
                    db.backup_verified(root, data)
            dump.write_bytes(b'changed dump')
            with self.assertRaisesRegex(RuntimeError, 'Restore proof mismatch'):
                db.backup_verified(root, data)


if __name__ == '__main__':
    unittest.main()
