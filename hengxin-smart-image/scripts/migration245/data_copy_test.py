"""stdlib tests; DATA_COPY_PG_TEST=1 enables an owned disposable PostgreSQL 16.
No published ports, network access, existing containers or source data are used.
The fixture exercises SQL guards/transactions; full Alembic deployment is separate.
"""
import json
import os
import subprocess
import time
import unittest
import uuid
from unittest.mock import patch

import data_copy as dc

DB = 'hengxin_overseas'
MEMBER = '00000000-0000-0000-0000-000000000001'


def sample(table, **values):
    row = {c: None for c in dc.SCHEMA[DB][table]}
    row.update(values)
    return row


def empty_payload():
    return dict(format=1, database=DB, migration_version=dc.VERSIONS[DB][1],
                audit_policy=dc.policy.POLICY, audit_transformations=dict(reclaim_rows=0, before={}, after={}), tables={
        t: dict(rows=[], count=0, sha256='0' * 64) for t in dc.SCHEMA[DB]})


class UnitTests(unittest.TestCase):
    def test_wrong_target_refused_before_subprocess(self):
        for container, confirmation in [('old-postgres', 'old-postgres/' + DB),
                                        ('hengxin-lan-db', None),
                                        ('hengxin-lan-db', 'hengxin-lan-db/hengxin'),
                                        ('107.172.161.139', None), ('-evil', None)]:
            with self.assertRaises(ValueError):
                dc.command(container, DB, 'postgres', True, confirmation)
        cmd = dc.command('hengxin-lan-db', DB, 'postgres', True, 'hengxin-lan-db/' + DB)
        self.assertEqual(cmd[1:3], ['--host', 'unix:///var/run/docker.sock'])
        self.assertIn('/var/run/postgresql', cmd)

    def test_audit_policy_rejects_business_or_unknown_payload(self):
        for action, before in [('studio.delete', {}), ('skill.update', {'prompt': 'secret'}),
                               ('skill.update', {'release': {'task': 'secret'}}),
                               ('skill.update', {'release': 'historical task body'})]:
            payload = empty_payload()
            row = sample('overseas_management_audit', action=action, before=before, after={})
            payload['tables']['overseas_management_audit'].update(rows=[row], count=1)
            with self.assertRaises(ValueError):
                dc.validate(json.dumps(payload), DB)

    def test_sql_values_are_hex_encoded(self):
        evil = "'); COMMIT;\\n\\! echo secret; --"
        self.assertNotIn(evil, dc.literal(evil))
        self.assertIn(evil.encode().hex(), dc.literal(evil))

    def test_errors_do_not_leak_records(self):
        result = subprocess.CompletedProcess([], 1, '', 'ERROR: secret customer record')
        with patch.object(dc.subprocess, 'run', return_value=result):
            with self.assertRaisesRegex(RuntimeError, 'details withheld') as raised:
                dc.run([], '')
        self.assertNotIn('secret customer', str(raised.exception))


