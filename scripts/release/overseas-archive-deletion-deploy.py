"""0.2.42 archive deletion cutover, preserving the installed credential broker.

Only overseas_0018 -> overseas_0019 is migrated; failures stay closed.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import stat
import sys

spec = importlib.util.spec_from_file_location('archive_deletion_base', Path(__file__).with_name('overseas-studio-ux-deploy.py'))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
d, c = a.d, a.c
m, u, r = d.m, d.u, d.r
drain, resources, proxy = d.drain, d.resources, d.proxy
BASE_VERSION = d.BASE_VERSION = '0.2.41'
d.TARGET_VERSION, d.TARGET_MIGRATION = '0.2.42', 'overseas_0019'
BASE_RELEASE = 'overseas-20261019-77ab69f'
BASE_IMAGE = 'sha256:24012e456da28a6a1e4b4c25d0875acdb05ed9a04a6ebe07bbeedec7987d15fe'
DOMESTIC_AUTH = Path('/opt/hengxin-native-releases/domestic-codex-auth-20261019/backend')
DOMESTIC_OLD = Path('/opt/hengxin-native-releases/domestic-retire-20261016-5d5d073/backend')
DOMESTIC_PATHS = dict(zip(a.DOMESTIC_UNITS, (DOMESTIC_AUTH, DOMESTIC_OLD, DOMESTIC_OLD)))
OVERSEAS_PATHS = {u.UNITS[0]: Path('/opt/hengxin-overseas-releases/overseas-codex-auth-20261019/backend'),
                  u.UNITS[1]: Path('/opt/hengxin-overseas-releases') / BASE_RELEASE / 'backend'}
BROKER = 'hengxin-codex-auth'
SOCKET = Path('/run/hengxin-codex-auth/broker.sock')
AUTH = Path('/home/codex/auth/auth.json')
u.DROP = 'zzzzz-archive-deletion-20261019.conf'
TABLE = 'overseas_archive_deletions'
TABLE_EXISTS = "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='" + TABLE + "'"
REQUIRED = {'scripts/release/overseas-archive-deletion-deploy.py',
    'backend/migrations/overseas/versions/0019_archive_deletion.py',
    'backend/app/overseas/archives/deletion.py', 'backend/app/overseas/archives/cleanup.py', 'backend/tests/test_overseas_archive_deletion.py',
    'backend/app/execution/credential_broker_client.py', 'backend/app/execution/managed_credentials.py'}
c.REQUIRED |= REQUIRED
d.MIGRATION_RECOVERY = (' Only overseas_archive_deletions is added. After MIGRATION_STARTED keep intake closed '
    'and inspect schema, queues and runtime before reviewed forward recovery. Never downgrade or restore '
    'databases automatically. Domestic, identity and the credential broker must remain unchanged.')


def show(unit, key):
    return m.run('systemctl', 'show', unit, '-p', key, '--value', capture=True)


def settings(unit):
    return {key: show(unit, key) for key in ('Environment', 'EnvironmentFiles', 'SupplementaryGroups',
        'User', 'Group', 'UMask', 'NoNewPrivileges', 'ProtectSystem', 'ReadWritePaths')}


def native_state(unit, expected):
    result = c.native_state(unit, expected)
    result['settings'] = settings(unit)
    return result


def broker_state():
    result = native_state(BROKER, DOMESTIC_AUTH)
    socket = SOCKET.stat()
    assert stat.S_ISSOCK(socket.st_mode), 'Broker socket missing'
    result['socket'] = [socket.st_ino, socket.st_uid, socket.st_gid, stat.S_IMODE(socket.st_mode)]
    auth = AUTH.stat()
    assert stat.S_ISREG(auth.st_mode) and not AUTH.is_symlink()
    assert (auth.st_uid, auth.st_gid, stat.S_IMODE(auth.st_mode)) == (1001, 1001, 0o600)
    assert (socket.st_uid, socket.st_gid, stat.S_IMODE(socket.st_mode)) == (1001, 986, 0o660)
    result['authMetadata'] = [str(AUTH), auth.st_uid, auth.st_gid, stat.S_IMODE(auth.st_mode)]
    result['source'] = {str(p.relative_to(DOMESTIC_AUTH)): m.digest(p)
                        for p in sorted((DOMESTIC_AUTH / 'app').rglob('*.py'))}
    assert 'app/execution/credential_broker.py' in {key.replace('\\', '/') for key in result['source']}
    return result


def domestic_native():
    return {**{unit: native_state(unit, path) for unit, path in DOMESTIC_PATHS.items()}, BROKER: broker_state()}


def check_schema(revision, count):
    a.check_schema(revision, '1')
    assert u.sql(TABLE_EXISTS) == count, 'Archive deletion schema drift'


def schemas():
    check_schema('overseas_0018', '0')


def installed_schemas():
    check_schema('overseas_0019', '1')


def pointer(unit, target):
    old = str(OVERSEAS_PATHS[unit])
    command = re.fullmatch(r'\{ path=[^;]+ ; argv\[\]=(.+?) ; ignore_errors=(?:yes|no) \}',
                          c.normalize_exec_start(show(unit, 'ExecStart')))
    assert command, 'Unrecognized native command'
    argv = command.group(1)
    assert argv.startswith(old + '/.venv/bin/'), 'Unexpected native executable'
    expected = 'app.overseas.execution.worker:celery_app' if unit == u.UNITS[0] else 'app.overseas.execution.outbox'
    assert expected in argv, 'Unexpected native module'
    return '[Service]\nWorkingDirectory=' + str(target) + '\nExecStart=\nExecStart=' + argv.replace(old + '/', str(target) + '/') + '\n'


def preflight():
    assert json.loads((m.APP / 'frontend/package.json').read_text())['version'] == BASE_VERSION
    for name in ('FRONTEND_RELEASE.json', 'OVERSEAS_RELEASE.json'):
        assert json.loads((m.APP / name).read_text())['release'] == BASE_RELEASE, 'Release baseline drift'
    actual = m.live(u.API)
    assert actual['Image'] == BASE_IMAGE, 'Overseas image baseline drift'
    assert actual['State']['Running'] and actual['State']['Health']['Status'] == 'healthy'
    assert actual['HostConfig']['Memory'] == resources.API_MEMORY
    assert actual['HostConfig']['RestartPolicy']['Name'] == a.RESTART
    for unit, path in OVERSEAS_PATHS.items():
        native_state(unit, path)
        pointer(unit, path)
        folder = c.SYSTEMD / (unit + '.service.d')
        effective = show(unit, 'DropInPaths').split()
        assert effective and all(Path(p).name < u.DROP for p in effective), 'Higher priority override'
        assert all(p.name < u.DROP for p in folder.glob('*.conf')), 'Unloaded higher priority override'
    worker = settings(u.UNITS[0])
    assert 'hengxin-codex-auth' in worker['SupplementaryGroups'].split()
    assert 'OVERSEAS_CODEX_AUTH_BROKER_SOCKET=' + str(SOCKET) in worker['Environment'].split()
    domestic_native()
    for path in (m.EDGE, proxy.inner(m)):
        c.a.proxy_baseline(path.read_text())


def switch_native(target):
    before = {unit: settings(unit) for unit in u.UNITS}
    bodies = {unit: pointer(unit, target) for unit in u.UNITS}
    for unit, body in bodies.items():
        path = c.SYSTEMD / (unit + '.service.d') / u.DROP
        assert not path.exists(), 'Release override already exists'
        m.private(path, body)
    m.run('systemctl', 'daemon-reload')
    assert {unit: settings(unit) for unit in u.UNITS} == before, 'Native environment/group drift'
    for unit in u.UNITS:
        assert show(unit, 'WorkingDirectory') == str(target)


def prepare(work, source, manifest, image):
    assert not (work / 'PREPARED').exists()
    identity = m.image_id(work, image)
    assert (work / 'UPLOAD_CAPACITY_IMAGE_ID').read_text() == identity
    schemas()
    assert json.loads((m.APP / 'frontend/package.json').read_text())['version'] == BASE_VERSION
    preflight()
    m.assets_safe(source)
    data = m.topology()
    assert data['overseas']['env'], 'Explicit overseas Compose env file required for backup'
    assert data['native'] | {k: str(v) for k, v in OVERSEAS_PATHS.items()} == data['native'], 'Native baseline drift'
    native = domestic_native()
    result = d.evidence(work)
    drain.idle(result['workers'])  # Unknown replies abort; known busy work can drain later.
    m.private(work / 'prepare-queues.json', result)
    m.private(work / 'topology.json', data)
    m.private(work / 'domestic-native.json', native)
    m.private(work / 'overseas-native-settings.json', {unit: settings(unit) for unit in u.UNITS})
    for group in m.GROUPS:
        config = json.loads(m.compose(data[group], 'config', '--format', 'json', capture=True))
        m.check_live_config(group, config)
        m.private(work / (group + '-compose.private.json'), config)
    m.private(work / 'overseas-overlay.json', resources.overlay(source, identity))
    d.prepared_settings(work, data, identity, source)
    target = u.prepare_native(source, manifest['release'])
    r.hashes(target.parent, {'files': {n: h for n, h in manifest['files'].items() if n.startswith('backend/')}})
    m.skills.verify(u, work, target)
    m.private(work / 'native-target', str(target))
    assert m.topology() == data and domestic_native() == native, 'Production topology drift during preparation'
    proxy.prepare(work, source, m)
    m.private(work / 'PREPARED', identity)

def migrate(work, source, identity, data, destination):
    assert (destination / 'COMPLETE').is_file(), 'No verified complete backup'
    assert (work / 'EXECUTORS_STOPPED').is_file(), 'Executors were not drained and stopped'
    schemas()
    before_rows = json.loads((destination / 'fingerprints.json').read_text())
    assert a.fingerprint(a.b.DBS['overseas']) == before_rows, 'Data drift after backup'
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
    after_rows = a.fingerprint(a.b.DBS['overseas'])
    assert set(after_rows) - set(before_rows) == {TABLE}, 'Unexpected new tables'
    assert all(after_rows.get(k) == v for k, v in before_rows.items()), 'Existing business rows changed'
    d.m.private(destination / 'fingerprints-after.json', after_rows)
    d.m.private(work / 'MIGRATION_VERIFIED', 'overseas_0019: archive deletion only; original rows unchanged')


_installed = d.installed


def installed(work, manifest, identity, data, native, target):
    assert {unit: settings(unit) for unit in u.UNITS} == json.loads((work / 'overseas-native-settings.json').read_text())
    for unit in u.UNITS:
        path = c.SYSTEMD / (unit + '.service.d') / u.DROP
        assert str(path) in show(unit, 'DropInPaths').split()
        assert str(target) in show(unit, 'ExecStart')
    _installed(work, manifest, identity, data, native, target)


d.domestic_native, d.preflight, d.prepare = domestic_native, preflight, prepare
d.schemas, d.installed_schemas = schemas, installed_schemas
d.before_switch, d.installed, u.switch_native = migrate, installed, switch_native
main = d.main

if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    m.module('release-retention').managed(main)
