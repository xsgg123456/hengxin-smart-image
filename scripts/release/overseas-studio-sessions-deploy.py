"""Pinned 0.2.49 -> 0.2.50 full-source release; migrate only overseas_0020 -> 0021.

CLI: RELEASE build|prepare|deploy. Reuse drained, isolated-restore-verified backup
and fail-closed cutover. No automatic downgrade or production database restore.
"""
import importlib.util
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import time
from uuid import UUID

spec = importlib.util.spec_from_file_location('sessions_release_base', Path(__file__).with_name('overseas-archive-deletion-deploy.py'))
a = importlib.util.module_from_spec(spec)
spec.loader.exec_module(a)
d, m, u = a.d, a.m, a.u
data_check = m.module('overseas-studio-sessions-data')
a.BASE_VERSION = d.BASE_VERSION = '0.2.49'
d.TARGET_VERSION = '0.2.50'
d.DOMESTIC_MIGRATION, d.TARGET_MIGRATION = '0032', 'overseas_0021'
d.RELEASE_PATTERN = r'overseas-20261024-[0-9a-f]{7}'
FRONTEND_RELEASE = 'domestic-record-filters-20261022-2f08f8f'
a.BASE_RELEASE = 'overseas-20261022-6897b6e'
a.BASE_IMAGE = 'sha256:a49cedf7f9c3f1b191d5ca716813645f47fb05ee12aff1ac429f82fc18057a18'
a.DOMESTIC_PATHS = {unit: Path('/opt/hengxin-native-releases') / FRONTEND_RELEASE / 'backend'
                    for unit in a.a.DOMESTIC_UNITS}
a.OVERSEAS_PATHS = {
    u.UNITS[0]: Path('/opt/hengxin-overseas-releases/studio-delivery-20261023/backend'),
    u.UNITS[1]: Path('/opt/hengxin-overseas-releases') / a.BASE_RELEASE / 'backend',
}
u.DROP = 'zzzzzzzzzz-studio-sessions-20261024.conf'
GRANT_OVERLAY = '/opt/hengxin-releases/member-grant-20261023/grant-overlay.json'
OWNER_KEY, GRANT_KEY = 'OVERSEAS_SKILL_TOGGLE_OWNER_ID', 'OVERSEAS_FULL_ACCESS_MEMBER_IDS'
REQUIRED = {'scripts/release/overseas-studio-sessions-deploy.py',
            'scripts/release/overseas-studio-sessions-data.py',
            'backend/migrations/overseas/versions/0021_studio_sessions.py',
            'backend/tests/test_studio_sessions.py',
            'backend/tests/studio_sessions_helpers.py',
            'backend/tests/test_studio_sessions_migration.py',
            'backend/tests/test_overseas_studio_conversations.py'}
a.c.REQUIRED |= REQUIRED
d.MIGRATION_RECOVERY = (' Add named sessions, nullable ownership and archive source snapshots; preserve all old rows. '
    'After MIGRATION_STARTED keep intake closed and inspect schema, queues and runtime for reviewed forward recovery. '
    'Never downgrade or restore production databases. Preserve domestic 0032, identity, broker, complete Compose '
    'environment, full-access members, Skill owner and arbitrary current Skill states.')
_prepare, _installed = a.prepare, a.installed
_prepared_settings, _prepare_native = d.prepared_settings, u.prepare_native
_deploy, _validate = d.deploy, d.validate

def bindings():
    entries = m.live(u.API)['Config']['Env']
    result = {}
    for key in (OWNER_KEY, GRANT_KEY):
        values = [entry.split('=', 1)[1] for entry in entries if entry.startswith(key + '=')]
        assert len(values) == 1, 'Missing or duplicate production permission binding'
        result[key] = values[0]
    owner = result[OWNER_KEY]
    assert str(UUID(owner)) == owner and UUID(owner).int, 'Invalid existing Skill owner'
    members = json.loads(result[GRANT_KEY])
    assert isinstance(members, list) and members and len(members) == len(set(members)), 'Invalid full-access members'
    assert all(isinstance(value, str) and str(UUID(value)) == value and UUID(value).int for value in members)
    return result

