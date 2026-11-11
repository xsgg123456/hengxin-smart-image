"""Real PostgreSQL regression for narrowly replacing pristine migration Skill seeds."""
import copy
import json
import os
import unittest

import data_copy as dc
import data_copy_test as fixtures

TABLE = 'overseas_installed_skill_availability'


@unittest.skipUnless(os.environ.get('DATA_COPY_PG_TEST') == '1', 'opt-in disposable PostgreSQL')
class AvailabilitySeedTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.PostgreSQLTests.setUpClass.__func__)
    cleanup = classmethod(fixtures.PostgreSQLTests.cleanup.__func__)
    setUp = fixtures.PostgreSQLTests.setUp
    reset = fixtures.PostgreSQLTests.reset
    query = fixtures.PostgreSQLTests.query
    snapshot = fixtures.PostgreSQLTests.snapshot

    def insert_rows(self, rows):
        self.query(f'INSERT INTO {TABLE}(id,enabled,version,platforms,created_at,updated_at) '
                   'SELECT id,enabled,version,platforms,transaction_timestamp(),transaction_timestamp() '
                   f'FROM jsonb_populate_recordset(NULL::{TABLE},' + dc.literal(json.dumps(rows)) + '::jsonb);')

    def source24(self):
        rows = copy.deepcopy(dc.policy.INSTALLED_SKILL_SEEDS)
        for row in rows:
            row.update(version=3, enabled=not row['enabled'], platforms=['Walmart'])
        rows += [dict(id=f'new-approved-skill-{i}', enabled=True, version=2, platforms=['Amazon']) for i in range(9)]
        self.insert_rows(rows)
        raw = self.snapshot()
        self.reset()
        return raw

    def test_exact_seed15_replaced_by_source24(self):
        raw = self.source24()
        self.insert_rows(dc.policy.INSTALLED_SKILL_SEEDS)
        self.query(dc.target_sql(fixtures.DB, raw))
        data = json.loads(self.snapshot())['tables'][TABLE]
        self.assertEqual(data['count'], 24)
        self.assertEqual(data, json.loads(raw)['tables'][TABLE])

    def test_modified_partial_extra_and_stale_seeds_rejected(self):
        raw = self.source24()
        changes = ["UPDATE " + TABLE + " SET enabled=NOT enabled WHERE id='amazon-new-product-aplus';",
                   'UPDATE ' + TABLE + ' SET version=2;',
                   'UPDATE ' + TABLE + " SET platforms='[]';",
                   'DELETE FROM ' + TABLE + " WHERE id='amazon-new-product-aplus';",
                   'UPDATE ' + TABLE + " SET created_at=transaction_timestamp()-INTERVAL '2 days';",
                   'UPDATE ' + TABLE + ' SET updated_at=NULL;',
                   'INSERT INTO ' + TABLE + "(id,enabled,version,platforms) VALUES('extra',false,1,'[]');"]
        for change in changes:
            with self.subTest(change=change):
                self.reset()
                self.insert_rows(dc.policy.INSTALLED_SKILL_SEEDS)
                self.query(change)
                before = self.query('SELECT ' + '(' + dc.rows_query(fixtures.DB, TABLE, False) + ')')
                with self.assertRaisesRegex(RuntimeError, 'target not empty: ' + TABLE):
                    self.query(dc.target_sql(fixtures.DB, raw))
                self.assertEqual(self.query('SELECT (' + dc.rows_query(fixtures.DB, TABLE, False) + ')'), before)

    def test_digest_failure_restores_all_15_original_seed_rows(self):
        payload = json.loads(self.source24())
        payload['tables'][TABLE]['sha256'] = '0' * 64
        self.insert_rows(dc.policy.INSTALLED_SKILL_SEEDS)
        before = self.query('SELECT (' + dc.rows_query(fixtures.DB, TABLE, False) + ')')
        with self.assertRaises(RuntimeError):
            self.query(dc.target_sql(fixtures.DB, json.dumps(payload)))
        self.assertEqual(self.query('SELECT count(*) FROM ' + TABLE), '15')
        self.assertEqual(self.query('SELECT (' + dc.rows_query(fixtures.DB, TABLE, False) + ')'), before)


if __name__ == '__main__':
    unittest.main()
