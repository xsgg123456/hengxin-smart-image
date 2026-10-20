"""API simplification: unchanged 0031 schema/history, three-service cutover."""
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

spec = importlib.util.spec_from_file_location('retry_deploy', Path(__file__).with_name('api-retry-deploy.py'))
previous = importlib.util.module_from_spec(spec)
spec.loader.exec_module(previous)
m, r, gate = previous.m, previous.r, previous.gate
SERVICES, DATABASE = previous.SERVICES, previous.DATABASE
topology, unchanged = previous.topology, previous.unchanged
graceful_stop, verify = previous.graceful_stop, previous.verify
columns, fingerprints, cycles = previous.columns, previous.fingerprints, previous.new_cycles
BACKUPS = previous.BACKUPS
handoff = m.module('api-simple-handoff')


def validate(work, release):
    assert re.fullmatch(r'domestic-api-simple-20261020-[0-9a-f]{7}', release)
    source = work / 'src'
    manifest = json.loads((source / 'release.json').read_text())
    assert manifest['release'] == release and manifest['frontendVersion'] == '0.2.45'
    assert manifest['migration'] == '0031' and manifest['overseasMigration'] == 'overseas_0019'
    assert {'scripts/release/api-simple-deploy.py', 'scripts/release/api-simple-handoff.py',
            'scripts/release/api-retry-deploy.py',
            'backend/migrations/versions/0031_api_retry_policy.py'} <= manifest['files'].keys()
    r.hashes(source, manifest)
    return source, manifest, 'hengxin-smart-image-backend:' + release


def baseline():
    assert r.sql('SELECT version_num FROM alembic_version') == '0031'
    assert m.u.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0019'
    assert json.loads((m.APP / 'frontend/package.json').read_text())['version'] == '0.2.44'


def same_settings(old, new):
    # The retry policy and graceful-stop settings are already installed in 0.2.44.
    m.same_settings(old, new, list(SERVICES))


def prepare(work, source, manifest, image):
    assert not (work / 'PREPARED').exists()
    identity = m.image_id(work, image)
    baseline()
    m.assets_safe(source)
    data = topology()
    old = json.loads(m.compose(data['domestic'], 'config', '--format', 'json', capture=True))
    m.check_live_config('domestic', old)
    overlay = {'services': {service: dict(image=identity, build={
        'context': str(source), 'dockerfile': 'infra/Dockerfile.backend'}) for service in SERVICES}}
    m.private(work / 'domestic-overlay.json', overlay)
    new = json.loads(m.compose(data['domestic'], 'config', '--format', 'json',
                              overlay=work / 'domestic-overlay.json', capture=True))
    same_settings(old, new)
    m.private(work / 'domestic-compose.private.json', old)
    m.private(work / 'topology.json', data)
    gate.save(work)
    assert topology() == data, 'Topology drift during prepare'
    m.private(work / 'PREPARED', identity)


def backup(work, destination, data, release):
    count = cycles()
    previous.backup(work, destination, data, release)
    assert cycles() == count, 'Historical retry cycles changed during backup'
    m.private(destination / 'retry-cycles.json', count)
    m.private(destination / 'protected.json', handoff.protected(previous))


def verify_preserved(destination):
    assert r.sql('SELECT version_num FROM alembic_version') == '0031'
    projection = json.loads((destination / 'columns.json').read_text())
    assert columns(DATABASE) == projection, 'Schema columns changed without a migration'
    assert fingerprints(DATABASE, projection) == json.loads(
        (destination / 'fingerprints.json').read_text()), 'Existing API rows changed'
    assert cycles() == json.loads((destination / 'retry-cycles.json').read_text()), 'Historical retry cycles changed'


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
        r.sql('UPDATE api_image_channel SET paused=true WHERE id=1')
        handoff.drain(work, previous)
        phase = 'backup'
        backup(work, destination, data, manifest['release'])
        gate.verify_closed()
        verify_preserved(destination)
        phase = 'switch'
        m.compose(data['domestic'], 'up', '-d', '--no-deps', '--wait', '--wait-timeout', '180',
            'api', 'api-image-worker', overlay=work / 'domestic-overlay.json')
        # No producer is running and no broker work may mutate the preserved snapshot.
        assert not m.live(m.container('domestic', 'api-image-outbox'))['State']['Running']
        handoff.wait_idle(work, previous)
        verify_preserved(destination)
        gate.verify_closed()
        m.private(work / 'NEW_POLICY_MAY_BE_ACTIVE', 'Outbox can resume durable work; retain current executors')
        m.compose(data['domestic'], 'up', '-d', '--no-deps', '--wait', '--wait-timeout', '180',
            'api-image-outbox', overlay=work / 'domestic-overlay.json')
        verify(work, data, image)
        handoff.verify_protected(previous, json.loads((destination / 'protected.json').read_text()))
        phase = 'publish'
        r.publish(source)
        assert (m.APP / 'frontend/package.json').read_bytes() == (source / 'frontend/package.json').read_bytes()
        r.sql('UPDATE api_image_channel SET paused=false WHERE id=1')
        phase = 'open-intake'
        gate.open_intake(work)
        previous.base.public_verify(source)
        unchanged(data)
        for name in ('DOMESTIC_RELEASE.json', 'API_SIMPLE_RELEASE.json', 'FRONTEND_RELEASE.json'):
            m.private(m.APP / name, manifest)
        m.private(work / 'VERIFIED', manifest['release'])
    except BaseException as error:
        m.private(work / 'RECOVERY_REQUIRED.json', dict(phase=phase, error=type(error).__name__,
            release=manifest['release'], backup=str(destination),
            note='Keep intake closed. Retain executors and late results. No automatic database restore or old-code restart.'))
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
