"""Domestic-only full dump, isolated restore and exact pre-existing row invariants."""
import importlib.util
import json
from pathlib import Path
import re
import shutil

spec = importlib.util.spec_from_file_location('member_backup', Path(__file__).with_name('member-release-backup.py'))
b = importlib.util.module_from_spec(spec)
spec.loader.exec_module(b)
m = b.m
DATABASE = b.DBS['domestic']


def fingerprint(database):
    names = b.query(database, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
    result = {}
    for name in names:
        assert re.fullmatch(r'[a-z][a-z0-9_]*', name)
        if name == 'alembic_version':
            continue
        result[name] = b.query(database, f'SELECT count(*)||\':\'||md5(coalesce(string_agg(md5(to_jsonb(t)::text),\'\' '
                              f'ORDER BY to_jsonb(t)::text),\'\')) FROM public."{name}" t')
    return result


def compare(before, after):
    assert set(after) - set(before) == {'api_task_deletions'}, 'Unexpected migration table set'
    assert all(after.get(name) == value for name, value in before.items()), 'Existing business rows changed'
    assert after['api_task_deletions'].startswith('0:'), 'Migration enqueued historical deletions'


def create(work, destination, data, release):
    assert (work / 'EXECUTORS_STOPPED').exists()
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    m.private(destination / 'topology.json', data)
    for path in data['domestic']['files']:
        b.save_file(destination, path)
    for path in data['nativeFiles']:
        b.save_file(destination, path)
    for relative in ('frontend/package.json', 'frontend/dist/index.html'):
        b.save_file(destination, m.APP / relative)
    if (m.APP / 'frontend/dist/index.html.gz').exists():
        b.save_file(destination, m.APP / 'frontend/dist/index.html.gz')
    for path in m.APP.glob('*RELEASE.json'):
        b.save_file(destination, path)
    for name in ('edge-before.conf', 'web-before.conf', 'native-policy.json', 'domestic-compose.private.json'):
        shutil.copyfile(work / name, destination / name)
    before = fingerprint(DATABASE)
    m.private(destination / 'fingerprints.json', before)
    target = destination / 'domestic.dump'
    b.dump(DATABASE, target)
    # The reusable restore uses its module's fingerprint; bind the strict row comparison.
    b.fingerprint = fingerprint
    b.restore_check(DATABASE, target, before, release, 'domestic')
    assert fingerprint(DATABASE) == before, 'Database changed during backup'
    b.secure_tree(destination)
    m.private(destination / 'COMPLETE', 'Domestic full dump restored and exact row hashes matched')


def verify_after(destination):
    after = fingerprint(DATABASE)
    compare(json.loads((destination / 'fingerprints.json').read_text()), after)
    m.private(destination / 'fingerprints-after.json', after)