def check_schema(revision):
    assert d.r.sql('SELECT version_num FROM alembic_version') == '0032', 'Domestic schema drift'
    assert u.sql('SELECT version_num FROM overseas_alembic_version') == revision, 'Overseas schema drift'
    assert u.sql(a.c.a.USAGE_COLUMN) == '0', 'Unexpected usage column'
    for name in ('overseas_studio_material_visibility', 'overseas_archive_events',
                 'overseas_archive_deletions', 'overseas_installed_skill_availability'):
        assert u.sql("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_name='" + name + "'") == '1'

def schemas():
    check_schema('overseas_0020')

def installed_schemas():
    check_schema('overseas_0021')

def bounded_sql(query, timeout):
    return m.run('docker', 'exec', u.PG, 'psql', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres',
                 '-d', 'hengxin_overseas', '-Atc', query, capture=True, timeout=timeout)

def evidence(work, timeout=45):
    deadline = time.monotonic() + timeout
    def remaining():
        value = deadline - time.monotonic()
        assert value > 0, 'Queue evidence deadline reached; do not stop executors'
        return value
    pid = int(m.run('systemctl', 'show', u.UNITS[0], '-p', 'MainPID', '--value',
                    capture=True, timeout=remaining()))
    assert pid > 0, 'Worker PID missing'
    cwd = Path(os.readlink(f'/proc/{pid}/cwd'))
    configured = m.run('systemctl', 'show', u.UNITS[0], '-p', 'WorkingDirectory', '--value',
                       capture=True, timeout=remaining())
    assert cwd == Path(configured), 'Worker running/configured directory differs'
    env = dict(os.fsdecode(item).split('=', 1) for item in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0') if item)
    env['PYTHONPATH'] = str(cwd)
    code = d.drain.PROBE.format(module='app.overseas.execution.worker', queues=['overseas.cli'])
    probe = subprocess.run([str(cwd / '.venv/bin/python'), '-c', code], cwd=cwd, env=env,
                           capture_output=True, text=True, timeout=remaining())
    if probe.returncode:
        m.private(work / 'sessions-worker-probe.private.log', probe.stderr)
    assert probe.returncode == 0, 'Worker unavailable; inspect private evidence, do not force-stop'
    jobs = int(bounded_sql("SELECT count(*) FROM overseas_jobs WHERE status NOT IN "
        "('succeeded','failed','cancelled') OR (process_id IS NOT NULL AND NOT process_exited)", remaining()))
    table = bounded_sql("SELECT count(*) FROM information_schema.tables WHERE table_schema='public' "
                        "AND table_name='" + data_check.TABLE + "'", remaining())
    deletion_tables = ['overseas_task_deletions', 'overseas_archive_deletions']
    if table == '1':
        deletion_tables.append(data_check.TABLE)
    deleting = int(bounded_sql('SELECT ' + '+'.join("(SELECT count(*) FROM " + name + " WHERE status='deleting')"
                                                    for name in deletion_tables), remaining()))
    remaining()
    return dict(workers={'overseas': json.loads(probe.stdout)}, jobs=jobs, deleting=deleting)

def wait_empty(work, label, timeout=600):
    deadline, stable = time.monotonic() + timeout, 0
    while True:
        left = deadline - time.monotonic()
        assert left > 0, 'Drain deadline reached; intake stays closed, no forced stop'
        result = evidence(work, timeout=min(45, left))
        m.private(work / (label + '.json'), result)
        empty = d.drain.idle(result['workers']) and result['jobs'] == result['deleting'] == 0
        stable = stable + 1 if empty else 0
        assert time.monotonic() < deadline, 'Drain deadline reached; no forced stop'
        if stable == 2:
            return
        time.sleep(min(3, max(0, deadline - time.monotonic())))

def native_arguments(unit, root):
    pid = int(a.show(unit, 'MainPID'))
    assert pid > 0 and Path(os.readlink(f'/proc/{pid}/cwd')) == root, 'Actual native process drift'
    argv = [os.fsdecode(x) for x in Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0') if x]
    if unit == u.UNITS[0]:
        assert argv[:8] == [str(root / '.venv/bin/python'), str(root / '.venv/bin/celery'),
            '-A', 'app.overseas.execution.worker:celery_app', 'worker', '--pool=prefork',
            '--concurrency=5', '--loglevel=INFO'], 'Worker command/pool/capacity drift'
        assert len(argv) == 10 and argv[8].startswith('--hostname=overseas@') and argv[9] == '--queues=overseas.cli'
    else:
        assert argv == [str(root / '.venv/bin/python'), '-m', 'app.overseas.execution.outbox'], 'Outbox command drift'
    return argv

def broker_state():
    result = a.native_state(a.BROKER, a.DOMESTIC_AUTH)
    socket, auth = a.SOCKET.stat(), a.AUTH.stat()
    assert stat.S_ISSOCK(socket.st_mode), 'Broker socket missing'
    assert (socket.st_uid, socket.st_gid, stat.S_IMODE(socket.st_mode)) == (1001, 986, 0o660)
    assert stat.S_ISREG(auth.st_mode) and not a.AUTH.is_symlink(), 'Broker credentials are not a regular file'
    # Broker service Group is hengxin-codex-auth; atomic credential refresh now
    # writes that group while retaining owner-only 0600. Never read its contents.
    assert (auth.st_uid, auth.st_gid, stat.S_IMODE(auth.st_mode)) == (1001, 986, 0o600)
    result['socket'] = [socket.st_ino, socket.st_uid, socket.st_gid, stat.S_IMODE(socket.st_mode)]
    result['authMetadata'] = [str(a.AUTH), auth.st_uid, auth.st_gid, stat.S_IMODE(auth.st_mode)]
    result['source'] = {str(path.relative_to(a.DOMESTIC_AUTH)): m.digest(path)
                        for path in sorted((a.DOMESTIC_AUTH / 'app').rglob('*.py'))}
    assert 'app/execution/credential_broker.py' in {name.replace('\\', '/') for name in result['source']}
    return result

def preflight():
    assert json.loads((m.APP / 'frontend/package.json').read_text())['version'] == d.BASE_VERSION
    for name, release in [('FRONTEND_RELEASE.json', FRONTEND_RELEASE), ('OVERSEAS_RELEASE.json', a.BASE_RELEASE)]:
        assert json.loads((m.APP / name).read_text())['release'] == release, 'Release pointer drift'
    actual = m.live(u.API)
    assert actual['Image'] == a.BASE_IMAGE and actual['State']['Running'] and actual['State']['Health']['Status'] == 'healthy'
    assert actual['HostConfig']['Memory'] == d.resources.API_MEMORY
    assert actual['HostConfig']['RestartPolicy']['Name'] == a.a.RESTART
    paths = actual['Config']['Labels']['com.docker.compose.project.config_files'].split(',')
    assert paths[-1] == GRANT_OVERLAY, 'Full-access grant Compose chain drift'
    bindings()
    for unit, root in a.OVERSEAS_PATHS.items():
        a.native_state(unit, root)
        native_arguments(unit, root)
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

def prepare_native(source, release):
    # Worker-only delivery fix and outbox have different baselines; both must have
    # the same pinned dependency declarations before sharing the new full source.
    for root in a.OVERSEAS_PATHS.values():
        for name in ('pyproject.toml', 'uv.lock'):
            assert (source / 'backend' / name).read_bytes() == (root / name).read_bytes(), 'Native dependency drift'
    return _prepare_native(source, release)

def prepared_settings(work, data, identity, source):
    saved = json.loads((work / 'sessions-bindings.private.json').read_text())
    assert bindings() == saved, 'Production permission bindings drift'
    before = json.loads((work / 'overseas-compose.private.json').read_text())
    assert all(before['services']['api'].get('environment', {}).get(key) == value
               for key, value in saved.items()), 'Compose/live permission binding mismatch'
    # The inherited overlay changes image/build/memory/restart only; no environment
    # normalization is permitted. The entire existing Compose chain remains intact.
    _prepared_settings(work, data, identity, source)

def receipt(work, source, identity, target):
    return dict(image=identity, manifest=m.digest(source / 'release.json'), target=str(target))

def native_install_test(work, source, manifest, identity, target):
    tests = ['tests/test_studio_sessions.py', 'tests/test_overseas_studio_conversations.py']
    # Test exact installed files in a disposable, networkless container with no
    # production configuration, credentials, data mounts or host dependency link.
    with (work / 'native-installation-tests.log').open('w') as log:
        subprocess.run(['docker', 'run', '--rm', '--init', '--network', 'none',
            '--mount', 'type=bind,src=' + str(target) + ',dst=/installed,readonly',
            '--workdir', '/installed', '--entrypoint', '/app/.venv/bin/python',
            '-e', 'APP_ENV=test', '-e', 'PYTHONDONTWRITEBYTECODE=1', '-e', 'PYTHONPATH=/installed',
            identity, '-m', 'pytest', '-q', '-p', 'no:cacheprovider', *tests],
            stdout=log, stderr=subprocess.STDOUT, check=True, timeout=600)
    m.private(work / 'NATIVE_INSTALL_TESTS.json', receipt(work, source, identity, target))

def prepare(work, source, manifest, image):
    assert source == work / 'src' and not (work / 'PREPARED').exists(), 'Unexpected/repeated preparation'
    preflight()
    current = bindings()
    path = work / 'sessions-bindings.private.json'
    if path.exists():
        assert json.loads(path.read_text()) == current, 'Permission bindings changed during retry'
    else:
        m.private(path, current)
    _prepare(work, source, manifest, image)
    target = Path((work / 'native-target').read_text())
    native_install_test(work, source, manifest, m.image_id(work, image), target)

def migrate(work, source, identity, data, destination):
    assert (destination / 'COMPLETE').is_file(), 'Verified isolated-restored backup missing'
    assert (work / 'EXECUTORS_STOPPED').is_file(), 'Executors not drained and stopped'
    schemas()
    before = json.loads((destination / 'fingerprints.json').read_text())
    assert a.a.fingerprint(a.a.b.DBS['overseas']) == before, 'Data drift after backup'
    baseline = data_check.before(u.sql)
    m.private(destination / 'sessions-before.private.json', baseline)
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
    m.private(work / 'MIGRATION_VERIFIED', 'overseas_0021: all original values retained; exact new ownership/source values verified')

def installed(work, manifest, identity, data, native, target):
    _installed(work, manifest, identity, data, native, target)
    assert bindings() == json.loads((work / 'sessions-bindings.private.json').read_text()), 'Installed permission binding drift'
    for unit in u.UNITS:
        native_arguments(unit, target)
    m.private(work / 'SESSIONS_PRESERVATION_VERIFIED', 'Complete permissions, native argv, broker and full package hashes preserved')

def deploy(work, source, manifest, image):
    identity = m.image_id(work, image)
    target = Path((work / 'native-target').read_text())
    assert json.loads((work / 'NATIVE_INSTALL_TESTS.json').read_text()) == receipt(work, source, identity, target), 'Installed tests receipt drift'
    _deploy(work, source, manifest, image)

def validate(work, release):
    source, manifest, image = _validate(work, release)
    assert REQUIRED <= manifest['files'].keys(), 'Missing sessions release files'
    return source, manifest, image


a.preflight = d.preflight = preflight
a.broker_state = broker_state
a.schemas = d.schemas = schemas
a.installed_schemas = d.installed_schemas = installed_schemas
u.prepare_native = prepare_native
d.prepare, d.prepared_settings, d.before_switch = prepare, prepared_settings, migrate
d.installed, d.deploy, d.validate = installed, deploy, validate
d.evidence, d.wait_empty = evidence, wait_empty
main = d.main

if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    m.module('release-retention').managed(main)
