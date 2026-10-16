"""Full restore-tested dump plus exact row fingerprints under the reviewed 0030 contract."""
import ast
import importlib.util
import json
from pathlib import Path
import re
import shutil

spec = importlib.util.spec_from_file_location('domestic_backup', Path(__file__).with_name('domestic-backup.py'))
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
b, m, DATABASE = old.b, old.m, old.DATABASE


def identifier(value):
    assert isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_]*', value), 'Unsafe SQL identifier'
    return '"' + value + '"'


def contract(source):
    path = source / 'backend/migrations/versions/0030_retire_legacy.py'
    tree = ast.parse(path.read_text(encoding='utf-8'))
    nodes = [node.value for node in tree.body if isinstance(node, ast.Assign)
             and any(isinstance(t, ast.Name) and t.id == 'RETIREMENT_CONTRACT' for t in node.targets)]
    assert len(nodes) == 1, 'Missing unique literal retirement contract'
    value = ast.literal_eval(nodes[0])
    assert value['version'] == 1
    assert set(value) == {'version', 'drop_tables', 'retired_job_kinds', 'row_filters', 'drop_columns', 'json_remove'}
    assert len(value['drop_tables']) == len(set(value['drop_tables'])) == 22
    assert set(value['retired_job_kinds']) == {'generation', 'skill_install', 'skill_check', 'skill_sync'}
    for table in value['drop_tables']:
        identifier(table)
    for table, predicate in value['row_filters'].items():
        identifier(table)
        assert isinstance(predicate, str) and not any(s in predicate for s in (';', '--', '/*'))
    for table, columns in value['drop_columns'].items():
        identifier(table)
        for column in columns:
            identifier(column)
    for table, columns in value['json_remove'].items():
        identifier(table)
        for column, keys in columns.items():
            identifier(column)
            assert all(re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', key) for key in keys)
    return value


def projection(name, policy):
    row = 'to_jsonb(t)'
    for column in policy.get('drop_columns', {}).get(name, []):
        identifier(column)
        row = '(' + row + "-'" + column + "')"
    for column, keys in policy.get('json_remove', {}).get(name, {}).items():
        expr = 't.' + identifier(column) + '::jsonb'
        for key in keys:
            assert re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', key)
            expr = '(' + expr + "-'" + key + "')"
        row = '(' + row + " || jsonb_build_object('" + column + "'," + expr + '))'
    return row


def fingerprint(database, policy=None):
    policy = policy or {}
    names = b.query(database, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
    result = {}
    for name in names:
        table = identifier(name)
        if name == 'alembic_version' or name in policy.get('drop_tables', []):
            continue
        row = projection(name, policy)
        predicate = policy.get('row_filters', {}).get(name, 'true')
        result[name] = b.query(database, f"SELECT count(*)||':'||md5(coalesce(string_agg(md5({row}::text),'' "
                               f"ORDER BY {row}::text),'')) FROM public.{table} t WHERE {predicate}")
    return result


def compare(before, after):
    assert set(before) == set(after), 'Unexpected preserved table set'
    for name, expected in before.items():
        assert after[name] == expected, 'Preserved business rows changed: ' + name


def create(work, destination, data, release, source):
    assert (work / 'EXECUTORS_STOPPED').exists() and (work / 'CLEANUP_STOPPED').exists()
    policy = contract(source)
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    m.private(destination / 'topology.json', data)
    for path in {*data['domestic']['files'], *data['nativeFiles']}:
        b.save_file(destination, path)
    for relative in ('frontend/package.json', 'frontend/dist/index.html'):
        b.save_file(destination, m.APP / relative)
    if (m.APP / 'frontend/dist/index.html.gz').exists():
        b.save_file(destination, m.APP / 'frontend/dist/index.html.gz')
    for path in m.APP.glob('*RELEASE.json'):
        b.save_file(destination, path)
    for name in ('edge-before.conf', 'web-before.conf', 'native-snapshots.private.json', 'domestic-compose.private.json'):
        shutil.copyfile(work / name, destination / name)
    raw, projected = fingerprint(DATABASE), fingerprint(DATABASE, policy)
    assert set(raw) - set(projected) == set(policy['drop_tables']), 'Pre-migration legacy table set differs'
    m.private(destination / 'fingerprints-full.json', raw)
    m.private(destination / 'fingerprints-preserved.json', projected)
    m.private(destination / 'contract.json', policy)
    target = destination / 'domestic.dump'
    b.dump(DATABASE, target)
    b.fingerprint = fingerprint
    b.restore_check(DATABASE, target, raw, release, 'domestic')
    compare(raw, fingerprint(DATABASE))
    b.secure_tree(destination)
    m.private(destination / 'COMPLETE', 'Full dump isolated restore and every row fingerprint verified')


def verify_after(destination):
    policy = json.loads((destination / 'contract.json').read_text())
    actual = fingerprint(DATABASE)
    assert not set(policy['drop_tables']) & set(actual), 'Legacy tables survived migration'
    # Use raw after hashes: deleted rows/keys must really be gone, not hidden by projection.
    compare(json.loads((destination / 'fingerprints-preserved.json').read_text()), actual)
    m.private(destination / 'fingerprints-after.json', actual)
