"""Pinned 0.2.46 -> 0.2.47 cutover; overseas-only additive availability migration."""
import importlib.util
import json
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('skill_availability_base', Path(__file__).with_name('overseas-archive-deletion-deploy.py'))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
d, m, u = a.d, a.m, a.u
owner = m.module('overseas-skill-availability-owner')
a.BASE_VERSION = d.BASE_VERSION = '0.2.46'
d.TARGET_VERSION = '0.2.47'
d.DOMESTIC_MIGRATION, d.TARGET_MIGRATION = '0032', 'overseas_0020'
d.RELEASE_PATTERN = r'overseas-20261022-[0-9a-f]{7}'
FRONTEND_RELEASE = 'domestic-retention-20261021-bec8dd7'
a.BASE_RELEASE = 'overseas-20261019-1c28ee2'
a.BASE_IMAGE = 'sha256:1a406c0ad954788dbe5b6c004005dcea6005e318995dc716e1d86d3fcc808854'
a.DOMESTIC_PATHS = {unit: Path('/opt/hengxin-native-releases') / FRONTEND_RELEASE / 'backend' for unit in a.a.DOMESTIC_UNITS}
a.OVERSEAS_PATHS = {unit: Path('/opt/hengxin-overseas-releases') / a.BASE_RELEASE / 'backend' for unit in u.UNITS}
u.DROP = 'zzzzzzz-skill-availability-20261022.conf'
TABLE = 'overseas_installed_skill_availability'
TABLE_EXISTS = "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='" + TABLE + "'"
OLD_COLUMNS = ("SELECT md5(coalesce(string_agg(to_jsonb(c)::text, '' ORDER BY table_name, ordinal_position), '')) "
    "FROM information_schema.columns c WHERE table_schema='public' AND table_name NOT IN "
    "('overseas_alembic_version', '" + TABLE + "')")
a.c.REQUIRED |= {'scripts/release/overseas-skill-availability-deploy.py',
    'scripts/release/overseas-skill-availability-owner.py',
    'backend/migrations/overseas/versions/0020_skill_availability.py'}
d.MIGRATION_RECOVERY = (' Only overseas_installed_skill_availability and its two approved initial rows are added. '
    'After MIGRATION_STARTED keep intake closed; inspect schema, queues and runtime before reviewed forward recovery. '
    'Never downgrade or restore production databases automatically. Preserve domestic 0032, identity and broker.')
_prepare, _installed = a.prepare, a.installed
_overlay, _same_settings = d.resources.overlay, d.resources.same_settings


def check_schema(revision, count):
    assert d.r.sql('SELECT version_num FROM alembic_version') == '0032', 'Domestic schema drift'
    assert u.sql('SELECT version_num FROM overseas_alembic_version') == revision, 'Overseas revision drift'
    assert u.sql(a.c.a.USAGE_COLUMN) == '0', 'Unexpected usage column'
    for query in (a.a.previous.TABLE_EXISTS, a.a.TABLE_EXISTS, a.TABLE_EXISTS):
        assert u.sql(query) == '1', 'Existing overseas table missing'
    assert u.sql(TABLE_EXISTS) == count, 'Availability schema drift'


def schemas():
    check_schema('overseas_0019', '0')


def installed_schemas():
    check_schema('overseas_0020', '1')
    rows = u.sql('SELECT id FROM ' + TABLE + ' WHERE enabled AND version=1 ORDER BY id').splitlines()
    assert set(rows) == owner.ENABLED and len(rows) == 2, 'Initial enabled Skills drift'
    assert u.sql('SELECT count(*) FROM ' + TABLE) == '2', 'Unexpected initial availability rows'


