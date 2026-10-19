"""Pinned 0.2.40 -> 0.2.41 overseas archive audit cutover; preserve domestic 0030.

CLI: RELEASE build|prepare|deploy. Failure stays closed for inspected recovery.
Never automatically downgrade, restore production data, or stop busy executors.
"""
import copy
import importlib.util
import json
from pathlib import Path
import re
import sys

spec = importlib.util.spec_from_file_location('studio_ux_base', Path(__file__).with_name('overseas-materials-deploy.py'))
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
d, c = previous.d, previous.c
b = d.m.module('member-release-backup')
d.TARGET_VERSION, d.BASE_VERSION = '0.2.41', '0.2.40'
d.DOMESTIC_MIGRATION, d.TARGET_MIGRATION = '0030', 'overseas_0018'
d.RELEASE_PATTERN = r'overseas-20261019-[0-9a-f]{7}'
c.BASE_RELEASE = 'overseas-20261016-8f991b4'
c.BASE_FRONTEND_RELEASE = 'domestic-retire-20261016-5d5d073'
c.BASE_NATIVE = Path('/opt/hengxin-overseas-releases') / c.BASE_RELEASE / 'backend'
c.DOMESTIC_NATIVE = Path('/opt/hengxin-native-releases') / c.BASE_FRONTEND_RELEASE / 'backend'
DOMESTIC_UNITS = ('hengxin-vps-codex-worker', 'hengxin-domestic-deletions', 'hengxin-retention')
d.m.UNITS = (*DOMESTIC_UNITS, *d.u.UNITS)
BASE_IMAGE = 'sha256:c05feb5677766667da738d8a5b17bac1b15301476c32c4ebb2bfa24a89a10c74'
RESTART = 'unless-stopped'
AUDIT_TABLE = 'overseas_archive_events'
TABLE_EXISTS = ("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' "
                "AND table_name='" + AUDIT_TABLE + "'")
c.REQUIRED |= {'scripts/release/overseas-studio-ux-deploy.py',
    'scripts/release/member-release-backup.py',
    'backend/migrations/versions/0030_retire_legacy.py',
    'backend/migrations/overseas/versions/0018_archive_events.py',
    'backend/app/overseas/archives/audit.py',
    'backend/tests/test_overseas_archive_audit.py',
    'backend/tests/test_overseas_archive_audit_migration.py'}
d.MIGRATION_RECOVERY = (' Only the overseas archive audit schema is added. After MIGRATION_STARTED, '
    'keep intake closed and inspect schema, queues and runtime before reviewed forward recovery. '
    'Never downgrade or restore databases automatically. Domestic 0030, identity, execution sessions, '
    'Skills, images and historical conversations must remain unchanged.')
_preflight, _overlay = d.preflight, d.resources.overlay
_same_settings, _topology = d.resources.same_settings, d.m.topology
_unchanged, _installed = d.resources.unchanged, d.installed


def domestic_native():
    return {unit: c.native_state(unit, c.DOMESTIC_NATIVE) for unit in DOMESTIC_UNITS}


def topology():
    data = _topology()
    # Container identity alone cannot detect a manual restart-policy change.
    for group in d.m.GROUPS:
        data[group]['runtime'] = {name: {
            'image': row['Image'], 'restart': row['HostConfig']['RestartPolicy']}
            for name in data[group]['ids'] for row in [d.m.live(name)]}
    return data


def preflight():
    _preflight()
    actual = d.m.live(d.u.API)
    assert actual['Image'] == BASE_IMAGE, 'Overseas image baseline drift'
    assert actual['HostConfig']['RestartPolicy']['Name'] == RESTART, 'API restart baseline drift'


def overlay(source, identity):
    result = _overlay(source, identity)
    result['services']['api']['restart'] = RESTART
    return result


def same_settings(before, after, m):
    assert after['services']['api']['restart'] == RESTART, 'API restart policy drift'
    normalized = copy.deepcopy(after)
    normalized['services']['api'].pop('restart')
    if 'restart' in before['services']['api']:
        normalized['services']['api']['restart'] = before['services']['api']['restart']
    _same_settings(before, normalized, m)


def unchanged(data, native, target, m, u, domestic):
    _unchanged(data, native, target, m, u, domestic)
    current = m.topology()
    for name, row in data['overseas']['runtime'].items():
        now = current['overseas']['runtime'][name]
        assert now['restart'] == row['restart'], 'Overseas restart policy changed'
        if name != u.API:
            assert now == row, 'Unrelated overseas runtime changed'


