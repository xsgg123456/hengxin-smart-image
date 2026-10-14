"""Overseas 0.2.33 hotfix: no migration, Skill installation or business deletion.

CLI: RELEASE build|prepare|deploy. Failed cutovers stay closed for inspected recovery;
never replay deploy or restore a database over potentially accepted business writes.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import time

spec = importlib.util.spec_from_file_location('hotfix_runtime', Path(__file__).with_name('member-release-runtime.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
u, r = m.u, m.r
drain = m.module('member-release-drain')
verify = m.module('member-release-verify')
BACKUPS = Path('/opt/hengxin-backups')
proxy = m.module('overseas-upload-proxy')
resources = m.module('overseas-upload-resources')
DELETING = "SELECT count(*) FROM overseas_task_deletions WHERE status='deleting'"
TARGET_VERSION = '0.2.33'
BASE_VERSION = '0.2.32'


def preflight():
    """Version-specific read-only prerequisites, before prepare or cutover writes."""
    pass

def validate(work, release):
    source = work / 'src'
    manifest = json.loads((source / 'release.json').read_text())
    assert manifest['release'] == release and manifest['frontendVersion'] == TARGET_VERSION
    assert manifest['migration'] == '0028' and manifest['overseasMigration'] == 'overseas_0015'
    assert json.loads((source / 'frontend/package.json').read_text())['version'] == TARGET_VERSION
    r.hashes(source, manifest)
    return source, manifest, 'hengxin-smart-image-backend:' + release

def schemas():
    assert r.sql('SELECT version_num FROM alembic_version') == '0028'
    assert u.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0015'

def domestic_native():
    unit = m.UNITS[0]
    m.run('systemctl', 'is-active', unit)
    pid = int(m.run('systemctl', 'show', unit, '-p', 'MainPID', '--value', capture=True))
    assert pid > 0
    cwd = os.readlink(f'/proc/{pid}/cwd')
    assert cwd == m.run('systemctl', 'show', unit, '-p', 'WorkingDirectory', '--value', capture=True)
    return dict(pid=pid, cwd=cwd)

def evidence(work):
    worker = drain.native_probe(u.UNITS[0], drain.PROBE.format(
        module='app.overseas.execution.worker', queues=['overseas.cli']), work)
    return dict(workers={'overseas': worker}, jobs=u.pending(), deleting=int(u.sql(DELETING)))

def wait_empty(work, label, timeout=180):
    deadline, stable = time.monotonic() + timeout, 0
    while True:
        result = evidence(work)
        # Save every observation, including busy state, for failure recovery inspection.
        m.private(work / (label + '.json'), result)
        empty = drain.idle(result['workers']) and result['jobs'] == result['deleting'] == 0
        stable = stable + 1 if empty else 0
        if stable == 2:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Overseas work not drained; executors remain running, intake stays closed')
        time.sleep(3)

def drain_and_stop(work):
    wait_empty(work, 'drained-before-outbox-stop')
    m.run('systemctl', 'stop', u.UNITS[1])
    wait_empty(work, 'drained-after-outbox-stop')
    m.run('systemctl', 'stop', u.UNITS[0])
    assert u.pending() == int(u.sql(DELETING)) == 0
    m.private(work / 'EXECUTORS_STOPPED', 'Two stable DB/broker checks before and after outbox stop')

def prepared_settings(work, data, identity, source):
    overlay = work / 'overseas-overlay.json'
    expected = resources.overlay(source, identity)
    assert json.loads(overlay.read_text()) == expected, 'Prepared overlay drift'
    before = json.loads((work / 'overseas-compose.private.json').read_text())
    current = json.loads(m.compose(data['overseas'], 'config', '--format', 'json', capture=True))
    assert before == current, 'Prepared Compose baseline drift'
    after = json.loads(m.compose(data['overseas'], 'config', '--format', 'json', overlay=overlay, capture=True))
    resources.same_settings(before, after, m)

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
    assert data['native'][u.UNITS[0]] == data['native'][u.UNITS[1]]
    native = domestic_native()
    result = evidence(work)
    drain.idle(result['workers'])  # Unknown replies abort; known busy work can drain later.
    m.private(work / 'prepare-queues.json', result)
    m.private(work / 'topology.json', data)
    m.private(work / 'domestic-native.json', native)
    for group in m.GROUPS:
        config = json.loads(m.compose(data[group], 'config', '--format', 'json', capture=True))
        m.check_live_config(group, config)
        m.private(work / (group + '-compose.private.json'), config)
    m.private(work / 'overseas-overlay.json', resources.overlay(source, identity))
    prepared_settings(work, data, identity, source)
    target = u.prepare_native(source, manifest['release'])
    r.hashes(target.parent, {'files': {n: h for n, h in manifest['files'].items() if n.startswith('backend/')}})
    m.skills.verify(u, work, target)
    m.private(work / 'native-target', str(target))
    assert m.topology() == data and domestic_native() == native, 'Production topology drift during preparation'
    proxy.prepare(work, source, m)
    m.private(work / 'PREPARED', identity)

def closed_config(original):
    changed, count = re.subn(r'location \^~ /api/overseas/v1/ \{[^{}]*\}',
        'location ^~ /api/overseas/v1/ { return 503; }', original)
    assert count == 1, 'Overseas edge location not uniquely identified'
    return changed

def close_edge(original):
    m.EDGE.write_text(closed_config(original))
    u.reload_edge()

def closed(timeout=30):
    deadline = time.monotonic() + timeout
    while True:
        codes = [verify.status(r.ORIGIN + '/api/overseas/v1/' + path) for path in ('auth/me', 'tasks')]
        if codes == ['503', '503']:
            return
        if time.monotonic() >= deadline:
            raise AssertionError('Overseas public intake is not closed: ' + repr(codes))
        time.sleep(1)

def resources_unchanged(data, native, target):
    current = m.topology()
    for group in ('domestic', 'identity'):
        assert current[group] == data[group], 'Unrelated topology changed: ' + group
    before, after = data['overseas'], current['overseas']
    assert set(before['ids']) == set(after['ids']), 'Overseas resource set changed'
    assert before['mounts'] == after['mounts'], 'Overseas mount drift'
    assert all(after['ids'][name] == identity for name, identity in before['ids'].items() if name != u.API)
    assert all(m.digest(path) == digest for path, digest in before['files'].items()), 'Existing Compose configuration changed'
    assert all(after[key] == before[key] for key in ('project', 'cwd', 'env'))
    assert after['paths'] == [*before['paths'], str(target['overlay'])]
    assert domestic_native() == native, 'Domestic native process changed'
    assert current['native'] == {**data['native'], **{unit: str(target['native']) for unit in u.UNITS}}
    pointers = {str(Path('/etc/systemd/system') / (unit + '.service.d') / u.DROP) for unit in u.UNITS}
    assert {p: h for p, h in current['nativeFiles'].items() if p not in pointers} == {
        p: h for p, h in data['nativeFiles'].items() if p not in pointers}, 'Native config/environment drift'

def installed(work, manifest, identity, data, native, target):
    schemas()
    expected = {n.removeprefix('backend/'): h for n, h in manifest['files'].items() if n.startswith('backend/')}
    assert expected
    actual = m.live(u.API)
    assert actual['State']['Running'] and actual['Image'] == identity
    assert actual['HostConfig']['Memory'] == resources.API_MEMORY, 'Installed API memory drift'
    assert actual['Mounts'] == data['overseas']['mounts'][u.API]
    code = ('import hashlib,json,sys; from pathlib import Path; m=json.loads(sys.argv[1]); '
            'assert all(hashlib.sha256((Path("/app")/n).read_bytes()).hexdigest()==h for n,h in m.items())')
    m.run('docker', 'exec', u.API, 'python', '-c', code, json.dumps(expected))
    for unit in u.UNITS:
        m.run('systemctl', 'is-active', unit)
        assert m.run('systemctl', 'show', unit, '-p', 'WorkingDirectory', '--value', capture=True) == str(target)
        pid = int(m.run('systemctl', 'show', unit, '-p', 'MainPID', '--value', capture=True))
        assert pid > 0 and Path(os.readlink(f'/proc/{pid}/cwd')) == target
    r.hashes(target.parent, {'files': {'backend/' + n: h for n, h in expected.items()}})
    u.wait_worker_ready()
    wait_empty(work, 'installed-idle')
    resources_unchanged(data, native, {'native': target, 'overlay': work / 'overseas-overlay.json'})
    m.skills.verify(u, work, target)
    for port, route in verify.HEALTH.values():
        verify.get(f'http://127.0.0.1:{port}' + route)
    for route in ('auth/me', 'tasks', 'members/applications'):
        assert verify.status('http://127.0.0.1:18018/api/overseas/v1/' + route) in ('401', '403')
    m.private(work / 'INSTALLED_VERIFIED', 'Overseas image/source/native hashes, mounts, Skills and untouched services verified')

def deploy(work, source, manifest, image):
    assert not (work / 'DEPLOY_STARTED').exists(), 'Previous attempt requires inspected recovery, not replay'
    identity = m.image_id(work, image)
    assert (work / 'UPLOAD_CAPACITY_IMAGE_ID').read_text() == identity
    assert (work / 'PREPARED').read_text() == identity
    schemas()
    data = json.loads((work / 'topology.json').read_text())
    native = json.loads((work / 'domestic-native.json').read_text())
    assert m.topology() == data and domestic_native() == native, 'Topology drift since prepare'
    preflight()
    prepared_settings(work, data, identity, source)
    proxy.unchanged(work, m)
    m.assets_safe(source)
    target = Path((work / 'native-target').read_text())
    r.hashes(target.parent, {'files': {n: h for n, h in manifest['files'].items() if n.startswith('backend/')}})
    destination, overlay = BACKUPS / manifest['release'], work / 'overseas-overlay.json'
    assert not destination.exists(), 'Backup destination already exists'
    edge = m.EDGE.read_text()
    closed_config(edge)
    m.private(work / 'edge-before.conf', edge)
    m.private(work / 'RECOVERY.txt', 'Keep overseas edge closed. Inspect PHASE, FAILURE.json and queue evidence. '
        'Do not force-stop unknown executors or replay deploy. After proving jobs, deletion cleanup and broker idle, '
        'a reviewed application recovery may use the original Compose config and native pointers from the verified '
        'backup, then restore frontend entry files and validate before opening edge. Never auto-restore the database; '
        'the dump may predate newly accepted work. Domestic and identity must remain unchanged.')
    m.private(work / 'DEPLOY_STARTED', manifest['release'])
    phase = 'close-intake'
    try:
        m.private(work / 'PHASE', phase)
        close_edge(edge)
        closed()
        m.compose(data['overseas'], 'stop', '-t', '30', 'api')
        phase = 'drain'
        m.private(work / 'PHASE', phase)
        drain_and_stop(work)
        phase = 'backup'
        m.private(work / 'PHASE', phase)
        u.backup(work, destination, data['overseas'])
        assert (destination / 'COMPLETE').exists(), 'No verified complete backup'
        m.private(destination / 'edge.conf', edge)
        m.private(destination / 'full-topology.json', data)
        phase = 'switch'
        m.private(work / 'PHASE', phase)
        u.switch_native(target)
        m.compose(data['overseas'], 'up', '-d', '--no-deps', '--no-build', '--pull', 'never',
                  '--wait', '--wait-timeout', '180', 'api', overlay=overlay)
        m.run('systemctl', 'start', *u.UNITS)
        phase = 'verify-installed'
        m.private(work / 'PHASE', phase)
        installed(work, manifest, identity, data, native, target)
        proxy.install_inner(work, destination, m)
        # Reload only: shared web keeps its identity and resolves the replaced API address.
        m.run('docker', 'exec', r.PREFIX + 'web-1', 'nginx', '-t')
        m.run('docker', 'exec', r.PREFIX + 'web-1', 'nginx', '-s', 'reload')
        verify.proxy()
        phase = 'publish-frontend'
        m.private(work / 'PHASE', phase)
        m.assets_safe(source)
        r.publish(source)
        verify.frontend(source, manifest)
        closed()
        phase = 'open-and-verify'
        m.private(work / 'PHASE', phase)
        m.EDGE.write_text((work / 'upload-edge-after.conf').read_text())
        u.reload_edge()
        verify.public()
        proxy.verify(work, m, verify)
        verify.frontend(source, manifest)
        resources_unchanged(data, native, {'native': target, 'overlay': overlay})
        for name in ('OVERSEAS_RELEASE.json', 'FRONTEND_RELEASE.json'):
            m.private(m.APP / name, manifest)
        m.private(work / 'verification.json', dict(release=manifest['release'], image=identity,
            migration='0028', overseasMigration='overseas_0015', backup=str(destination),
            sourceHashes=True, domesticIdentityUnchanged=True, skillsVerified=True, businessDeletion=False))
        m.private(work / 'PHASE', 'complete')
        print('OVERSEAS_HOTFIX_COMPLETE ' + manifest['release'], flush=True)
    except BaseException as exc:
        # Close admission even after public reopening; newly accepted work forbids executor stops.
        try:
            close_edge(edge)
            closed()
            proxy.restore_inner(work, m)
        finally:
            try:
                m.compose(data['overseas'], 'stop', '-t', '30', 'api', overlay=overlay)
            finally:
                m.private(work / 'FAILURE.json', dict(phase=phase, errorType=type(exc).__name__,
                    recovery='Inspect RECOVERY.txt; no database restore or unknown executor stop'))
        raise

def main():
    os.umask(0o077)
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    assert os.geteuid() == 0, 'Production release requires root'
    release, action = sys.argv[1:]
    assert re.fullmatch(r'overseas-20261014-[0-9a-f]{7}', release)
    work = Path('/opt/hengxin-releases') / release
    source, manifest, image = validate(work, release)
    if action == 'build':
        m.module('overseas-deploy').build(work, source, image)
        resources.test_capacity(work, image, m)
    elif action == 'prepare':
        prepare(work, source, manifest, image)
    elif action == 'deploy':
        deploy(work, source, manifest, image)
    else:
        raise ValueError('Unknown hotfix action')

if __name__ == '__main__':
    spec = importlib.util.spec_from_file_location('release_retention', Path(__file__).with_name('release-retention.py'))
    retention = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(retention)
    retention.managed(main)
