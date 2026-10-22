"""Pinned 0.2.47 -> 0.2.48 arbitrary-file release; no schema or Skill changes."""
import importlib.util
import json
from pathlib import Path
import sys
from uuid import UUID

spec = importlib.util.spec_from_file_location('any_file_base', Path(__file__).with_name('overseas-archive-deletion-deploy.py'))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
d, m, u = a.d, a.m, a.u

a.BASE_VERSION = d.BASE_VERSION = '0.2.47'
d.TARGET_VERSION = '0.2.48'
d.DOMESTIC_MIGRATION, d.TARGET_MIGRATION = '0032', 'overseas_0020'
d.RELEASE_PATTERN = r'overseas-20261022-[0-9a-f]{7}'
FRONTEND_RELEASE = a.BASE_RELEASE = 'overseas-20261022-5c3715f'
a.BASE_IMAGE = 'sha256:ed7bafd1e6c0008fb89d7f19ef23e24546f5bcf2819b34de1b7aebb39924935c'
a.DOMESTIC_PATHS = {unit: Path('/opt/hengxin-native-releases/domestic-retention-20261021-bec8dd7/backend')
                    for unit in a.a.DOMESTIC_UNITS}
a.OVERSEAS_PATHS = {unit: Path('/opt/hengxin-overseas-releases') / a.BASE_RELEASE / 'backend' for unit in u.UNITS}
u.DROP = 'zzzzzzzz-any-file-20261022.conf'
OWNER_KEY = 'OVERSEAS_SKILL_TOGGLE_OWNER_ID'
TABLE = 'overseas_installed_skill_availability'
TABLE_EXISTS = "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='" + TABLE + "'"
SCHEMA = """SELECT md5(jsonb_build_array(
    (SELECT jsonb_agg(to_jsonb(c) ORDER BY table_name,ordinal_position) FROM information_schema.columns c WHERE table_schema='public'),
    (SELECT jsonb_agg(to_jsonb(c) ORDER BY table_name,constraint_name) FROM information_schema.table_constraints c WHERE table_schema='public'),
    (SELECT jsonb_agg(to_jsonb(i) ORDER BY tablename,indexname) FROM pg_indexes i WHERE schemaname='public')
)::text)"""
a.c.REQUIRED |= {'scripts/release/overseas-any-file-deploy.py',
    'backend/app/overseas/studio/files.py', 'backend/tests/test_studio_any_file.py',
    'backend/migrations/overseas/versions/0020_skill_availability.py'}
d.MIGRATION_RECOVERY = (' No schema migration in this release. Keep intake closed on failure; inspect phase, '
    'queues and runtime before reviewed forward recovery. Never restore or downgrade production databases. '
    'Preserve domestic 0032, overseas_0020, identity, credential broker, owner binding and all existing Skill states.')
_prepare, _prepared_settings, _installed = a.prepare, d.prepared_settings, a.installed


def schemas():
    assert d.r.sql('SELECT version_num FROM alembic_version') == '0032', 'Domestic schema drift'
    assert u.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0020', 'Overseas revision drift'
    assert u.sql(a.c.a.USAGE_COLUMN) == '0', 'Unexpected usage column'
    for query in (a.a.previous.TABLE_EXISTS, a.a.TABLE_EXISTS, a.TABLE_EXISTS, TABLE_EXISTS):
        assert u.sql(query) == '1', 'Existing overseas table missing'


def owner_binding():
    values = [v.split('=', 1)[1] for v in m.live(u.API)['Config']['Env'] if v.startswith(OWNER_KEY + '=')]
    assert len(values) == 1, 'Existing API owner binding missing or duplicated'
    value = values[0]
    assert str(UUID(value)) == value and UUID(value).int, 'Invalid existing API owner binding'
    return value


def prepared_settings(work, data, identity, source):
    pinned = json.loads((work / 'any-file-baseline.private.json').read_text())
    assert owner_binding() == pinned['owner'], 'API owner binding drift since preparation'
    assert u.sql(SCHEMA) == pinned['schema'], 'Schema drift since preparation'
    before = json.loads((work / 'overseas-compose.private.json').read_text())
    assert before['services']['api'].get('environment', {}).get(OWNER_KEY) == pinned['owner'], 'Compose owner binding mismatch'
    _prepared_settings(work, data, identity, source)


def prepare(work, source, manifest, image):
    assert source == work / 'src', 'Unexpected prepared source location'
    assert not (work / 'PREPARED').exists(), 'Already prepared'
    schemas()
    a.preflight()
    current = {'owner': owner_binding(), 'schema': u.sql(SCHEMA)}
    path = work / 'any-file-baseline.private.json'
    if path.exists():
        assert json.loads(path.read_text()) == current, 'Baseline drift during preparation retry'
    else:
        m.private(path, current)
    _prepare(work, source, manifest, image)


def verify_unchanged_data(work, source, identity, data, destination):
    assert (destination / 'COMPLETE').is_file(), 'No verified complete backup'
    assert (work / 'EXECUTORS_STOPPED').is_file(), 'Executors were not drained and stopped'
    schemas()
    prepared_settings(work, data, identity, source)
    before = json.loads((destination / 'fingerprints.json').read_text())
    assert TABLE in before, 'Availability table missing from backup'
    assert a.a.fingerprint(a.a.b.DBS['overseas']) == before, 'Data drift after backup'
    m.private(work / 'skill-state.private.json', {'fingerprint': before[TABLE]})
    m.private(work / 'SCHEMA_UNCHANGED', 'overseas_0020 and domestic 0032; exact overseas row hashes unchanged')


def installed(work, manifest, identity, data, native, target):
    _installed(work, manifest, identity, data, native, target)
    baseline = json.loads((work / 'any-file-baseline.private.json').read_text())
    assert owner_binding() == baseline['owner'], 'Installed API owner binding drift'
    assert u.sql(SCHEMA) == baseline['schema'], 'Installed schema drift'
    expected = json.loads((work / 'skill-state.private.json').read_text())['fingerprint']
    assert a.a.fingerprint(a.a.b.DBS['overseas']).get(TABLE) == expected, 'Installed Skill state drift'
    m.private(work / 'ANY_FILE_PRESERVATION_VERIFIED', 'Existing owner, schema and arbitrary Skill state preserved')


a.schemas = d.schemas = a.installed_schemas = d.installed_schemas = schemas
d.prepare, d.prepared_settings = prepare, prepared_settings
d.before_switch, d.installed = verify_unchanged_data, installed
main = d.main

if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    m.module('release-retention').managed(main)