def check_schema(revision, table_count):
    assert d.r.sql('SELECT version_num FROM alembic_version') == '0030'
    assert d.u.sql('SELECT version_num FROM overseas_alembic_version') == revision
    assert d.u.sql(c.a.USAGE_COLUMN) == '0', 'Unexpected usage column'
    assert d.u.sql(previous.TABLE_EXISTS) == '1', 'Material visibility table missing'
    assert d.u.sql(TABLE_EXISTS) == table_count, 'Archive audit schema drift'


def schemas():
    check_schema('overseas_0017', '0')


def installed_schemas():
    check_schema('overseas_0018', '1')


def fingerprint(database):
    names = b.query(database, "SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename").splitlines()
    result = {}
    for name in names:
        assert re.fullmatch(r'[a-z][a-z0-9_]*', name), 'Unsafe table identifier'
        if name == 'overseas_alembic_version':
            continue
        result[name] = b.query(database, f'SELECT count(*)||\':\'||md5(coalesce(string_agg(md5(to_jsonb(t)::text),\'\' '
                              f'ORDER BY to_jsonb(t)::text),\'\')) FROM public."{name}" t')
    return result


def backup(work, destination, data):
    assert (work / 'EXECUTORS_STOPPED').is_file()
    assert d.u.pending() == int(d.u.sql(d.DELETING)) == 0
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    topology_data = json.loads((work / 'topology.json').read_text())
    b.m.UNITS = d.m.UNITS
    b.backup_config(work, destination, topology_data)
    database = b.DBS['overseas']
    before = fingerprint(database)
    d.m.private(destination / 'fingerprints.json', before)
    dump = destination / 'overseas.dump'
    b.dump(database, dump)
    b.fingerprint = fingerprint
    b.restore_check(database, dump, before, work.name, 'overseas')
    assert fingerprint(database) == before, 'Overseas data changed during backup'
    b.secure_tree(destination)
    d.m.private(destination / 'COMPLETE', 'Overseas dump isolated restore and exact row hashes verified')


def migrate(work, source, identity, data, destination):
    assert (destination / 'COMPLETE').is_file(), 'No verified complete backup'
    assert (work / 'EXECUTORS_STOPPED').is_file(), 'Executors were not drained and stopped'
    schemas()
    before_rows = json.loads((destination / 'fingerprints.json').read_text())
    assert fingerprint(b.DBS['overseas']) == before_rows, 'Data drift after backup'
    migration_overlay = work / 'overseas-migration-overlay.json'
    d.m.private(migration_overlay, {'services': {'migrate': {'image': identity,
        'build': {'context': str(source), 'dockerfile': 'infra/Dockerfile.backend'}}}})
    before = json.loads((work / 'overseas-compose.private.json').read_text())
    assert json.loads(d.m.compose(data['overseas'], 'config', '--format', 'json', capture=True)) == before
    after = json.loads(d.m.compose(data['overseas'], 'config', '--format', 'json', overlay=migration_overlay, capture=True))
    d.m.same_settings(before, after, ['migrate'])
    assert after['services']['migrate']['image'] == identity
    d.m.private(work / 'MIGRATION_STARTED', d.MIGRATION_RECOVERY)
    d.m.compose(data['overseas'], 'run', '--rm', '--no-deps', '--pull', 'never',
        'migrate', 'alembic', '-c', 'alembic.overseas.ini', 'upgrade', d.TARGET_MIGRATION, overlay=migration_overlay)
    installed_schemas()
    after_rows = fingerprint(b.DBS['overseas'])
    assert set(after_rows) - set(before_rows) == {AUDIT_TABLE}, 'Unexpected new tables'
    assert all(after_rows.get(k) == v for k, v in before_rows.items()), 'Existing business rows changed'
    d.m.private(destination / 'fingerprints-after.json', after_rows)
    d.m.private(work / 'MIGRATION_VERIFIED', 'overseas_0018: archive audit only; original rows unchanged')


def installed(work, manifest, identity, data, native, target):
    assert d.m.live(d.u.API)['HostConfig']['RestartPolicy']['Name'] == RESTART
    _installed(work, manifest, identity, data, native, target)


d.domestic_native = domestic_native
d.m.topology = topology
d.preflight = preflight
d.resources.overlay, d.resources.same_settings = overlay, same_settings
d.resources.unchanged = unchanged
d.schemas, d.installed_schemas = schemas, installed_schemas
d.u.backup, d.before_switch, d.installed = backup, migrate, installed
main = d.main

if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    d.m.module('release-retention').managed(main)
