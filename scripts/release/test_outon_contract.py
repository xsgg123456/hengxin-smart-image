"""Release closure and narrow migration exceptions remain explicit."""
import importlib.util
import json
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
        self.assertEqual(b.UNITS,r.UNITS)

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
