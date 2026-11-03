"""SKU release boundaries: credential isolation, complete package, additive migration."""
import base64
import importlib.util
import json
from pathlib import Path
import stat
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name+'.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


r, b, p, db, e = map(load, ('sku-runtime', 'sku-baseline', 'sku-package', 'sku-database', 'sku-environment'))


class ContractTests(unittest.TestCase):
    def test_readonly_probe_and_package_pin_identical_scope(self):
        self.assertEqual(b.FILES, r.FILES)
        self.assertEqual(b.NATIVE_FILES, r.NATIVE_FILES)
        self.assertEqual(b.UNITS, r.UNITS)

    def test_all_current_draft_sources_and_tests_are_in_release(self):
        backend = Path(__file__).resolve().parents[2]/'hengxin-smart-image/backend'
        actual = {path.relative_to(backend).as_posix() for path in (backend/'app/overseas/drafts').glob('*.py')}
        self.assertEqual(actual, {n for n in r.FILES if '/drafts/' in n})
        tests = {path.name for pattern in ('test_overseas_draft*.py', 'test_overseas_sku*.py')
                 for path in (backend/'tests').glob(pattern)}
        self.assertLessEqual(tests, set(r.TESTS))

    def test_native_manifest_records_native_bytes_independently(self):
        value = {'nativeSources': {u: {n: base64.b64encode(u.encode()).decode() for n in r.NATIVE_FILES}
                                   for u in r.UNITS},
                 'units': {u: {'WorkingDirectory': '/'+u} for u in r.UNITS}}
        result = p.native_manifest(value)
        self.assertNotEqual(result['units'][r.UNITS[0]], result['units'][r.UNITS[1]])
        value['units'][r.UNITS[1]]['WorkingDirectory'] = '/'+r.UNITS[0]
        with self.assertRaisesRegex(RuntimeError, 'Shared native baseline'):
            p.native_manifest(value)

    def test_dependency_fixture_closure_is_transitive_and_cycle_safe(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            sources = {'conftest.py': 'import helper', 'test_one.py': 'from helper import value',
                       'helper.py': 'import other', 'other.py': 'import helper'}
            for name, raw in sources.items():
                (root/name).write_text(raw)
            with patch.object(p.r, 'TESTS', ('test_one.py',)):
                result = p.collect_tests(root, lambda name: (root/name).read_bytes())
            self.assertEqual(set(result), {'tests/'+n for n in sources})

    def test_real_installed_test_fixture_closure(self):
        root = Path(__file__).resolve().parents[2]/'hengxin-smart-image/backend/tests'
        result = p.collect_tests(root, lambda name: (root/name).read_bytes())
        self.assertTrue(all('tests/'+n in result for n in r.TESTS))
        self.assertIn('tests/test_overseas_members_postgres.py', result)

    def test_only_authorized_secret_can_change_existing_environment(self):
        before = ['OVERSEAS_DATABASE_URL=database', 'OVERSEAS_WORKFLOW_COLLABORATOR_MEMBER_IDS=a,b',
                  'HX_BUSINESS_CONTEXT=overseas', 'PATH=/bin']
        after = e.expected_environment(before, 'synthetic-token')
        self.assertEqual(after[:-1], before)
        self.assertEqual(after[-1], e.KEY+'=synthetic-token')
        self.assertEqual(e.overlay('new-image', 'synthetic-token'),
                         {'services': {'api': {'image': 'new-image', 'environment': {e.KEY: 'synthetic-token'}}}})
        self.assertNotEqual(r.environment_hash(before), r.environment_hash(after))
        self.assertNotIn('synthetic-token', r.environment_hash(after))

    def test_secret_replacement_cannot_duplicate_environment_key(self):
        result = e.expected_environment(['OVERSEAS_OTHER=retain', e.KEY+'=old'], 'new')
        self.assertEqual(result, ['OVERSEAS_OTHER=retain', e.KEY+'=new'])

    def read_secret(self, raw, mode=0o600, uid=0):
        info = SimpleNamespace(st_mode=stat.S_IFREG | mode, st_uid=uid, st_size=len(raw))
        with patch.object(e.Path, 'is_symlink', return_value=False), \
             patch.object(e.Path, 'stat', return_value=info), patch.object(e.Path, 'read_text', return_value=raw):
            return e.credential(Path.cwd()/'private-secret')

    def test_secret_requires_private_owner_mode_and_single_token(self):
        self.assertEqual(self.read_secret('synthetic-token\n'), 'synthetic-token')
        for raw, mode, uid in [('token', 0o644, 0), ('token', 0o600, 1000),
                               ('first\nsecond', 0o600, 0), ('', 0o600, 0), ('a'*4097, 0o600, 0)]:
            with self.subTest(raw_length=len(raw), mode=mode, uid=uid), self.assertRaises(RuntimeError):
                self.read_secret(raw, mode, uid)

    def test_migration_keeps_every_historical_field_and_table(self):
        before = {'overseas_tasks': ['unchanged'], 'overseas_archives': ['unchanged archive']}
        full = {**before, 'overseas_alembic_version': ['new'], **{n: [] for n in r.NEW_TABLES}}
        with patch.object(r, 'fingerprints', return_value=full):
            self.assertEqual(r.migration_fingerprints(('db',)), before)

    def test_new_tables_must_be_exact_and_empty(self):
        names = '\n'.join(sorted(r.NEW_TABLES))
        with patch.object(r, 'sql', side_effect=[names, '0', '0', '0']):
            r.verify_new_tables(('db',))
        with patch.object(r, 'sql', return_value=names), self.assertRaisesRegex(RuntimeError, 'Unexpected draft'):
            r.verify_new_tables(('db',), before=True)
        with patch.object(r, 'sql', side_effect=[names, '1']), self.assertRaisesRegex(RuntimeError, 'not empty'):
            r.verify_new_tables(('db',))

    def test_migration_rejects_historical_data_and_existing_schema_drift(self):
        with patch.object(db.r, 'sql', return_value=r.REVISION), \
             patch.object(db.r, 'migration_fingerprints', return_value={'old': ['changed']}):
            with self.assertRaisesRegex(RuntimeError, 'Unexpected migration data'):
                db.migrated(('db',), {'old': ['before']}, {}, 'columns')
        with patch.object(db.r, 'sql', return_value=r.REVISION), \
             patch.object(db.r, 'migration_fingerprints', return_value={}), \
             patch.object(db.r, 'columns', return_value='changed'):
            with self.assertRaisesRegex(RuntimeError, 'schema columns changed'):
                db.migrated(('db',), {}, {}, 'original')

    def test_migration_requires_same_new_schema_as_isolated_restoration(self):
        with patch.object(db.r, 'sql', return_value=r.REVISION), \
             patch.object(db.r, 'migration_fingerprints', return_value={}), \
             patch.object(db.r, 'columns', return_value='columns'), \
             patch.object(db.r, 'verify_new_tables'), patch.object(db.r, 'draft_schema', return_value={'wrong': []}):
            with self.assertRaisesRegex(RuntimeError, 'isolated migration'):
                db.migrated(('db',), {}, {'verified': []}, 'columns')


if __name__ == '__main__':
    unittest.main()
