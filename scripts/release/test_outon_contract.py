"""Release closure and narrow migration exceptions remain explicit."""
import importlib.util
import json
import base64
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(name,Path(__file__).with_name(name+'.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


p = load('outon-package')
r = load('outon-runtime')
db = load('outon-database')
b = load('outon-baseline')


class ContractTests(unittest.TestCase):
    def test_probe_and_runtime_share_exact_closed_files(self):
        self.assertEqual(b.FILES,r.FILES)
        self.assertEqual(b.NATIVE_FILES,r.NATIVE_FILES)
        self.assertEqual(b.UNITS,r.UNITS)

    def native_fixture(self):
        return {'nativeSources':{unit:{name:base64.b64encode(b'old native').decode() for name in r.NATIVE_FILES}
                                 for unit in r.UNITS},
                'units':{unit:{'WorkingDirectory':'/native'} for unit in r.UNITS}}

    def test_native_manifest_pins_each_unit_without_embedding_private_sources(self):
        baseline = self.native_fixture()
        name = sorted(r.NATIVE_FILES)[0]
        for unit in r.UNITS:
            baseline['nativeSources'][unit][name] = None
        native = p.native_manifest(baseline)
        for unit in r.UNITS:
            self.assertIsNone(native['units'][unit]['files'][name])
            self.assertTrue(all(value in (None,hashlib.sha256(b'old native').hexdigest())
                                for value in native['units'][unit]['files'].values()))
        self.assertNotIn('old native',json.dumps(native))

    def test_native_manifest_requires_every_unit_and_exact_scope(self):
        baseline = self.native_fixture()
        del baseline['nativeSources'][r.UNITS[0]]
        with self.assertRaisesRegex(RuntimeError,'baselines missing'):
            p.native_manifest(baseline)
        baseline = self.native_fixture()
        baseline['nativeSources'][r.UNITS[0]]['app/overseas/unrelated.py'] = None
        with self.assertRaisesRegex(RuntimeError,'source scope'):
            p.native_manifest(baseline)

    def test_native_manifest_rejects_shared_root_disagreement(self):
        baseline = self.native_fixture()
        baseline['nativeSources'][r.UNITS[1]][sorted(r.NATIVE_FILES)[0]] = None
        with self.assertRaisesRegex(RuntimeError,'Shared native baseline conflict'):
            p.native_manifest(baseline)
        baseline['units'][r.UNITS[1]]['WorkingDirectory'] = '/other'
        p.native_manifest(baseline)

    def snapshot_fixture(self, root, *, active=True, changed=False):
        calls = {}
        name = sorted(b.NATIVE_FILES)[0]
        path = root/name
        path.parent.mkdir(parents=True)
        path.write_bytes(b'actual native source')
        def run(*args):
            if args[:2] == ('docker','exec'):
                return json.dumps({n:None for n in b.FILES})
            if args[:2] == ('docker','inspect'):
                return 'image'
            unit,key = args[2],args[4]
            if key == 'MainPID':
                calls[unit] = calls.get(unit,0)+1
                return '0' if not active else '11' if changed and calls[unit]>1 else '10'
            return str(root) if key == 'WorkingDirectory' else 'value'
        return name,run

    def test_snapshot_captures_each_live_native_source_and_explicit_absence(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            name,run = self.snapshot_fixture(root)
            with patch.object(b,'run',side_effect=run),patch.object(b.os,'readlink',return_value=str(root)), \
                 patch.object(b.Path,'read_text',return_value='{"version":"0.2.57"}'):
                result = b.snapshot()
            self.assertEqual(set(result['nativeSources']),set(r.UNITS))
            for files in result['nativeSources'].values():
                self.assertEqual(set(files),r.NATIVE_FILES)
                self.assertEqual(base64.b64decode(files[name]),b'actual native source')
                self.assertTrue(all(value is None for key,value in files.items() if key != name))

    def test_snapshot_rejects_inactive_unit(self):
        with tempfile.TemporaryDirectory() as folder:
            _,run = self.snapshot_fixture(Path(folder),active=False)
            with patch.object(b,'run',side_effect=run),self.assertRaisesRegex(RuntimeError,'not running'):
                b.snapshot()

    def test_snapshot_rejects_actual_process_directory_mismatch(self):
        with tempfile.TemporaryDirectory() as folder:
            _,run = self.snapshot_fixture(Path(folder))
            with patch.object(b,'run',side_effect=run),patch.object(b.os,'readlink',return_value='different'), \
                 self.assertRaisesRegex(RuntimeError,'working directory differs'):
                b.snapshot()

    def test_snapshot_rejects_process_change_during_capture(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            _,run = self.snapshot_fixture(root,changed=True)
            with patch.object(b,'run',side_effect=run),patch.object(b.os,'readlink',return_value=str(root)), \
                 self.assertRaisesRegex(RuntimeError,'process changed'):
                b.snapshot()

    def test_test_source_closure_includes_transitive_helpers_and_terminates_cycles(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            contents = {'conftest.py':'import first', 'test_x.py':'from first import fixture',
                        'first.py':'import second', 'second.py':'import first\nimport os'}
            for name,value in contents.items():
                (root/name).write_text(value)
            with patch.object(p.r,'TESTS',('test_x.py',)):
                result = p.collect_tests(root,lambda name:(root/name).read_bytes())
            self.assertEqual(set(result),{'tests/'+name for name in contents})

    def test_real_installed_test_closure_contains_pg_migration_fixture(self):
        directory = Path(__file__).resolve().parents[2]/'hengxin-smart-image/backend/tests'
        result = p.collect_tests(directory,lambda name:(directory/name).read_bytes())
        self.assertIn('tests/test_overseas_database.py',result)
        self.assertIn('tests/test_overseas_members_postgres.py',result)
        self.assertIn('tests/overseas_installed_helpers.py',result)
        self.assertTrue(all('tests/'+name in result for name in r.TESTS))

    def test_migration_fingerprints_limit_exceptions_to_affected_members(self):
        affected = ['12345678-1234-1234-1234-123456789abc']
        tables = ['overseas_alembic_version','overseas_members','overseas_member_roles','overseas_tasks']
        calls = []
        def sql(database,query):
            calls.append(query)
            return '\n'.join(tables) if query.startswith('SELECT tablename') else '[]'
        with patch.object(r,'sql',side_effect=sql):
            result = r.migration_fingerprints(('test',),affected,before=True)
        self.assertNotIn('overseas_alembic_version',result)
        self.assertIn('version+1',calls[1])
        self.assertIn(affected[0],calls[1])
        self.assertIn('ELSE to_jsonb(t)',calls[1])
        self.assertIn("THEN 'design_manager'",calls[2])
        self.assertNotIn('updated_at',calls[3])
        self.assertNotIn('version+1',calls[3])
        with patch.object(r,'sql',side_effect=sql):
            r.migration_fingerprints(('test',),affected)
        self.assertNotIn('version+1',calls[5])

    def test_migration_fingerprint_rejects_sql_in_member_identifier(self):
        with patch.object(r,'sql') as sql, self.assertRaisesRegex(RuntimeError,'Invalid affected'):
            r.migration_fingerprints(('test',),["x'); DROP TABLE overseas_tasks;"])
        sql.assert_not_called()

    def test_unexpected_data_or_columns_prevent_migration_verification(self):
        with patch.object(db.r,'sql',return_value=r.REVISION), \
             patch.object(db.r,'migration_fingerprints',return_value={'tasks':['changed']}):
            with self.assertRaisesRegex(RuntimeError,'Unexpected migration data'):
                db.migrated(('test',),{'tasks':['original']},[],'columns')
        with patch.object(db.r,'sql',return_value=r.REVISION), \
             patch.object(db.r,'migration_fingerprints',return_value={}), \
             patch.object(db.r,'columns',return_value='changed'):
            with self.assertRaisesRegex(RuntimeError,'columns changed'):
                db.migrated(('test',),{},[],'original')


if __name__ == '__main__':
    unittest.main()
