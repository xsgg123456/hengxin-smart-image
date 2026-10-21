"""Restore-test a full dump; permit only the reviewed retention schedule migration."""
import importlib.util
import json
from pathlib import Path
import re
import shutil

spec = importlib.util.spec_from_file_location('retry', Path(__file__).with_name('api-retry-deploy.py'))
p = importlib.util.module_from_spec(spec)
spec.loader.exec_module(p)
m, b, DATABASE = p.m, p.b, p.DATABASE
SCHEDULE = """SELECT coalesce(json_object_agg(id, CASE
 WHEN domain='api_cli' AND status='active' THEN last_activity_at +
 CASE WHEN cache_cleared_at IS NULL THEN interval '24 hours' ELSE interval '72 hours' END
 ELSE next_cleanup_at END),'{}'::json) FROM cli_retention"""
ACTUAL_SCHEDULE = "SELECT coalesce(json_object_agg(id,next_cleanup_at),'{}'::json) FROM cli_retention"


def fingerprint(database, schedule=False):
    names = b.query(database, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
    result = {}
    for name in names:
        assert re.fullmatch(r'[a-z][a-z0-9_]*', name)
        if name == 'alembic_version':
            continue
        row = "(to_jsonb(t)-'next_cleanup_at')" if schedule and name == 'cli_retention' else 'to_jsonb(t)'
        result[name] = b.query(database, f"SELECT count(*)||':'||md5(coalesce(string_agg(md5({row}::text),'' "
            f"ORDER BY {row}::text),'')) FROM public.\"{name}\" t")
    return result


def create(work, destination, data, release):
    assert (work / 'EXECUTORS_STOPPED').exists() and (work / 'CLEANUP_STOPPED').exists()
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    m.private(destination / 'topology.json', data)
    for path in {*data['domestic']['files'], *data['nativeFiles']}:
        b.save_file(destination, path)
    for relative in ('frontend/package.json', 'frontend/dist/index.html', 'frontend/dist/index.html.gz'):
        if (m.APP / relative).exists():
            b.save_file(destination, m.APP / relative)
    for path in m.APP.glob('*RELEASE.json'):
        b.save_file(destination, path)
    for name in ('edge-before.conf', 'web-before.conf', 'domestic-compose.private.json', 'native-snapshots.private.json'):
        shutil.copyfile(work / name, destination / name)
    raw, projected = fingerprint(DATABASE), fingerprint(DATABASE, True)
    m.private(destination / 'fingerprints-full.json', raw)
    m.private(destination / 'fingerprints-preserved.json', projected)
    m.private(destination / 'columns.json', p.columns(DATABASE))
    m.private(destination / 'expected-schedules.json', b.query(DATABASE, SCHEDULE))
    target = destination / 'domestic.dump'
    b.dump(DATABASE, target)
    original = b.fingerprint
    try:
        b.fingerprint = fingerprint
        b.restore_check(DATABASE, target, raw, release, 'domestic')
    finally:
        b.fingerprint = original
    assert fingerprint(DATABASE) == raw, 'Database changed during backup'
    b.secure_tree(destination)
    m.private(destination / 'COMPLETE', 'Full domestic dump restored offline and all row fingerprints matched')


def verify_after(destination, added):
    assert (destination / 'COMPLETE').exists()
    before = json.loads((destination / 'fingerprints-preserved.json').read_text())
    after = fingerprint(DATABASE, True)
    assert set(after) - set(before) == set(added), 'Unexpected migration tables'
    assert all(after.get(name) == value for name, value in before.items()), 'Existing rows changed outside schedule'
    columns = json.loads((destination / 'columns.json').read_text())
    actual = p.columns(DATABASE)
    assert all(actual.get(name) == fields for name, fields in columns.items()), 'Existing schema changed'
    actual_schedules = json.loads(b.query(DATABASE, ACTUAL_SCHEDULE))
    assert actual_schedules == json.loads((destination / 'expected-schedules.json').read_text()), 'Retention schedule or pending barrier changed'
    m.private(destination / 'fingerprints-after.json', after)
