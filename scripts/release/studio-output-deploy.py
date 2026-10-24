"""0.2.51 -> 0.2.52: additive files schema, existing full release workflow.

CLI: RELEASE build|prepare|deploy. Optional incident settlement requires a private
explicit request, runs only after admission closes, and never collects files.
"""
import importlib.util
import json
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('studio_output_release_base',
    Path(__file__).with_name('studio-delivery-reliability-20261024.py'))
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
s, a, d, m, u = previous.s, previous.a, previous.d, previous.m, previous.u
data_check = m.module('studio-output-data')
settle = m.module('studio-output-settle')
a.BASE_VERSION = d.BASE_VERSION = '0.2.51'
d.TARGET_VERSION, d.TARGET_MIGRATION = '0.2.52', 'overseas_0022'
s.FRONTEND_RELEASE = a.BASE_RELEASE = 'overseas-20261024-59ceb83'
a.BASE_IMAGE = 'sha256:64129f632688e11d09723f3d92822badd7856554f64fce4cfaba19109e7ea1c1'
a.OVERSEAS_PATHS = {unit: Path('/opt/hengxin-overseas-releases') / a.BASE_RELEASE / 'backend' for unit in u.UNITS}
u.DROP = 'zzzzzzzzzzzz-studio-output-20261024.conf'
EXPECTED_COMPOSE_TAIL = [s.GRANT_OVERLAY,
    '/opt/hengxin-releases/overseas-20261024-71ed440/overseas-overlay.json',
    '/opt/hengxin-releases/' + a.BASE_RELEASE + '/overseas-overlay.json']
previous.EXPECTED_COMPOSE_TAIL = EXPECTED_COMPOSE_TAIL[-2:]
previous.TESTS += ['tests/test_studio_open_outputs.py', 'tests/test_overseas_studio_file_recovery.py',
                   'tests/test_studio_output_lifecycle.py', 'tests/test_studio_recovery_transport.py',
                   'tests/test_studio_recovery_versions.py']
REQUIRED = {'scripts/release/studio-output-' + name + '.py' for name in ('deploy', 'data', 'settle', 'settle-runtime')}
REQUIRED |= {'backend/migrations/overseas/versions/0022_studio_output_files.py',
    'backend/app/overseas/studio/output_store.py', 'backend/app/overseas/studio/recovery_files.py',
    'backend/app/overseas/studio/recovery_listing.py', 'backend/app/overseas/studio/recovery_router.py',
    'backend/app/overseas/studio/recovery_transport.py',
    'backend/app/overseas/studio/output_files.py',
    *('backend/' + name for name in previous.TESTS)}
previous.REQUIRED |= REQUIRED
s.REQUIRED |= REQUIRED
a.c.REQUIRED |= REQUIRED
d.MIGRATION_RECOVERY = (' Add only overseas_studio_output_files; preserve domestic 0032, identity, '
    'broker, all permission bindings and Skill contents/states. After migration an application rollback '
    'must retain overseas_0022 and its new table, prove a new drain and inspect output data compatibility. '
    'Never downgrade or restore production databases; keep admission closed on failure.')
_preflight, _prepare, _installed = previous.preflight, previous.prepare, previous.installed
_drain_and_stop = d.drain_and_stop


def schemas():
    s.check_schema('overseas_0021')
    assert u.sql("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' "
                 "AND table_name='overseas_studio_output_files'") == '0', 'Output schema baseline drift'


def installed_schemas():
    s.check_schema('overseas_0022')
    assert u.sql("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' "
                 "AND table_name='overseas_studio_output_files'") == '1', 'Output schema missing'


def preflight():
    actual = m.live(u.API)
    paths = actual['Config']['Labels']['com.docker.compose.project.config_files'].split(',')
    assert paths[-3:] == EXPECTED_COMPOSE_TAIL, 'Permission/release Compose chain drift'
    _preflight()


def prepare(work, source, manifest, image):
    if (work / settle.REQUEST).exists():
        settle.pin(work, m)
    _prepare(work, source, manifest, image)


def drain_and_stop(work):
    if (work / settle.REQUEST).exists():
        settle.run(work, a.OVERSEAS_PATHS[u.UNITS[0]], m, d, u)
    _drain_and_stop(work)


def before_switch(work, source, identity, data, destination):
    assert (destination / 'COMPLETE').is_file(), 'Verified isolated-restored backup missing'
    assert (work / 'EXECUTORS_STOPPED').is_file(), 'Executors not drained and stopped'
    schemas()
    before = json.loads((destination / 'fingerprints.json').read_text())
    assert a.a.fingerprint(a.a.b.DBS['overseas']) == before, 'Data drift after backup'
    assert (work / 'delivery-skill-states.private.json').read_text() == previous.skill_states(), 'Skill states drift'
    baseline = data_check.before(u.sql)
    m.private(destination / 'output-before.private.json', baseline)
    overlay = work / 'overseas-migration-overlay.json'
    m.private(overlay, {'services': {'migrate': {'image': identity,
        'build': {'context': str(source), 'dockerfile': 'infra/Dockerfile.backend'}}}})
    config = json.loads((work / 'overseas-compose.private.json').read_text())
    assert json.loads(m.compose(data['overseas'], 'config', '--format', 'json', capture=True)) == config
    after = json.loads(m.compose(data['overseas'], 'config', '--format', 'json', overlay=overlay, capture=True))
    m.same_settings(config, after, ['migrate'])
    assert after['services']['migrate']['image'] == identity
    m.private(work / 'MIGRATION_STARTED', d.MIGRATION_RECOVERY)
    m.compose(data['overseas'], 'run', '--rm', '--no-deps', '--pull', 'never', 'migrate',
              'alembic', '-c', 'alembic.overseas.ini', 'upgrade', d.TARGET_MIGRATION, overlay=overlay)
    installed_schemas()
    data_check.verify(u.sql, baseline)
    m.private(destination / 'fingerprints-after.json', a.a.fingerprint(a.a.b.DBS['overseas']))
    m.private(work / 'MIGRATION_VERIFIED', 'overseas_0022: empty output table added; all old columns/rows unchanged')


previous.preflight = s.preflight = a.preflight = d.preflight = preflight
previous.schemas = s.schemas = a.schemas = d.schemas = schemas
s.installed_schemas = a.installed_schemas = d.installed_schemas = installed_schemas
d.prepare, d.before_switch, d.drain_and_stop = prepare, before_switch, drain_and_stop
main = d.main

if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    m.module('release-retention').managed(main)
