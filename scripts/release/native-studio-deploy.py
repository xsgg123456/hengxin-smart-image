"""Overseas native studio 0.2.32: drained, backed-up, forward-only 0014 -> 0015.

CLI: RELEASE build|prepare|deploy|recover. No Skill installation or domestic/identity restart.
"""
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

spec = importlib.util.spec_from_file_location('native_studio_runtime', Path(__file__).with_name('native-studio-runtime.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
h, m, u, r, verify = s.h, s.m, s.u, s.r, s.verify
BACKUPS = Path('/opt/hengxin-backups')


def deploy(work, source, manifest, image):
    assert not (work / 'DEPLOY_STARTED').exists(), 'Previous attempt requires inspected forward recovery, not replay'
    assert not (work / 'MIGRATION_STARTED').exists(), 'Previous migration requires inspected forward recovery'
    identity = m.image_id(work, image)
    assert (work / 'PREPARED').read_text() == identity, 'Prepared image drift'
    s.schemas(s.OLD_SCHEMA)
    s.previous_version()
    data = json.loads((work / 'topology.json').read_text())
    native = json.loads((work / 'domestic-native.json').read_text())
    assert m.topology() == data and h.domestic_native() == native, 'Topology drift since prepare'
    s.prepared_settings(work, data, identity, source)
    m.assets_safe(source)
    target = Path((work / 'native-target').read_text())
    r.hashes(target.parent, {'files': {n: v for n, v in manifest['files'].items() if n.startswith('backend/')}})
    destination, overlay = BACKUPS / manifest['release'], work / 'overseas-overlay.json'
    assert not destination.exists(), 'Backup destination already exists'
    edge = m.EDGE.read_text()
    h.closed_config(edge)
    m.private(work / 'edge-before.conf', edge)
    m.private(work / 'RECOVERY.txt', 'Keep overseas intake closed. Inspect PHASE, FAILURE.json, '
        'MIGRATION_STARTED, MIGRATION_VERIFIED and queue evidence. Never replay deploy, force-stop unknown '
        'executors, downgrade schema or restore an old database over potentially accepted writes. '
        'After migration begins, require reviewed forward recovery matching the actual schema; do not '
        'blindly restart the previous application. Backup contains the original Compose and native pointers. '
        'Validate source/image/schema, jobs/broker, health/auth and frontend before opening intake. '
        'Domestic and identity must remain unchanged.')
    m.private(work / 'DEPLOY_STARTED', manifest['release'])
    phase = 'close-intake'
    try:
        m.private(work / 'PHASE', phase)
        h.close_edge(edge)
        h.closed()
        m.compose(data['overseas'], 'stop', '-t', '30', 'api')
        phase = 'drain'
        m.private(work / 'PHASE', phase)
        h.drain_and_stop(work)
        phase = 'backup'
        m.private(work / 'PHASE', phase)
        u.backup(work, destination, data['overseas'])
        assert (destination / 'COMPLETE').exists(), 'No verified complete backup'
        m.private(destination / 'edge.conf', edge)
        m.private(destination / 'full-topology.json', data)
        phase = 'migration'
        m.private(work / 'PHASE', phase)
        s.migrate(work, data, identity, image)
        phase = 'switch'
        m.private(work / 'PHASE', phase)
        u.switch_native(target)
        m.compose(data['overseas'], 'up', '-d', '--no-deps', '--no-build', '--pull', 'never',
                  '--wait', '--wait-timeout', '180', 'api', overlay=overlay)
        m.run('systemctl', 'start', *u.UNITS)
    except BaseException as exc:
        s.failure(work, phase, exc, edge, data)
        raise

    finish(work, source, manifest, identity, data, native, target, edge)


def finish(work, source, manifest, identity, data, native, target, edge):
    overlay = work / 'overseas-overlay.json'
    destination = BACKUPS / manifest['release']
    phase = 'verify-installed'
    try:
        m.private(work / 'PHASE', phase)
        s.installed(work, manifest, identity, data, native, target)
        m.run('docker', 'exec', r.PREFIX + 'web-1', 'nginx', '-t')
        m.run('docker', 'exec', r.PREFIX + 'web-1', 'nginx', '-s', 'reload')
        verify.proxy()
        phase = 'publish-frontend'
        m.private(work / 'PHASE', phase)
        m.assets_safe(source)
        r.publish(source)
        verify.frontend(source, manifest)
        assert json.loads((m.APP / 'frontend/package.json').read_text())['version'] == s.VERSION
        s.schemas(s.NEW_SCHEMA)
        h.closed()
        phase = 'open-and-verify'
        m.private(work / 'PHASE', phase)
        m.EDGE.write_text(edge)
        u.reload_edge()
        verify.public()
        verify.frontend(source, manifest)
        for route in s.AUTH_ROUTES:
            assert verify.status(r.ORIGIN + '/api/overseas/v1/' + route) in ('401', '403'), route
        h.resources_unchanged(data, native, {'native': target, 'overlay': overlay})
        s.schemas(s.NEW_SCHEMA)
        for name in ('OVERSEAS_RELEASE.json', 'FRONTEND_RELEASE.json'):
            m.private(m.APP / name, manifest)
        m.private(work / 'verification.json', dict(release=manifest['release'], image=identity,
            frontendVersion=s.VERSION, previousVersion=s.PREVIOUS, migration='0028',
            overseasMigration=s.NEW_SCHEMA, previousOverseasMigration=s.OLD_SCHEMA, backup=str(destination),
            sourceHashes=True, domesticIdentityUnchanged=True, skillsVerified=True, businessDeletion=False))
        m.private(work / 'PHASE', 'complete')
        print('NATIVE_STUDIO_COMPLETE ' + manifest['release'], flush=True)
    except BaseException as exc:
        s.failure(work, phase, exc, edge, data)
        raise


def recover(work, source, manifest, image):
    """Resume only the inspected post-migration/pre-frontend auth-probe failure."""
    assert not (work / 'RECOVERY_STARTED').exists(), 'Recovery requires inspected state, not replay'
    assert (work / 'PHASE').read_text() == 'verify-installed'
    failure = json.loads((work / 'FAILURE.json').read_text())
    assert failure['phase'] == 'verify-installed' and failure['errorType'] == 'AssertionError'
    assert failure['edgeClosed'] and failure['apiStopped'] and failure['migrationStarted']
    assert (work / 'MIGRATION_VERIFIED').read_text() == s.NEW_SCHEMA
    assert (BACKUPS / manifest['release'] / 'COMPLETE').exists()
    assert not (work / 'INSTALLED_VERIFIED').exists() and not (work / 'verification.json').exists()
    s.schemas(s.NEW_SCHEMA)
    s.previous_version()
    identity = m.image_id(work, image)
    assert (work / 'PREPARED').read_text() == identity
    data = json.loads((work / 'topology.json').read_text())
    native = json.loads((work / 'domestic-native.json').read_text())
    target = Path((work / 'native-target').read_text())
    overlay = work / 'overseas-overlay.json'
    assert json.loads(overlay.read_text()) == s.overlay(source, identity)
    actual = m.live(u.API)
    assert not actual['State']['Running'] and actual['Image'] == identity
    assert actual['Mounts'] == data['overseas']['mounts'][u.API]
    # The API is deliberately stopped: topology() lists running containers only.
    assert h.domestic_native() == native
    for baseline in data.values():
        if not isinstance(baseline, dict) or 'ids' not in baseline:
            continue
        for name, expected_id in baseline['ids'].items():
            if name != u.API:
                resource = m.live(name)
                assert resource['Id'] == expected_id and resource['State']['Running'], name
                assert resource['Mounts'] == baseline['mounts'][name], name
        assert all(m.digest(path) == digest for path, digest in baseline['files'].items())
    s.prepared_settings(work, data, identity, source)
    r.hashes(target.parent, {'files': {n: v for n, v in manifest['files'].items() if n.startswith('backend/')}})
    h.closed()
    h.wait_empty(work, 'recovery-idle')
    edge = (work / 'edge-before.conf').read_text()
    assert m.EDGE.read_text() == h.closed_config(edge)
    m.private(work / 'RECOVERY_STARTED', 'Forward continuation of verified 0015; no migration or restore')
    try:
        m.compose(data['overseas'], 'up', '-d', '--no-deps', '--no-build', '--pull', 'never',
                  '--wait', '--wait-timeout', '180', 'api', overlay=overlay)
    except BaseException as exc:
        s.failure(work, 'recovery-api-start', exc, edge, data)
        raise
    finish(work, source, manifest, identity, data, native, target, edge)


def main():
    os.umask(0o077)
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    assert os.geteuid() == 0, 'Production release requires root'
    release, action = sys.argv[1:]
    assert re.fullmatch(r'overseas-20261014-[0-9a-f]{7}', release)
    work = Path('/opt/hengxin-releases') / release
    source, manifest, image = s.validate(work, release)
    if action == 'build':
        m.module('overseas-deploy').build(work, source, image)
    elif action == 'prepare':
        s.prepare(work, source, manifest, image)
    elif action == 'deploy':
        deploy(work, source, manifest, image)
    elif action == 'recover':
        recover(work, source, manifest, image)
    else:
        raise ValueError('Unknown native studio action')


if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release safety assertions')
    spec = importlib.util.spec_from_file_location('release_retention', Path(__file__).with_name('release-retention.py'))
    retention = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(retention)
    retention.managed(main)
