"""Domestic 0032 cutover: drained, restore-tested and forward-only after cleanup."""
import importlib.util
import json
import os
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('retention_runtime', Path(__file__).with_name('retention-management-runtime.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
m, r, gate, n = s.m, s.r, s.gate, s.n
drain, backup, checks = (m.module('retention-management-' + name) for name in ('drain', 'backup', 'verify'))
BACKUPS = Path('/opt/hengxin-backups')


def deploy(work, source, manifest, image):
    assert not (work / 'DEPLOY_STARTED').exists(), 'Inspect recovery state; never replay a cutover'
    assert (work / 'PREPARED').read_text() == m.image_id(work, image)
    data = json.loads((work / 'topology.json').read_text())
    assert s.topology() == data, 'Topology changed after prepare'
    s.baseline()
    old = json.loads((work / 'domestic-compose.private.json').read_text())
    overlay = work / 'domestic-overlay.json'
    new = json.loads(m.compose(data['domestic'], 'config', '--format', 'json', overlay=overlay, capture=True))
    s.same_settings(old, new)
    m.assets_safe(source)
    target = Path((work / 'native-target').read_text())
    r.hashes(target.parent, {'files': {name: value for name, value in manifest['files'].items()
                                    if name.startswith('backend/')}})
    assert r.sql('SELECT paused FROM api_image_channel WHERE id=1') == 'f'
    destination = BACKUPS / manifest['release']
    assert not destination.exists()
    m.private(work / 'DEPLOY_STARTED', manifest['release'])
    phase = 'close-intake'
    try:
        gate.close(work)
        s.p.graceful_stop('api')
        r.sql('UPDATE api_image_channel SET paused=true WHERE id=1')
        phase = 'drain'
        drain.stop(work, source, data)
        phase = 'backup'
        backup.create(work, destination, data, manifest['release'])
        assert (destination / 'COMPLETE').exists()
        phase = 'migration'
        gate.verify_closed()
        m.private(work / 'MIGRATION_STARTED', 'Forward-only 0032; retain pending receipts and cleanup barriers')
        m.compose(data['domestic'], 'run', '--rm', '--no-deps', 'migrate', overlay=overlay)
        assert r.sql('SELECT version_num FROM alembic_version') == '0032'
        backup.verify_after(destination, checks.ADDED)
        checks.migrated()
        phase = 'switch'
        n.switch(work)
        m.compose(data['domestic'], 'up', '-d', '--no-deps', '--no-build', '--pull', 'never',
            '--wait', '--wait-timeout', '180', 'api', 'api-image-worker', 'image-variants', overlay=overlay)
        m.run('systemctl', 'start', n.UNIT)
        r.worker(source / 'scripts/release/image-inputs-worker.py', 'native-verify')
        r.worker(source / 'scripts/release/image-inputs-worker.py', 'api-verify')
        gate.verify_closed()
        phase = 'publish'
        r.publish(source)
        checks.frontend(source)
        s.unchanged(data)
        phase = 'start-cleanup'
        # Persist before starting: objects may be deleted even when the following command fails.
        m.private(work / 'CLEANUP_MAY_HAVE_DELETED', 'Never restore old DB or erase deletion receipts; pause cleanup on failure')
        checks.mark_start(work)
        m.run('systemctl', 'start', n.DELETE, n.RETENTION)
        checks.first_scan(work)
        n.verify(work)
        phase = 'resume-producers'
        m.compose(data['domestic'], 'up', '-d', '--no-deps', '--no-build', '--pull', 'never',
            '--wait', '--wait-timeout', '180', 'outbox', 'api-image-outbox', overlay=overlay)
        s.installed(work, data, image)
        r.sql('UPDATE api_image_channel SET paused=false WHERE id=1')
        phase = 'open-intake'
        gate.open_intake(work)
        s.p.base.public_verify(source)
        s.unchanged(data)
        for name in ('DOMESTIC_RELEASE.json', 'RETENTION_MANAGEMENT_RELEASE.json', 'FRONTEND_RELEASE.json'):
            m.private(m.APP / name, manifest)
        m.private(work / 'VERIFIED', manifest['release'])
    except BaseException as error:
        m.private(work / 'RECOVERY_REQUIRED.json', dict(phase=phase, error=type(error).__name__,
            release=manifest['release'], backup=str(destination),
            note='Keep intake closed. Pause cleanup. Never restore old DB, erase receipts, downgrade schema or restart old consumers.'))
        try:
            gate.close(work)
        except BaseException as gate_error:
            m.private(work / 'GATE_RECOVERY_REQUIRED', type(gate_error).__name__)
        if (work / 'CLEANUP_MAY_HAVE_DELETED').exists():
            for unit in (n.RETENTION, n.DELETE):
                try:
                    n.stop(unit)
                except BaseException as stop_error:
                    m.private(work / (unit + '-STOP_REQUIRED'), type(stop_error).__name__)
        raise


def main():
    os.umask(0o077)
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release assertions')
    release, action = sys.argv[1:]
    work = Path('/opt/hengxin-releases') / release
    source, manifest, image = s.validate(work, release)
    actions = {'build': lambda: m.module('overseas-deploy').build(work, source, image),
        'prepare': lambda: s.prepare(work, source, manifest, image),
        'deploy': lambda: deploy(work, source, manifest, image)}
    if action not in actions:
        raise ValueError('Use build, prepare, deploy; recovery requires inspected state')
    actions[action]()


if __name__ == '__main__':
    if sys.flags.optimize:
        raise RuntimeError('Python -O disables release assertions')
    m.module('release-retention').managed(main)