def preflight():
    assert json.loads((m.APP / 'frontend/package.json').read_text())['version'] == a.BASE_VERSION
    for name, release in [('FRONTEND_RELEASE.json', FRONTEND_RELEASE), ('OVERSEAS_RELEASE.json', a.BASE_RELEASE)]:
        assert json.loads((m.APP / name).read_text())['release'] == release, 'Release baseline drift'
    actual = m.live(u.API)
    assert actual['Image'] == a.BASE_IMAGE, 'Overseas image baseline drift'
    assert actual['State']['Running'] and actual['State']['Health']['Status'] == 'healthy'
    assert actual['HostConfig']['Memory'] == d.resources.API_MEMORY
    assert actual['HostConfig']['RestartPolicy']['Name'] == a.a.RESTART
    for unit, path in a.OVERSEAS_PATHS.items():
        a.native_state(unit, path)
        a.pointer(unit, path)
        effective = a.show(unit, 'DropInPaths').split()
        assert effective and all(Path(p).name < u.DROP for p in effective), 'Higher priority override'
        assert all(p.name < u.DROP for p in (a.c.SYSTEMD / (unit + '.service.d')).glob('*.conf')), 'Unloaded higher priority override'
    worker = a.settings(u.UNITS[0])
    assert 'hengxin-codex-auth' in worker['SupplementaryGroups'].split()
    assert 'OVERSEAS_CODEX_AUTH_BROKER_SOCKET=' + str(a.SOCKET) in worker['Environment'].split()
    a.domestic_native()
    for path in (m.EDGE, d.proxy.inner(m)):
        a.c.a.proxy_baseline(path.read_text())


def overlay(source, identity):
    result = _overlay(source, identity)
    result['services']['api']['environment'] = {owner.KEY: owner.pinned(source.parent, u)}
    return result


def same_settings(before, after, runtime):
    _same_settings(before, owner.normalize(before, after), runtime)


def prepare(work, source, manifest, image):
    assert source == work / 'src', 'Unexpected prepared source location'
    assert not (work / 'PREPARED').exists(), 'Already prepared'
    binding = owner.read(work)
    owner.account(binding['owner'], u)
    evidence = work / 'skill-owner.private.json'
    if evidence.exists():
        assert json.loads(evidence.read_text()) == binding, 'Owner changed during preparation retry'
    else:
        m.private(evidence, binding)
    _prepare(work, source, manifest, image)
    owner.pinned(work, u)


def migrate(work, source, identity, data, destination):
    owner.pinned(work, u)
    assert (destination / 'COMPLETE').is_file(), 'No verified complete backup'
    assert (work / 'EXECUTORS_STOPPED').is_file(), 'Executors were not drained and stopped'
    schemas()
    before_rows = json.loads((destination / 'fingerprints.json').read_text())
    assert a.a.fingerprint(a.a.b.DBS['overseas']) == before_rows, 'Data drift after backup'
    before_columns = u.sql(OLD_COLUMNS)
    migration_overlay = work / 'overseas-migration-overlay.json'
    m.private(migration_overlay, {'services': {'migrate': {'image': identity,
        'build': {'context': str(source), 'dockerfile': 'infra/Dockerfile.backend'}}}})
    before = json.loads((work / 'overseas-compose.private.json').read_text())
    assert json.loads(m.compose(data['overseas'], 'config', '--format', 'json', capture=True)) == before
    after = json.loads(m.compose(data['overseas'], 'config', '--format', 'json', overlay=migration_overlay, capture=True))
    m.same_settings(before, after, ['migrate'])
    assert after['services']['migrate']['image'] == identity
    m.private(work / 'MIGRATION_STARTED', d.MIGRATION_RECOVERY)
    m.compose(data['overseas'], 'run', '--rm', '--no-deps', '--pull', 'never',
        'migrate', 'alembic', '-c', 'alembic.overseas.ini', 'upgrade', d.TARGET_MIGRATION, overlay=migration_overlay)
    installed_schemas()
    assert u.sql(OLD_COLUMNS) == before_columns, 'Existing table columns changed'
    after_rows = a.a.fingerprint(a.a.b.DBS['overseas'])
    assert set(after_rows) - set(before_rows) == {TABLE}, 'Unexpected new tables'
    assert all(after_rows.get(k) == v for k, v in before_rows.items()), 'Existing business rows changed'
    m.private(destination / 'fingerprints-after.json', after_rows)
    m.private(work / 'MIGRATION_VERIFIED', 'overseas_0020: availability only; original rows unchanged; domestic 0032 preserved')


def installed(work, manifest, identity, data, native, target):
    owner.installed(work, m, u)
    _installed(work, manifest, identity, data, native, target)


# prepare resolves module-level hooks on a; cutover resolves hooks on d.
a.preflight = d.preflight = preflight
a.schemas = d.schemas = schemas
a.installed_schemas = d.installed_schemas = installed_schemas
d.resources.overlay, d.resources.same_settings = overlay, same_settings
d.prepare, d.before_switch, d.installed = prepare, migrate, installed
main = d.main

if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    m.module('release-retention').managed(main)
