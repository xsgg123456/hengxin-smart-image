"""No-migration API/frontend/native cutover; preserve policy and fail closed."""
import importlib.util
import json
import os
from pathlib import Path
import sys

spec = importlib.util.spec_from_file_location('record_runtime', Path(__file__).with_name('domestic-record-filters-runtime.py'))
s = importlib.util.module_from_spec(spec)
spec.loader.exec_module(s)
m, r, gate, n = s.m, s.r, s.gate, s.n
drain, checks = m.module('retention-management-drain'), m.module('domestic-record-filters-verify')
cleanup = m.module('retention-management-verify')
BACKUPS = Path('/opt/hengxin-backups')


def deploy(work, source, manifest, image):
    assert not (work / 'DEPLOY_STARTED').exists(), 'Inspect recovery state; never replay a cutover'
    assert (work / 'PREPARED').read_text() == m.image_id(work, image)
    data = json.loads((work / 'topology.json').read_text())
    assert s.topology() == data, 'Topology changed after prepare'
    s.baseline()
    overlay = work / 'domestic-overlay.json'
    old = json.loads((work / 'domestic-compose.private.json').read_text())
    new = json.loads(m.compose(data['domestic'], 'config', '--format', 'json', overlay=overlay, capture=True))
    s.same_settings(old, new)
    m.assets_safe(source)
    assert r.sql('SELECT paused FROM api_image_channel WHERE id=1') == 'f'
    destination = BACKUPS / manifest['release']
    assert not destination.exists()
    assert int(r.sql(drain.CLI)) >= 0 and int(r.sql(drain.VARIANTS)) >= 0
    m.private(work / 'DEPLOY_STARTED', manifest['release'])
    phase = 'close-intake'
    try:
        gate.close(work)
        s.p.graceful_stop('api')
        r.sql('UPDATE api_image_channel SET paused=true WHERE id=1')
        phase = 'drain'
        drain.stop(work, source, data)
        phase = 'backup'
        checks.backup(work, destination, data, manifest['release'])
        assert (destination / 'COMPLETE').exists()
        gate.verify_closed()
        checks.preserved(destination)
        phase = 'switch-native'
        n.switch(work, destination)
        phase = 'switch-api'
        m.compose(data['domestic'], 'up', '-d', '--no-deps', '--no-build', '--pull', 'never',
            '--wait', '--wait-timeout', '180', 'api', overlay=overlay)
        s.schemas()
        checks.routes()
        checks.preserved(destination)
        phase = 'publish'
        r.publish(source)
        checks.frontend(source)
        gate.verify_closed()
        phase = 'resume-consumers'
        s.start_existing(data, s.CONSUMERS)
        m.run('systemctl', 'start', n.UNIT)
        n.ready(work)
        r.worker(source / 'scripts/release/image-inputs-worker.py', 'api-verify')
        # Native directories change; actual argv semantics, env and policy stay pinned.
        m.private(work / 'CLEANUP_MAY_HAVE_DELETED', 'Cleanup restart can change files and durable receipts')
        cleanup.mark_start(work)
        m.run('systemctl', 'start', n.DELETE, n.RETENTION)
        cleanup.first_scan(work)
        s.start_existing(data, s.PRODUCERS)
        s.installed(work, data, image)
        r.sql('UPDATE api_image_channel SET paused=false WHERE id=1')
        phase = 'open-intake'
        gate.open_intake(work)
        s.p.base.public_verify(source)
        s.installed(work, data, image)
        for name in ('DOMESTIC_RELEASE.json', 'RECORD_FILTERS_RELEASE.json', 'FRONTEND_RELEASE.json'):
            m.private(m.APP / name, manifest)
        m.private(work / 'VERIFIED', manifest['release'])
    except BaseException as error:
        m.private(work / 'RECOVERY_REQUIRED.json', dict(phase=phase, error=type(error).__name__,
            release=manifest['release'], backup=str(destination),
            note='Keep intake closed. Inspect saved topology and phase; original consumer containers/native directories are retained. '
                 'Never restore old DB, downgrade schema, clear queues or force-stop unknown work.'))
        try:
            gate.close(work)
        except BaseException as gate_error:
            m.private(work / 'GATE_RECOVERY_REQUIRED', type(gate_error).__name__)
        try:
            r.sql('UPDATE api_image_channel SET paused=true WHERE id=1')
        except BaseException as pause_error:
            m.private(work / 'CHANNEL_PAUSE_REQUIRED', type(pause_error).__name__)
        # Early failures can leave the old scanners alive, before the restart marker.
        for unit in (n.DELETE, n.RETENTION):
            try:
                n.old.stop(unit)
            except BaseException as stop_error:
                m.private(work / (unit + '.STOP_REQUIRED'), type(stop_error).__name__)
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
