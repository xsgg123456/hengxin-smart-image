"""Full-row/schema restore evidence and read-only installed route checks."""
import importlib.util
import json
from pathlib import Path
import re
import shutil

spec = importlib.util.spec_from_file_location('record_runtime', Path(__file__).with_name('domestic-record-filters-runtime.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
m, r, b, DATABASE = s.m, s.r, s.p.b, s.p.DATABASE
schema_spec = importlib.util.spec_from_file_location('record_schema', Path(__file__).with_name('domestic-record-filters-schema.py'))
schema = importlib.util.module_from_spec(schema_spec)
schema_spec.loader.exec_module(schema)
SCHEMA = """SELECT json_build_object(
 'columns',(SELECT json_agg(t ORDER BY table_name,ordinal_position) FROM
   (SELECT table_name,column_name,ordinal_position,column_default,is_nullable,data_type,
    udt_schema,udt_name,character_maximum_length,numeric_precision,numeric_scale,
    datetime_precision,is_identity,identity_generation,is_generated,generation_expression
    FROM information_schema.columns WHERE table_schema='public') t),
 'constraints',(SELECT json_agg(t ORDER BY relation,name) FROM
   (SELECT c.conrelid::regclass::text AS relation,c.conname AS name,
    pg_get_constraintdef(c.oid) AS definition FROM pg_constraint c
    JOIN pg_namespace n ON n.oid=c.connamespace WHERE n.nspname='public') t),
 'indexes',(SELECT json_agg(t ORDER BY tablename,indexname) FROM
   (SELECT tablename,indexname,indexdef FROM pg_indexes WHERE schemaname='public') t))"""


def state(database):
    names = b.query(database, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
    rows = {}
    for name in names:
        assert re.fullmatch(r'[a-z][a-z0-9_]*', name)
        # Include every column, schedule, heartbeat, receipt and Alembic version row.
        rows[name] = b.query(database, "SELECT count(*)||':'||md5(coalesce(string_agg(md5(to_jsonb(t)::text),'' "
            f"ORDER BY to_jsonb(t)::text),'')) FROM public.\"{name}\" t")
    structure = json.loads(b.query(database, SCHEMA))
    for constraint in structure['constraints'] or []:
        constraint['definition'] = schema.constraint_definition(constraint['definition'])
    return dict(rows=rows, schema=structure, columns=s.p.columns(database))


def backup(work, destination, data, release):
    assert (work / 'EXECUTORS_STOPPED').exists() and (work / 'CLEANUP_STOPPED').exists()
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    m.private(destination / 'topology.json', data)
    for path in {*data['domestic']['files'], *data['nativeFiles']}:
        b.save_file(destination, path)
    s.n.backup(destination, data)
    for relative in ('frontend/package.json', 'frontend/dist/index.html', 'frontend/dist/index.html.gz'):
        if (m.APP / relative).exists():
            b.save_file(destination, m.APP / relative)
    for path in m.APP.glob('*RELEASE.json'):
        b.save_file(destination, path)
    for name in ('edge-before.conf', 'web-before.conf', 'domestic-compose.private.json'):
        shutil.copyfile(work / name, destination / name)
    before = state(DATABASE)
    m.private(destination / 'database-state.json', before)
    target = destination / 'domestic.dump'
    b.dump(DATABASE, target)
    original = b.fingerprint
    try:
        # The generic helper restores into a temporary --network none PostgreSQL.
        # Comparing this complete object verifies schema/columns as well as all rows.
        b.fingerprint = state
        b.restore_check(DATABASE, target, before, release, 'domestic')
    finally:
        b.fingerprint = original
    assert state(DATABASE) == before, 'Database changed during backup'
    b.secure_tree(destination)
    m.private(destination / 'COMPLETE', 'Isolated restore matched every row, schema and column; no migration')


def preserved(destination):
    assert (destination / 'COMPLETE').exists()
    assert state(DATABASE) == json.loads((destination / 'database-state.json').read_text()), 'Database changed before consumers resumed'


def routes():
    origin = 'http://127.0.0.1:18008'
    m.run('curl', '--max-time', '15', '--retry', '10', '--retry-delay', '2', '--retry-connrefused',
          '-fsS', '-o', '/dev/null', origin + '/api/v1/health/ready')
    for path in ('tasks', 'creators'):
        code = m.run('curl', '--max-time', '15', '-sS', '-o', '/dev/null', '-w', '%{http_code}',
            origin + '/api/v1/api-image-edits/' + path, capture=True)
        assert code == '401', 'Missing or unauthenticated record route: ' + path
    document = json.loads(m.run('curl', '--max-time', '15', '-fsS', origin + '/openapi.json', capture=True))
    params = {p['name']: p for p in document['paths']['/api/v1/api-image-edits/tasks']['get']['parameters']}
    assert {'scope', 'creatorId', 'dateFrom', 'dateTo'} <= params.keys()
    assert params['scope']['schema']['default'] == 'mine'
    assert '/api/v1/api-image-edits/creators' in document['paths']


def frontend(source):
    assert (m.APP / 'frontend/package.json').read_bytes() == (source / 'frontend/package.json').read_bytes()
    for origin in ('http://127.0.0.1:18080', r.ORIGIN):
        actual = m.run('curl', '--max-time', '15', '-fsS', origin + '/', capture=True)
        assert actual == (source / 'frontend/dist/index.html').read_text().strip()
