"""0.2.50 -> 0.2.51 full overseas release; preserve both existing schemas.

RELEASE build|prepare|deploy reuses the reviewed full release, isolated backup
restore, bounded drain and fail-closed recovery. Never stop a busy executor or
automatically restore production data. Original-image restoration was cancelled;
this release leaves deleted tasks untouched and requires no repair request.
"""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

spec = importlib.util.spec_from_file_location('delivery_reliability_base',
    Path(__file__).with_name('overseas-studio-sessions-deploy.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
a, d, m, u = s.a, s.d, s.m, s.u
a.BASE_VERSION = d.BASE_VERSION = '0.2.50'
d.TARGET_VERSION = '0.2.51'
d.DOMESTIC_MIGRATION, d.TARGET_MIGRATION = '0032', 'overseas_0021'
# These are the read-only production observations from 2026-10-24. Drift refuses
# preparation; a future release must explicitly rebase this reviewed adapter.
s.FRONTEND_RELEASE = a.BASE_RELEASE = 'overseas-20261024-71ed440'
a.BASE_IMAGE = 'sha256:b1d785fd94bfc8fe5fb7628dcc42f25d2ed6605495d3fad4e6c63c1adb2bf2f1'
a.OVERSEAS_PATHS = {unit: Path('/opt/hengxin-overseas-releases') / a.BASE_RELEASE / 'backend' for unit in u.UNITS}
u.DROP = 'zzzzzzzzzzz-studio-delivery-reliability-20261024.conf'
EXPECTED_COMPOSE_TAIL = [s.GRANT_OVERLAY,
    '/opt/hengxin-releases/' + a.BASE_RELEASE + '/overseas-overlay.json']
TESTS = ['tests/test_studio_sessions.py', 'tests/test_overseas_studio_conversations.py',
    'tests/test_studio_delivery_bridge.py', 'tests/test_studio_formal_delivery.py',
    'tests/test_studio_image_recovery.py', 'tests/test_studio_completion.py',
    'tests/test_studio_native_images.py', 'tests/test_overseas_studio_execution.py']
REQUIRED = {'scripts/release/studio-delivery-reliability-20261024.py',
    'scripts/release/studio-delivery-release-repair.py',
    'scripts/release/studio-delivery-repair-runtime.py',
    'backend/app/overseas/studio/delivery_repair.py',
    *('backend/' + name for name in TESTS)}
s.REQUIRED |= REQUIRED
a.c.REQUIRED |= REQUIRED
d.MIGRATION_RECOVERY = (' No schema migration or Skill installation. Preserve domestic 0032, overseas_0021, '
    'credential broker, full permission bindings and all Skill contents/states. Keep intake closed on failure. '
    'Inspect phase and queues; an application rollback requires a new proven drain and reviewed handling of '
    'any delivery snapshots written by the new runtime. Never restore or downgrade production databases.')
_prepare, _installed, _validate = s.prepare, s.installed, s.validate


def schemas():
    s.check_schema('overseas_0021')
    assert u.sql("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' "
                 "AND table_name='overseas_studio_conversation_deletions'") == '1', 'Session schema missing'


def preflight():
    assert json.loads((m.APP / 'frontend/package.json').read_text())['version'] == d.BASE_VERSION
    for name in ('FRONTEND_RELEASE.json', 'OVERSEAS_RELEASE.json'):
        assert json.loads((m.APP / name).read_text())['release'] == a.BASE_RELEASE, 'Release pointer drift'
    actual = m.live(u.API)
    assert actual['Image'] == a.BASE_IMAGE, 'API image baseline drift'
    assert actual['State']['Running'] and actual['State']['Health']['Status'] == 'healthy'
    assert actual['HostConfig']['Memory'] == d.resources.API_MEMORY
    assert actual['HostConfig']['RestartPolicy']['Name'] == a.a.RESTART
    paths = actual['Config']['Labels']['com.docker.compose.project.config_files'].split(',')
    assert paths[-2:] == EXPECTED_COMPOSE_TAIL, 'Permission/release Compose chain drift'
    s.bindings()
    for unit, root in a.OVERSEAS_PATHS.items():
        a.native_state(unit, root)
        s.native_arguments(unit, root)
        a.pointer(unit, root)
        effective = a.show(unit, 'DropInPaths').split()
        assert effective and all(Path(path).name < u.DROP for path in effective), 'Higher priority loaded override'
        assert all(path.name < u.DROP for path in (a.c.SYSTEMD / (unit + '.service.d')).glob('*.conf')), 'Higher priority unloaded override'
    worker = a.settings(u.UNITS[0])
    assert 'hengxin-codex-auth' in worker['SupplementaryGroups'].split(), 'Broker group missing'
    assert 'OVERSEAS_CODEX_AUTH_BROKER_SOCKET=' + str(a.SOCKET) in worker['Environment'].split(), 'Broker socket config missing'
    a.domestic_native()
    for path in (m.EDGE, d.proxy.inner(m)):
        a.c.a.proxy_baseline(path.read_text())


def skill_states():
    return u.sql("SELECT coalesce(jsonb_agg(to_jsonb(t) ORDER BY t.id),'[]'::jsonb)::text "
                 "FROM overseas_installed_skill_availability t")


def preserve_skill_states(work):
    path = work / 'delivery-skill-states.private.json'
    current = skill_states()
    if path.exists():
        assert path.read_text() == current, 'Production Skill states drift'
    else:
        m.private(path, current)


def prepare(work, source, manifest, image):
    preflight()
    preserve_skill_states(work)
    _prepare(work, source, manifest, image)


def before_switch(work, source, identity, data, destination):
    assert (destination / 'COMPLETE').is_file(), 'Verified isolated-restored backup missing'
    assert (work / 'EXECUTORS_STOPPED').is_file(), 'Executors not drained and stopped'
    schemas()
    before = json.loads((destination / 'fingerprints.json').read_text())
    assert a.a.fingerprint(a.a.b.DBS['overseas']) == before, 'Data drift after backup'
    assert (work / 'delivery-skill-states.private.json').read_text() == skill_states(), 'Production Skill states drift'
    m.private(work / 'SCHEMA_UNCHANGED', 'Domestic 0032 / overseas_0021; all original overseas row hashes unchanged')


def native_install_test(work, source, manifest, identity, target):
    tests = list(TESTS)
    # Include newly delivered fault tests without guessing their names. The full
    # package/manifest hashes bind every discovered test to the reviewed source.
    tests.extend(name.removeprefix('backend/') for name in sorted(manifest['files'])
                 if name.startswith('backend/tests/test_studio_delivery_')
                 and name.endswith('.py') and name.removeprefix('backend/') not in tests)
    with (work / 'native-installation-tests.log').open('w') as log:
        subprocess.run(['docker', 'run', '--rm', '--init', '--network', 'none',
            '--mount', 'type=bind,src=' + str(target) + ',dst=/installed,readonly',
            '--workdir', '/installed', '--entrypoint', '/app/.venv/bin/python',
            '-e', 'APP_ENV=test', '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'PYTHONPATH=/installed',
            identity, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *tests],
            stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)
    m.private(work / 'NATIVE_INSTALL_TESTS.json', s.receipt(work, source, identity, target))


def installed(work, manifest, identity, data, native, target):
    _installed(work, manifest, identity, data, native, target)
    assert (work / 'delivery-skill-states.private.json').read_text() == skill_states(), 'Installed Skill states drift'
    m.private(work / 'DELIVERY_PRESERVATION_VERIFIED', 'Skill contents and all enable/disable rows preserved; no model calls')


def deploy(work, source, manifest, image):
    return s.deploy(work, source, manifest, image)


def validate(work, release):
    source, manifest, image = _validate(work, release)
    assert REQUIRED <= manifest['files'].keys(), 'Delivery release files missing'
    return source, manifest, image


s.preflight = a.preflight = d.preflight = preflight
s.schemas = a.schemas = d.schemas = schemas
s.installed_schemas = a.installed_schemas = d.installed_schemas = schemas
s.native_install_test = native_install_test
d.prepare, d.before_switch, d.installed, d.validate = prepare, before_switch, installed, validate
d.deploy = deploy
main = d.main

if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    m.module('release-retention').managed(main)
