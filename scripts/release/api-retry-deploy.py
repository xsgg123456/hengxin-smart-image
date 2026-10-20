"""0031 API retry cutover, retaining native/foreign runtimes and failing closed."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

spec = importlib.util.spec_from_file_location('domestic_deploy', Path(__file__).with_name('domestic-deploy.py'))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
m, r, gate = base.m, base.r, base.gate
b = m.module('member-release-backup')
probe = m.module('member-release-drain')
SERVICES = ('api', 'api-image-worker', 'api-image-outbox')
SETTINGS = dict(API_IMAGE_REQUEST_TIMEOUT_SECONDS='300', API_IMAGE_DOWNLOAD_TIMEOUT_SECONDS='60',
    API_IMAGE_LEASE_SECONDS='600', API_IMAGE_SEND_INTERVAL_SECONDS='5', API_IMAGE_MAX_INFLIGHT='10',
    API_IMAGE_FAILURE_THRESHOLD='5', API_IMAGE_COOLDOWN_SECONDS='60')
DATABASE = b.DBS['domestic']
PENDING = """SELECT (SELECT count(*) FROM api_image_tasks WHERE state NOT IN ('succeeded','failed','partial_failed'))
 + (SELECT count(*) FROM api_image_items WHERE state NOT IN ('succeeded','failed')
    OR lease_token IS NOT NULL OR lease_until IS NOT NULL)
 + (SELECT count(*) FROM api_image_attempts WHERE state='running')
 + (SELECT count(*) FROM api_image_channel WHERE item_id IS NOT NULL)
 + (SELECT count(*) FROM api_edit_turns WHERE status IN ('queued','running','cancelling'))"""
BACKUPS = Path('/opt/hengxin-backups')


def validate(work, release):
    assert re.fullmatch(r'domestic-api-retry-20261020-[0-9a-f]{7}', release)
    source = work / 'src'
    manifest = json.loads((source / 'release.json').read_text())
    assert manifest['release'] == release and manifest['frontendVersion'] == '0.2.44'
    assert manifest['migration'] == '0031' and manifest['overseasMigration'] == 'overseas_0019'
    assert 'backend/migrations/versions/0031_api_retry_policy.py' in manifest['files']
    r.hashes(source, manifest)
    return source, manifest, 'hengxin-smart-image-backend:' + release


def baseline():
    assert r.sql('SELECT version_num FROM alembic_version') == '0030'
    assert m.u.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0019'
    assert json.loads((m.APP / 'frontend/package.json').read_text())['version'] == '0.2.43'


def topology():
    data = m.topology()
    units = (*m.UNITS, 'hengxin-domestic-deletions', 'hengxin-retention', 'hengxin-codex-auth')
    data['nativeProcesses'] = {}
    for unit in units:
        pid = m.run('systemctl', 'show', unit, '-p', 'MainPID', '--value', capture=True)
        assert int(pid) > 0
        proc = Path('/proc') / pid
        data['nativeProcesses'][unit] = dict(pid=pid, cwd=os.readlink(proc / 'cwd'),
            argv=m.digest(proc / 'cmdline'), environment=m.digest(proc / 'environ'))
        for key in ('FragmentPath', 'DropInPaths', 'EnvironmentFiles'):
            for path in m.run('systemctl', 'show', unit, '-p', key, '--value', capture=True).split():
                if path.startswith('/'):
                    data['nativeFiles'][path] = m.digest(path)
    data['images'] = {group: {name: m.live(name)['Image'] for name in data[group]['ids']}
                      for group in m.GROUPS}
    return data


def unchanged(data):
    current = topology()
    assert current['nativeProcesses'] == data['nativeProcesses'], 'Native processes changed'
    assert current['nativeFiles'] == data['nativeFiles'], 'Native auth/policy changed'
    for group in ('overseas', 'identity'):
        assert current[group] == data[group] and current['images'][group] == data['images'][group]
    for name, identity in data['domestic']['ids'].items():
        if name not in {m.container('domestic', service) for service in SERVICES}:
            assert current['domestic']['ids'].get(name) == identity, 'Unrelated domestic container changed'
            assert current['images']['domestic'][name] == data['images']['domestic'][name]
    assert m.u.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0019'


def same_settings(old, new):
    expected = json.loads(json.dumps(old))
    for service in SERVICES:
        expected['services'][service].setdefault('environment', {}).update(SETTINGS)
        expected['services'][service]['stop_grace_period'] = '11m0s'
    m.same_settings(expected, new, [*SERVICES, 'migrate'])


def prepare(work, source, manifest, image):
    assert not (work / 'PREPARED').exists()
    identity = m.image_id(work, image)
    baseline()
    m.assets_safe(source)
    data = topology()
    old = json.loads(m.compose(data['domestic'], 'config', '--format', 'json', capture=True))
    m.check_live_config('domestic', old)
    overlay = {'services': {service: dict(image=identity, build={
        'context': str(source), 'dockerfile': 'infra/Dockerfile.backend'}) for service in (*SERVICES, 'migrate')}}
    for service in SERVICES:
        overlay['services'][service].update(environment=SETTINGS, stop_grace_period='660s')
    m.private(work / 'domestic-overlay.json', overlay)
    new = json.loads(m.compose(data['domestic'], 'config', '--format', 'json',
                              overlay=work / 'domestic-overlay.json', capture=True))
    same_settings(old, new)
    m.private(work / 'domestic-compose.private.json', old)
    m.private(work / 'topology.json', data)
    gate.save(work)
    assert topology() == data, 'Topology drift during prepare'
    m.private(work / 'PREPARED', identity)


def wait_empty(work, timeout=660):
    deadline, stable = time.monotonic() + timeout, 0
    while True:
        remaining = deadline - time.monotonic()
        assert remaining > 0, 'API work busy/unknown; no force stop'
        evidence = json.loads(m.run('docker', 'exec', m.container('domestic', 'api-image-worker'), 'python', '-c',
            probe.PROBE.format(module='app.modules.api_image_edits.celery_app', queues=['api_image_edits']),
            capture=True, timeout=remaining))
        remaining = deadline - time.monotonic()
        assert remaining > 0, 'Drain deadline exceeded'
        pending = int(m.run('docker', 'exec', DATABASE[0], 'psql', '-v', 'ON_ERROR_STOP=1',
            '-U', DATABASE[1], '-d', DATABASE[2], '-Atc', PENDING, capture=True, timeout=remaining))
        stable = stable + 1 if probe.idle({'api': evidence}) and pending == 0 else 0
        m.private(work / 'api-drain.json', dict(worker=evidence, pending=pending))
        if stable == 2:
            return
        time.sleep(min(3, max(0, deadline - time.monotonic())))


def graceful_stop(service, timeout=660):
    name = m.container('domestic', service)
    # -1 prevents daemon SIGKILL; client timeout fails closed without killing unknown requests.
    m.run('docker', 'stop', '--timeout=-1', name, timeout=timeout)
    assert not m.live(name)['State']['Running'], 'Service did not exit: ' + service


def drain(work, data):
    wait_empty(work)
    graceful_stop('api-image-outbox')
    wait_empty(work)
    graceful_stop('api-image-worker')
    assert r.sql(PENDING) == '0'
    m.private(work / 'EXECUTORS_STOPPED', 'API queue/broker/durable work idle; native services retained')


def columns(database):
    rows = b.query(database, "SELECT table_name,column_name FROM information_schema.columns "
        "WHERE table_schema='public' ORDER BY table_name,ordinal_position").splitlines()
    result = {}
    for row in rows:
        table, column = row.split('|')
        assert re.fullmatch(r'[a-z][a-z0-9_]*', table) and re.fullmatch(r'[a-z][a-z0-9_]*', column)
        result.setdefault(table, []).append(column)
    return result


def fingerprints(database, projection):
    # Preserve old API columns; exclude native heartbeat/cleanup tables that remain live.
    result = {}
    for table, fields in projection.items():
        if not table.startswith('api_') or table == 'api_worker_heartbeats':
            continue
        names = ','.join('"' + field + '"' for field in fields)
        result[table] = b.query(database, "SELECT count(*)||':'||md5(coalesce(string_agg(md5(to_jsonb(t)::text),'' "
            f'ORDER BY to_jsonb(t)::text),\'\')) FROM (SELECT {names} FROM "{table}") t')
    return result


def backup(work, destination, data, release):
    assert (work / 'EXECUTORS_STOPPED').exists()
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    projection = columns(DATABASE)
    before = fingerprints(DATABASE, projection)
    m.private(destination / 'columns.json', projection)
    m.private(destination / 'fingerprints.json', before)
    m.private(destination / 'topology.json', data)
    for path in {*data['domestic']['files'], *data['nativeFiles']}:
        b.save_file(destination, path)
    for relative in ('frontend/package.json', 'frontend/dist/index.html', 'frontend/dist/index.html.gz'):
        if (m.APP / relative).exists():
            b.save_file(destination, m.APP / relative)
    for path in m.APP.glob('*RELEASE.json'):
        b.save_file(destination, path)
    for name in ('edge-before.conf', 'web-before.conf', 'domestic-compose.private.json'):
        shutil.copyfile(work / name, destination / name)
    target = destination / 'domestic.dump'
    b.dump(DATABASE, target)
    previous = b.fingerprint
    try:
        b.fingerprint = lambda database: fingerprints(database, projection)
        b.restore_check(DATABASE, target, before, release, 'domestic')
    finally:
        b.fingerprint = previous
    assert fingerprints(DATABASE, projection) == before, 'API rows changed during backup'
    b.secure_tree(destination)
    m.private(destination / 'COMPLETE', 'Full dump restored offline; API old-column rows match')


def verify_migration(destination):
    before = json.loads((destination / 'columns.json').read_text())
    after = columns(DATABASE)
    assert set(before) <= set(after), 'Migration removed tables'
    assert all(set(fields) <= set(after[table]) for table, fields in before.items()), 'Migration removed columns'
    assert fingerprints(DATABASE, before) == json.loads((destination / 'fingerprints.json').read_text()), 'Existing API rows changed'
    assert new_cycles() == 0, 'Migration reopened historical cycles'


def new_cycles():
    return int(r.sql("SELECT count(*) FROM api_image_items WHERE retry_policy_version='bounded-v2' AND retry_cycle_id IS NOT NULL"))


def verify(work, data, image):
    for service in SERVICES:
        live = m.live(m.container('domestic', service))
        assert live['Image'] == m.image_id(work, image) and live['State']['Running']
        assert live['State'].get('Health', {}).get('Status', 'healthy') == 'healthy'
        env = dict(value.split('=', 1) for value in live['Config']['Env'])
        assert all(env.get(key) == value for key, value in SETTINGS.items())
        assert live['Config']['StopTimeout'] == 660
    config = json.loads(m.compose(data['domestic'], 'config', '--format', 'json',
        overlay=work / 'domestic-overlay.json', capture=True))
    m.check_live_config('domestic', config)
    r.worker(work / 'src/scripts/release/image-inputs-worker.py', 'api-verify')
    m.run('docker', 'exec', m.container('domestic', 'api-image-worker'), 'python', '-c',
        'from app.modules.api_image_edits.celery_app import celery_app as c; '
        'assert c.conf.broker_transport_options["visibility_timeout"] >= 900')
    assert r.sql('SELECT version_num FROM alembic_version') == '0031'
    unchanged(data)


def deploy(work, source, manifest, image):
    assert (work / 'PREPARED').read_text() == m.image_id(work, image)
    data = json.loads((work / 'topology.json').read_text())
    assert topology() == data
    baseline()
    old = json.loads((work / 'domestic-compose.private.json').read_text())
    new = json.loads(m.compose(data['domestic'], 'config', '--format', 'json',
        overlay=work / 'domestic-overlay.json', capture=True))
    same_settings(old, new)
    m.assets_safe(source)
    assert r.sql('SELECT paused FROM api_image_channel WHERE id=1') == 'f'
    destination = BACKUPS / manifest['release']
    assert not destination.exists()
    phase = 'close-intake'
    try:
        gate.close(work)
        graceful_stop('api')
        phase = 'drain'
        drain(work, data)
        r.sql('UPDATE api_image_channel SET paused=true WHERE id=1')
        phase = 'backup'
        backup(work, destination, data, manifest['release'])
        phase = 'migration'
        gate.verify_closed()
        m.compose(data['domestic'], 'run', '--rm', '--no-deps', 'migrate', overlay=work / 'domestic-overlay.json')
        assert r.sql('SELECT version_num FROM alembic_version') == '0031'
        verify_migration(destination)
        phase = 'switch'
        m.compose(data['domestic'], 'up', '-d', '--no-deps', '--wait', '--wait-timeout', '180',
            *SERVICES, overlay=work / 'domestic-overlay.json')
        verify(work, data, image)
        gate.verify_closed()
        phase = 'publish'
        r.publish(source)
        # Set before unpause: background outbox can admit pending work even while HTTP is closed.
        m.private(work / 'NEW_POLICY_MAY_BE_ACTIVE', 'Never restart pre-0031 consumers automatically')
        r.sql('UPDATE api_image_channel SET paused=false WHERE id=1')
        phase = 'open-intake'
        gate.open_intake(work)
        base.public_verify(source)
        unchanged(data)
        for name in ('DOMESTIC_RELEASE.json', 'API_RETRY_RELEASE.json', 'FRONTEND_RELEASE.json'):
            m.private(m.APP / name, manifest)
        m.private(work / 'VERIFIED', manifest['release'])
    except BaseException as error:
        m.private(work / 'RECOVERY_REQUIRED.json', dict(phase=phase, error=type(error).__name__,
            release=manifest['release'], backup=str(destination),
            note='Keep intake closed. Retain new executors and late results. No automatic database restore or old-code restart.'))
        try:
            gate.close(work)
        except BaseException as gate_error:
            m.private(work / 'GATE_RECOVERY_REQUIRED', type(gate_error).__name__)
        raise


def main():
    os.umask(0o077)
    release, action = sys.argv[1:3]
    work = Path('/opt/hengxin-releases') / release
    source, manifest, image = validate(work, release)
    actions = {'build': lambda: m.module('overseas-deploy').build(work, source, image),
               'prepare': lambda: prepare(work, source, manifest, image),
               'deploy': lambda: deploy(work, source, manifest, image)}
    if action not in actions:
        raise ValueError('Use build, prepare or deploy; recovery requires inspected state')
    actions[action]()


if __name__ == '__main__':
    m.module('release-retention').managed(main)
