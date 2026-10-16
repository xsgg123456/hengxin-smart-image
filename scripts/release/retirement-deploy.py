"""Irreversible domestic 0030 cutover; every failure closes intake without old-code rollback."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import time

spec = importlib.util.spec_from_file_location('retirement_runtime', Path(__file__).with_name('retirement-runtime.py'))
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)
m, r = n.m, n.r
gate, drain, backup = (m.module(name) for name in ('domestic-gate', 'retirement-drain', 'retirement-backup'))


def verify(work, source, data, image):
    identity = m.image_id(work, image)
    for service in r.SERVICES:
        live = m.live(m.container('domestic', service))
        assert live['Image'] == identity and live['State']['Running']
        assert live['State'].get('Health', {}).get('Status', 'healthy') == 'healthy'
        assert n.container_policy(live) == data['containerLimits'][service], 'Container resource/security policy changed'
    config = json.loads(m.compose(data['domestic'], 'config', '--format', 'json',
                                 overlay=work / 'domestic-overlay.json', capture=True))
    m.check_live_config('domestic', config)
    assert str(config['services']['api']['environment'].get('CLI_RETENTION_ENABLED')).lower() == 'true'
    n.n.verify(work)
    m.module('retirement-verify').cleanup_ready(work)
    probe = m.module('member-release-drain')
    deadline = time.monotonic() + 60
    while True:
        try:
            probe.native_probe(n.n.UNIT, probe.PROBE.format(module='app.worker.celery_app', queues=['celery']), work)
            break
        except AssertionError:
            assert time.monotonic() < deadline, 'New native worker unavailable'
            time.sleep(2)
    r.worker(source / 'scripts/release/image-inputs-worker.py', 'api-verify')
    n.unchanged_other_groups(data)
    m.run('curl', '--max-time', '15', '--retry', '10', '--retry-delay', '2', '--retry-connrefused',
          '-fsS', '-o', '/dev/null', 'http://127.0.0.1:18008/api/v1/health/ready')
    assert r.sql('SELECT version_num FROM alembic_version') == '0030'


def public_verify(source):
    for origin in ('http://127.0.0.1:18080', r.ORIGIN):
        for path in ('/api/v1/health/ready', '/api/overseas/v1/health/ready', '/api/identity/v1/config'):
            m.run('curl', '--max-time', '15', '-fsS', '-o', '/dev/null', origin + path)
        assert m.run('curl', '--max-time', '15', '-fsS', origin + '/', capture=True) == (
            source / 'frontend/dist/index.html').read_text().strip()


def deploy(work, source, manifest, image):
    assert (work / 'PREPARED').read_text() == m.image_id(work, image)
    data = json.loads((work / 'topology.json').read_text())
    assert n.topology() == data, 'Live topology changed after prepare'
    n.baseline()
    old = json.loads((work / 'domestic-compose.private.json').read_text())
    new = json.loads(m.compose(data['domestic'], 'config', '--format', 'json',
                             overlay=work / 'domestic-overlay.json', capture=True))
    m.same_settings(old, new, [*r.SERVICES, 'migrate'])
    m.assets_safe(source)
    destination = Path('/opt/hengxin-backups') / manifest['release']
    assert not destination.exists()
    assert r.sql('SELECT paused FROM api_image_channel WHERE id=1') == 'f'
    phase = 'close-intake'
    try:
        gate.close(work)
        m.private(work / 'INTAKE_CLOSED', 'Both domestic proxy layers verified 503')
        m.compose(data['domestic'], 'stop', '-t', '30', 'api')
        phase = 'drain'
        drain.stop(work, source, data)
        r.sql('UPDATE api_image_channel SET paused=true WHERE id=1')
        phase = 'backup'
        backup.create(work, destination, data, manifest['release'], source)
        phase = 'migration'
        gate.verify_closed()
        m.private(work / 'IRREVERSIBLE_MIGRATION_STARTED', 'Never start pre-0030 code after this point')
        m.compose(data['domestic'], 'run', '--rm', '--no-deps', 'migrate', overlay=work / 'domestic-overlay.json')
        assert r.sql('SELECT version_num FROM alembic_version') == '0030'
        backup.verify_after(destination)
        phase = 'switch'
        n.n.switch(work)
        m.compose(data['domestic'], 'up', '-d', '--no-deps', '--wait', '--wait-timeout', '180',
                  *r.SERVICES, overlay=work / 'domestic-overlay.json')
        m.run('systemctl', 'start', *n.n.UNITS)
        verify(work, source, data, image)
        gate.verify_closed()
        phase = 'publish'
        r.publish(source)
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
        m.private(work / 'RECOVERY_REQUIRED.json', dict(phase=phase, error=type(error).__name__,
            release=manifest['release'], backup=str(destination),
            note='Keep intake closed. No automatic DB restore or old-code restart. Inspect schema and live PIDs.'))
        try:
            gate.close(work)
        except BaseException as gate_error:
            m.private(work / 'GATE_RECOVERY_REQUIRED', type(gate_error).__name__)
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
        raise ValueError('Use build, prepare, deploy; failed irreversible migrations require state-based recovery')


if __name__ == '__main__':
    m.module('release-retention').managed(main)
