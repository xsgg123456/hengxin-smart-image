"""Domestic 0.2.37 release. Failure preserves closed intake and recovery evidence."""
import importlib.util
import json
import os
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('domestic_runtime', Path(__file__).with_name('domestic-runtime.py'))
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)
m, r = n.m, n.r
gate, drain, backup = (m.module('domestic-' + name) for name in ('gate', 'drain', 'backup'))


def verify(work, source, data, image):
    identity = m.image_id(work, image)
    for service in r.SERVICES:
        live = m.live(m.container('domestic', service))
        assert live['Image'] == identity and live['State']['Running']
        assert live['State'].get('Health', {}).get('Status', 'healthy') == 'healthy'
    helper = source / 'scripts/release/image-inputs-worker.py'
    r.worker(helper, 'native-verify')
    r.worker(helper, 'api-verify')
    assert m.run('systemctl', 'show', n.UNIT, '-p', 'WorkingDirectory', '--value', capture=True) == (work / 'native-target').read_text()
    assert n.native_policy() == json.loads((work / 'native-policy.json').read_text())
    n.verify_deletions(work)
    m.module('domestic-verify').deletion_ready(work)
    n.unchanged_other_groups(data)
    m.run('curl', '--max-time', '15', '--retry', '10', '--retry-delay', '2', '--retry-connrefused',
          '-fsS', '-o', '/dev/null', 'http://127.0.0.1:18008/api/v1/health/ready')
    assert r.sql('SELECT version_num FROM alembic_version') == '0029'
    assert m.u.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0016'


def public_verify(source):
    for origin in ('http://127.0.0.1:18080', r.ORIGIN):
        for path in ('/api/v1/health/ready', '/api/overseas/v1/health/ready', '/api/identity/v1/config'):
            m.run('curl', '--max-time', '15', '-fsS', '-o', '/dev/null', origin + path)
        actual = m.run('curl', '--max-time', '15', '-fsS', origin + '/', capture=True)
        assert actual == (source / 'frontend/dist/index.html').read_text().strip(), 'Frontend entry differs'


def deploy(work, source, manifest, image):
    assert (work / 'PREPARED').read_text() == m.image_id(work, image)
    data = json.loads((work / 'topology.json').read_text())
    assert m.topology() == data, 'Live topology changed after prepare'
    assert n.native_policy() == json.loads((work / 'native-policy.json').read_text())
    before = json.loads((work / 'domestic-compose.private.json').read_text())
    new = json.loads(m.compose(data['domestic'], 'config', '--format', 'json',
                             overlay=work / 'domestic-overlay.json', capture=True))
    m.same_settings(before, new, [*r.SERVICES, 'migrate'])
    m.assets_safe(source)
    destination = Path('/opt/hengxin-backups') / manifest['release']
    assert not destination.exists()
    assert r.sql('SELECT version_num FROM alembic_version') == '0028'
    assert r.sql('SELECT paused FROM api_image_channel WHERE id=1') == 'f'
    phase = 'close-intake'
    try:
        gate.close(work)
        m.private(work / 'INTAKE_CLOSED', 'Both domestic proxy layers verified 503')
        m.compose(data['domestic'], 'stop', '-t', '30', 'api')
        phase = 'drain'
        drain.stop(work, source, data)
        # No generation remains. Preserve this channel value in the exact backup.
        r.sql('UPDATE api_image_channel SET paused=true WHERE id=1')
        phase = 'backup'
        backup.create(work, destination, data, manifest['release'])
        phase = 'migration'
        gate.verify_closed()
        m.compose(data['domestic'], 'run', '--rm', '--no-deps', 'migrate', overlay=work / 'domestic-overlay.json')
        assert r.sql('SELECT version_num FROM alembic_version') == '0029'
        backup.verify_after(destination)
        phase = 'switch'
        n.switch_native(work)
        m.compose(data['domestic'], 'up', '-d', '--no-deps', '--wait', '--wait-timeout', '180',
                  *r.SERVICES, overlay=work / 'domestic-overlay.json')
        m.run('systemctl', 'enable', '--now', n.DELETE_UNIT)
        verify(work, source, data, image)
        gate.verify_closed()
        phase = 'publish'
        r.publish(source)
        assert (m.APP / 'frontend/package.json').read_bytes() == (source / 'frontend/package.json').read_bytes()
        r.sql('UPDATE api_image_channel SET paused=false WHERE id=1')
        phase = 'open-intake'
        gate.open_intake(work)
        public_verify(source)
        n.unchanged_other_groups(data)
        for name in ('DOMESTIC_RELEASE.json', 'FRONTEND_RELEASE.json'):
            m.private(m.APP / name, manifest)
        m.private(work / 'VERIFIED', manifest['release'])
        print('DEPLOY_COMPLETE ' + manifest['release'], flush=True)
    except BaseException as error:
        # Never stop active executors or restore DB after admission may have reopened.
        m.private(work / 'RECOVERY_REQUIRED.json', dict(phase=phase, error=type(error).__name__,
            release=manifest['release'], backup=str(destination),
            note='Keep domestic intake closed. Inspect queues, current units and schema before recovery.'))
        try:
            gate.close(work)
        except BaseException as gate_error:
            m.private(work / 'GATE_RECOVERY_REQUIRED', type(gate_error).__name__)
            print('DOMESTIC_GATE_REQUIRES_OPERATOR_INSPECTION', flush=True)
        print('DOMESTIC_RECOVERY_REQUIRED_NO_EXECUTOR_FORCE_STOP', flush=True)
        raise


def main():
    os.umask(0o077)
    release, action = sys.argv[1:3]
    work = Path('/opt/hengxin-releases') / release
    source, manifest, image = n.validate(work, release)
    if action == 'build':
        m.module('overseas-deploy').build(work, source, image)
    elif action == 'prepare':
        n.prepare(work, source, manifest, image)
    elif action == 'deploy':
        deploy(work, source, manifest, image)
    else:
        raise ValueError('Use build, prepare or deploy; failed deployments require state-based recovery')


if __name__ == '__main__':
    m.module('release-retention').managed(main)