@unittest.skipUnless(os.environ.get('DATA_COPY_PG_TEST') == '1', 'opt-in disposable PostgreSQL')
class PostgreSQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.name = 'hengxin-lan-copy-test-' + uuid.uuid4().hex[:12]
        host = 'npipe:////./pipe/docker_engine' if os.name == 'nt' else 'unix:///var/run/docker.sock'
        cls.docker = ['docker', '--host', host]
        result = subprocess.run(cls.docker + ['run', '-d', '--name', cls.name, '--network', 'none',
            '--tmpfs', '/var/lib/postgresql/data', '-e', 'POSTGRES_HOST_AUTH_METHOD=trust',
            '-e', 'POSTGRES_DB=' + DB, 'postgres:16'], capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise RuntimeError('isolated PostgreSQL container could not start')
        cls.addClassCleanup(cls.cleanup)
        cls.cmd = dc.command(cls.name, DB, 'postgres', True, cls.name + '/' + DB)
        cls.cmd[2] = host  # Windows-only test transport adapter; production stays Unix-only.
        for _ in range(60):
            ready = subprocess.run(cls.docker + ['exec', cls.name, 'pg_isready', '-h', '127.0.0.1', '-U', 'postgres'],
                                   capture_output=True, timeout=10)
            if ready.returncode == 0:
                return
            time.sleep(.25)
        raise RuntimeError('isolated PostgreSQL readiness timeout')

    @classmethod
    def cleanup(cls):
        subprocess.run(cls.docker + ['rm', '-fv', cls.name], capture_output=True, timeout=30, check=True)

    def query(self, sql):
        return dc.run(self.cmd, sql)

    def setUp(self):
        self.reset()

    def reset(self, db=DB):
        sql = 'DROP SCHEMA public CASCADE; CREATE SCHEMA public;\n'
        for table in dc.ALL_TABLES[db]:
            if table in dc.SCHEMA[db]:
                cols = [dc.ident(c) + ' ' + typ + (' PRIMARY KEY' if c == 'id' else '')
                        for c, typ in dc.SCHEMA[db][table].items()]
            elif table == dc.VERSIONS[db][0]:
                cols = ['version_num varchar(32) NOT NULL']
            elif table in dc.SEEDS:
                cols = [dc.ident(k) + ' ' + ('boolean' if type(v) is bool else 'integer' if type(v) is int
                        else 'json' if isinstance(v, dict) else 'text') for k, v in dc.SEEDS[table].items()]
            else:
                cols = ['id integer PRIMARY KEY']
            sql += f'CREATE TABLE public.{dc.ident(table)} (' + ','.join(cols) + ');\n'
        if db == 'hengxin':
            self.query(sql + "INSERT INTO alembic_version VALUES('0032');"
                'ALTER TABLE role_assignments ADD FOREIGN KEY(user_id) REFERENCES users(id);')
            return
        sql += "INSERT INTO overseas_alembic_version VALUES ('overseas_0026');\n"
        sql += "ALTER TABLE overseas_members ADD CHECK(status IN ('active','pending','disabled'));\n"
        sql += ('ALTER TABLE overseas_member_roles ADD FOREIGN KEY(user_id) REFERENCES overseas_members(id);\n'
                'ALTER TABLE overseas_management_audit ADD FOREIGN KEY(actor_id) REFERENCES overseas_members(id);\n')
        self.query(sql)

    def seed_source(self):
        self.insert('overseas_members', sample('overseas_members', id=MEMBER, name="中文 ' \\n", status='disabled'))
        self.insert('overseas_member_roles', sample('overseas_member_roles', id=str(uuid.uuid4()), user_id=MEMBER, role='designer'))
        for action in ('skill.availability', 'studio.delete'):
            self.insert('overseas_management_audit', sample('overseas_management_audit', id=str(uuid.uuid4()),
                actor_id=MEMBER, action=action, before={'enabled': True}, after={'enabled': False}))
        self.query("INSERT INTO overseas_settings(id,version,values) VALUES (1,7,"
                   "'{\"precision\":0.12345678901234567890123456789}'::json);")

    def insert(self, table, row):
        self.query(f'INSERT INTO public.{dc.ident(table)} SELECT * FROM '
                   f'jsonb_populate_record(NULL::public.{dc.ident(table)},'
                   + dc.literal(json.dumps(row)) + '::jsonb);')

    def snapshot(self):
        raw = self.query(dc.source_sql(DB))
        dc.validate(raw, DB)
        return raw

    def test_filter_roundtrip_state_and_precision(self):
        self.seed_source()
        raw = self.snapshot()
        data = json.loads(raw)
        self.assertEqual(data['tables']['overseas_management_audit']['count'], 1)
        self.assertNotIn('studio.delete', raw)
        self.reset()
        self.query("INSERT INTO overseas_settings(id,version,values) VALUES (1,1,'{}');"
                   'INSERT INTO overseas_execution_gate(id,paused) VALUES(1,false);')
        self.query(dc.target_sql(DB, raw))
        self.assertEqual(self.query('SELECT status FROM overseas_members'), 'disabled')
        self.assertEqual(self.query("SELECT values->>'precision' FROM overseas_settings"),
                         '0.12345678901234567890123456789')
        self.assertEqual(json.loads(self.snapshot())['tables'], data['tables'])
        with self.assertRaisesRegex(RuntimeError, 'target not empty: overseas_management_audit|target not empty: overseas_member'):
            self.query(dc.target_sql(DB, raw))

    def test_business_data_and_dirty_seed_refused(self):
        raw = self.snapshot()
        self.query('INSERT INTO overseas_tasks VALUES(1);')
        with self.assertRaisesRegex(RuntimeError, 'target not empty: overseas_tasks'):
            self.query(dc.target_sql(DB, raw))
        self.assertEqual(self.query('SELECT count(*) FROM overseas_tasks'), '1')
        self.reset()
        self.query('INSERT INTO overseas_execution_gate(id,paused) VALUES(1,true);')
        with self.assertRaisesRegex(RuntimeError, 'target not empty: overseas_execution_gate'):
            self.query(dc.target_sql(DB, raw))

    def test_digest_failure_rolls_back_seed_and_insertions(self):
        self.seed_source()
        payload = json.loads(self.snapshot())
        payload['tables']['overseas_members']['sha256'] = '0' * 64
        self.reset()
        self.query("INSERT INTO overseas_settings(id,version,values) VALUES(1,1,'{}');")
        with self.assertRaises(RuntimeError):
            self.query(dc.target_sql(DB, json.dumps(payload)))
        self.assertEqual(self.query('SELECT count(*) FROM overseas_members'), '0')
        self.assertEqual(self.query('SELECT version FROM overseas_settings'), '1')

    def test_foreign_key_failure_rolls_back(self):
        self.seed_source()
        payload = json.loads(self.snapshot())
        payload['tables']['overseas_member_roles']['rows'][0]['user_id'] = str(uuid.uuid4())
        self.reset()
        with self.assertRaises(RuntimeError):
            self.query(dc.target_sql(DB, json.dumps(payload)))
        self.assertEqual(self.query('SELECT count(*) FROM overseas_members'), '0')

    def test_source_is_read_only_and_catalog_drift_rejected(self):
        sql = dc.source_sql(DB).replace('COMMIT;', 'CREATE TABLE must_not_exist(id int); COMMIT;')
        with self.assertRaises(RuntimeError):
            self.query(sql)
        self.assertEqual(self.query("SELECT to_regclass('public.must_not_exist') IS NULL"), 't')
        self.query('ALTER TABLE overseas_members ADD COLUMN unexpected text;')
        with self.assertRaises(RuntimeError):
            self.snapshot()

    def test_empty_version_rejects_source_and_target(self):
        raw = self.snapshot()
        self.query('DELETE FROM overseas_alembic_version;')
        for sql in (dc.source_sql(DB), dc.target_sql(DB, raw)):
            with self.assertRaises(RuntimeError):
                self.query(sql)
        self.assertEqual(self.query('SELECT count(*) FROM overseas_members'), '0')

    def test_assertion_rejects_null_and_false_accepts_true(self):
        for condition in ('NULL::boolean', 'false'):
            with self.assertRaises(RuntimeError):
                self.query('DO $test$ BEGIN ' + dc.assertion(condition, 'must reject') + 'END $test$;')
        self.query('DO $test$ BEGIN ' + dc.assertion('true', 'must accept') + 'END $test$;')

    def test_domestic_roundtrip_and_pristine_seeds(self):
        self.query('CREATE DATABASE hengxin;')
        self.cmd = list(self.cmd)
        self.cmd[self.cmd.index('-d') + 1] = 'hengxin'
        self.reset('hengxin')
        self.query("INSERT INTO users(id,status,name) VALUES ('" + MEMBER + "','pending','待审批');")
        raw = self.query(dc.source_sql('hengxin'))
        self.reset('hengxin')
        for table, seed in dc.SEEDS.items():
            if table in dc.ALL_TABLES['hengxin']:
                self.query(f'INSERT INTO public.{dc.ident(table)} SELECT * FROM '
                           f'jsonb_populate_record(NULL::public.{dc.ident(table)},'
                           + dc.literal(json.dumps(seed)) + '::jsonb);')
        self.query(dc.target_sql('hengxin', raw))
        self.assertEqual(self.query('SELECT status FROM users'), 'pending')
        self.assertEqual(self.query('SELECT count(*) FROM system_settings'), '0')

    def test_reclaim_projection_keeps_48_audits_and_verifies_digest(self):
        self.seed_source()
        normal = [sample('overseas_management_audit', id=str(uuid.uuid4()), actor_id=MEMBER,
                  action='skill.availability', before={'enabled': False}, after={'enabled': True}) for _ in range(46)]
        marker = 'PRIVATE_OLD_JOB_BODY_MUST_NEVER_LEAVE_SOURCE'
        raw_fields = {f: {k: {'private': marker} for k in dc.policy.RECLAIM_RAW[f]}
                      for f in ('before', 'after')}
        raw_fields['before'].update(release='a' * 64, centralBytes=20, libraryBytes=10)
        raw_fields['after'].update(release='b' * 64, centralBytes=15, libraryBytes=5,
                                  libraryAfterBytes=5, afterBytes=15, reclaimedBytes=5,
                                  cleanupComplete=True, dryRun=False)
        reclaim = sample('overseas_management_audit', id=str(uuid.uuid4()), actor_id=MEMBER,
                         action='skill.reclaim', target='skill-library', created_at='2026-11-10T00:00:00+00:00',
                         updated_at='2026-11-10T00:00:00+00:00', **raw_fields)
        self.query('INSERT INTO overseas_management_audit SELECT * FROM jsonb_populate_recordset('
                   'NULL::overseas_management_audit,' + dc.literal(json.dumps(normal + [reclaim])) + '::jsonb);')
        raw = self.snapshot()
        data = json.loads(raw)
        self.assertNotIn(marker, raw)
        audits = data['tables']['overseas_management_audit']
        self.assertEqual(audits['count'], 48)
        kept = next(r for r in audits['rows'] if r['action'] == 'skill.reclaim')
        self.assertEqual({k: v for k, v in kept.items() if k not in raw_fields},
                         {k: v for k, v in reclaim.items() if k not in raw_fields})
        self.assertEqual(data['audit_transformations']['reclaim_rows'], 1)
        for f in raw_fields:
            self.assertEqual(kept[f], {k: v for k, v in raw_fields[f].items() if k in dc.policy.RECLAIM_KEEP})
            self.assertEqual(data['audit_transformations'][f],
                             {k: 1 for k in dc.policy.RECLAIM_RAW[f] - dc.policy.RECLAIM_KEEP})
        for row in normal:
            self.assertIn(row, audits['rows'])
        self.assertEqual(self.query("SELECT before->'jobs'->>'private' FROM overseas_management_audit WHERE action='skill.reclaim'"), marker)
        self.reset()
        self.query(dc.target_sql(DB, raw))
        self.assertEqual(json.loads(self.snapshot())['tables'], data['tables'])
        self.assertNotIn('skill.reclaim', dc.rows_query(DB, 'overseas_management_audit', False))

    def test_unknown_reclaim_or_normal_fields_rejected_before_export(self):
        self.seed_source()
        for action, field, value in [('skill.reclaim', 'before', {'futureBusiness': 'private'}),
                                     ('skill.reclaim', 'after', {'futureBusiness': 'private'}),
                                     ('skill.reclaim', 'before', None),
                                     ('skill.update', 'before', {'jobs': 'private'})]:
            self.query('DELETE FROM overseas_management_audit;')
            row = sample('overseas_management_audit', id=str(uuid.uuid4()), actor_id=MEMBER,
                         action=action, before={}, after={})
            row[field] = value
            self.insert('overseas_management_audit', row)
            with self.assertRaises(RuntimeError):
                self.query(dc.source_sql(DB))
        self.assertEqual(self.query('SELECT count(*) FROM overseas_management_audit'), '1')


if __name__ == '__main__':
    unittest.main()
