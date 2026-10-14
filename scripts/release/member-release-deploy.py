"""Forward-only coordinated member isolation release. CLI: RELEASE build|prepare|deploy."""
import importlib.util
import json
import os
from pathlib import Path
import re
import sys

spec = importlib.util.spec_from_file_location('member_runtime', Path(__file__).with_name('member-release-runtime.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
drain = m.module('member-release-drain')
backup = m.module('member-release-backup')
verify = m.module('member-release-verify')
BACKUPS = Path('/opt/hengxin-backups')


def cutover(work, source, manifest, identity, data, targets, destination):
    drain.drain_and_stop(work, source, data)
    backup.create(work, destination, data, manifest['release'])
    assert (destination / 'COMPLETE').exists(), 'No verified complete backup'
    m.private(work / 'MIGRATION_STARTED', 'Forward-only: no automatic downgrade or old-runtime restore')
    for group in ('domestic', 'overseas'):
        m.compose(data[group], 'run', '--rm', '--no-deps', '--pull', 'never', 'migrate',
                  overlay=work / (group + '-overlay.json'))
    assert m.r.sql('SELECT version_num FROM alembic_version') == '0028'
    assert m.u.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0014'
    # Compare full business records while all writers are still stopped.
    backup.verify_after(destination)
    m.r.switch_native(Path(targets['domestic']))
    m.u.switch_native(Path(targets['overseas']))
    for group in ('identity', 'domestic', 'overseas'):
        m.compose(data[group], 'up', '-d', '--no-deps', '--no-build', '--pull', 'never',
                  '--wait', '--wait-timeout', '180', *m.GROUPS[group]['services'],
                  overlay=work / (group + '-overlay.json'))
    m.run('systemctl', 'start', *m.UNITS)
    verify.installed(work, source, manifest, identity, data, targets)
    # Existing Nginx containers keep their config/mounts; reload resolves replaced API addresses.
    m.run('docker', 'exec', m.r.PREFIX + 'web-1', 'nginx', '-t')
    m.run('docker', 'exec', m.r.PREFIX + 'web-1', 'nginx', '-s', 'reload')
    verify.proxy()
    m.assets_safe(source)
    m.r.publish(source)
    verify.frontend(source, manifest)
    verify.closed()


def deploy(work, source, manifest, image):
    assert not (work / 'MIGRATION_STARTED').exists(), 'Previous attempt needs reviewed forward recovery'
    identity = m.image_id(work, image)
    assert (work / 'PREPARED').read_text() == identity
    assert m.r.sql('SELECT version_num FROM alembic_version') == '0027'
    assert m.u.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0013'
    data = json.loads((work / 'topology.json').read_text())
    assert m.topology() == data, 'Container/config/native drift since prepare'
    m.prepared_settings(work, data)
    m.assets_safe(source)
    targets = json.loads((work / 'native-targets.json').read_text())
    destination = BACKUPS / manifest['release']
    assert not destination.exists(), 'Backup destination already exists'
    edge = m.EDGE.read_text()
    m.closed_config(edge)  # Validate the exact layout before any production mutation.
    m.private(work / 'edge-before.conf', edge)
    try:
        m.close_edge(edge)
        verify.closed()
        m.stop_apis(data)
        cutover(work, source, manifest, identity, data, targets, destination)
        m.EDGE.write_text(edge)
        m.u.reload_edge()
        verify.public()
        for name in ('MEMBER_RELEASE.json', 'FRONTEND_RELEASE.json', 'OVERSEAS_RELEASE.json'):
            m.private(m.APP / name, manifest)
        m.private(work / 'verification.json', dict(release=manifest['release'], image=identity,
            migration='0028', overseasMigration='overseas_0014', backup=str(destination),
            sourceHashes=True, allThreeAPIs=True, skills=14, historicalCleanup=False))
        print('MEMBER_RELEASE_COMPLETE ' + manifest['release'], flush=True)
    except BaseException:
        # No executor stop in recovery: a failure after opening could include newly accepted work.
        try:
            m.close_edge(edge)
        finally:
            m.stop_apis(data, work)
        print('ALL_API_INTAKE_CLOSED_FORWARD_RECOVERY_REQUIRED', flush=True)
        raise


def main():
    os.umask(0o077)
    assert not sys.flags.optimize, 'Python -O disables release safety assertions'
    assert os.geteuid() == 0, 'Production release requires root'
    release, action = sys.argv[1:3]
    assert re.fullmatch(r'overseas-20261013-[0-9a-f]{7}', release)
    work = Path('/opt/hengxin-releases') / release
    source, manifest, image = m.validate(work, release)
    if action == 'build':
        m.module('overseas-deploy').build(work, source, image)
    elif action == 'prepare':
        m.prepare(work, source, manifest, image)
    elif action == 'deploy':
        deploy(work, source, manifest, image)
    else:
        raise ValueError('Unknown release action')


if __name__ == '__main__':
    spec = importlib.util.spec_from_file_location('release_retention', Path(__file__).with_name('release-retention.py'))
    retention = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(retention)
    retention.managed(main)
