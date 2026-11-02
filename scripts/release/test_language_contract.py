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


p = load('language-package')
r = load('language-runtime')
db = load('language-database')
b = load('language-baseline')


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
                 patch.object(b.Path,'read_text',return_value='{"version":"0.2.58"}'):
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
        self.assertTrue(all('tests/'+name in result for name in r.TESTS))

    def test_migration_fingerprints_ignore_only_new_columns(self):
        tables = ['overseas_alembic_version','overseas_tasks','overseas_archives','overseas_members']
        queries = []
        def sql(database, query):
            queries.append(query)
            return '\n'.join(tables) if query.startswith('SELECT tablename') else '[]'
        with patch.object(r, 'sql', side_effect=sql):
            result = r.migration_fingerprints(('test',))
        self.assertEqual(set(result), set(tables)-{'overseas_alembic_version'})
        self.assertIn("to_jsonb(t)-'language'", queries[1])
        self.assertIn("to_jsonb(t)-'task_name'-'language'", queries[2])
        self.assertNotIn("-'",queries[3])
        self.assertTrue(all('updated_at' not in q and 'version+1' not in q for q in queries))

    def test_column_definitions_are_exact_nullable_strings_without_default(self):
        rows = [[table, name, 'character varying', length, 'YES', None]
                for (table,name), length in r.NEW_COLUMNS.items()]
        with patch.object(r, 'sql', return_value=json.dumps(rows)):
            r.verify_new_columns(('test',))
            with self.assertRaisesRegex(RuntimeError,'Unexpected new'):
                r.verify_new_columns(('test',),before=True)
        for index,value in ((2,'text'),(3,81),(4,'NO'),(5,'en')):
            changed = [row[:] for row in rows]
            changed[0][index] = value
            with patch.object(r,'sql',return_value=json.dumps(changed)), self.assertRaisesRegex(RuntimeError,'Unexpected new'):
                r.verify_new_columns(('test',))
        with patch.object(r,'sql',return_value='[]'):
            r.verify_new_columns(('test',),before=True)

    def test_backfill_expected_values_come_from_actual_task_and_keep_unknown_null(self):
        with patch.object(r,'sql',return_value='{"linked":["real task",null],"deleted":[null,null]}') as sql:
            expected = r.language_snapshots(('test',),before=True)
        self.assertEqual(expected['deleted'], [None,None])
        self.assertIn('LEFT JOIN overseas_tasks t ON t.id=a.task_id',sql.call_args.args[1])
        self.assertIn('json_build_array(t.name,NULL)',sql.call_args.args[1])
        with patch.object(r,'sql',return_value='0'),patch.object(r,'language_snapshots',return_value=expected):
            r.verify_languages(('test',),expected)
        with patch.object(r,'sql',return_value='0'),patch.object(r,'language_snapshots',return_value={'linked':['invented',None]}):
            with self.assertRaisesRegex(RuntimeError,'actual task source'):
                r.verify_languages(('test',),expected)
        with patch.object(r,'sql',return_value='1'),self.assertRaisesRegex(RuntimeError,'unknown'):
            r.verify_languages(('test',),expected)

    def test_environment_fingerprint_preserves_grants_without_secrets_or_process_noise(self):
        entries = ['OVERSEAS_DATABASE_URL=private', 'OVERSEAS_WORKFLOW_COLLABORATOR_MEMBER_IDS=member-a,member-b',
                   'HX_BUSINESS_CONTEXT=overseas', 'INVOCATION_ID=old', 'PATH=/bin']
        actual = r.environment_hash(entries)
        self.assertEqual(len(actual),64)
        self.assertEqual(actual,r.environment_hash(list(reversed(entries))))
        self.assertEqual(actual,r.environment_hash(entries[:-2]+['INVOCATION_ID=new','PATH=/usr/bin']))
        self.assertNotEqual(actual,r.environment_hash([entry.replace('member-b','member-c') for entry in entries]))
        self.assertNotIn('private',actual)

    def test_worker_probe_disables_bytecode_and_keeps_actual_environment(self):
        with patch.object(r.a,'worker',return_value={'pid':12,'cwd':'/native'}), \
             patch.object(r.Path,'read_bytes',return_value=b'OVERSEAS_DATABASE_URL=private\0'), \
             patch.object(r,'run',return_value='{"node":"existing"}') as run:
            self.assertEqual(r.worker_probe('overseas','verify',Path('/work')),{'node':'existing'})
        self.assertEqual(run.call_args.args[:2],('/native/.venv/bin/python','-B'))
        self.assertEqual(run.call_args.kwargs['env']['OVERSEAS_DATABASE_URL'],'private')
        with self.assertRaisesRegex(RuntimeError,'Only overseas'):
            r.worker_probe('domestic','verify',Path('/work'))

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
