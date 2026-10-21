"""Forward-only recovery of the inspected bec8dd7 native-readiness timeout."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

RELEASE = 'domestic-retention-20261021-bec8dd7'


def load(work):
    path = work / 'src/scripts/release/retention-management-deploy.py'
    spec = importlib.util.spec_from_file_location('original_retention_deploy', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def preserved(d, destination):
    # New consumers have already registered fresh heartbeat rows; business rows stay exact.
    before = json.loads((destination / 'fingerprints-preserved.json').read_text())
    after = d.backup.fingerprint(d.backup.DATABASE, True)
    assert set(after) - set(before) == d.checks.ADDED
    heartbeat_tables = {'api_worker_heartbeats', 'worker_heartbeats'}
    assert all(after.get(name) == value for name, value in before.items() if name not in heartbeat_tables), 'Business rows changed'
    columns = json.loads((destination / 'columns.json').read_text())
    actual = d.backup.p.columns(d.backup.DATABASE)
    assert all(actual.get(name) == fields for name, fields in columns.items())
    schedules = json.loads(d.backup.b.query(d.backup.DATABASE, d.backup.ACTUAL_SCHEDULE))
    assert schedules == json.loads((destination / 'expected-schedules.json').read_text())


def preflight(d, work, source, manifest, image):
    assert manifest['release'] == RELEASE
    error = json.loads((work / 'RECOVERY_REQUIRED.json').read_text())
    assert error['release'] == RELEASE and error['phase'] == 'switch' and error['error'] == 'AssertionError'
    assert (work / 'MIGRATION_STARTED').exists() and (work / 'EXECUTORS_STOPPED').exists()
    for name in ('CLEANUP_MAY_HAVE_DELETED', 'VERIFIED', 'SWITCH_RECOVERY_STARTED'):
        assert not (work / name).exists(), 'Recovery cannot be replayed'
    identity = d.m.image_id(work, image)
    assert (work / 'PREPARED').read_text() == identity
    assert d.r.sql('SELECT version_num FROM alembic_version') == '0032'
    assert d.r.sql('SELECT paused FROM api_image_channel WHERE id=1') == 't'
    d.gate.verify_closed()
    destination = d.BACKUPS / RELEASE
    assert (destination / 'COMPLETE').exists()
    preserved(d, destination)
    d.checks.migrated()
    data = json.loads((work / 'topology.json').read_text())
    target = (work / 'native-target').read_text()
    d.r.hashes(Path(target).parent, {'files': {k: v for k, v in manifest['files'].items() if k.startswith('backend/')}})
    for unit in d.n.UNITS:
        assert d.n.show(unit, 'WorkingDirectory') == target
        if unit != d.n.UNIT:
            assert d.n.show(unit, 'MainPID') == '0'
    original = json.loads((work / 'native-snapshots.private.json').read_text())[d.n.UNIT]
    current = d.n.snapshot(d.n.UNIT)
    assert current['cwd'] == target and current['policy'] == original['policy']
    assert current['argv'] == d.n.target_argv(original, target)
    transient = {'PWD', 'INVOCATION_ID', 'SYSTEMD_EXEC_PID', 'JOURNAL_STREAM'}
    clean = lambda env: {k: v for k, v in env.items() if k not in transient}
    assert clean(current['environment']) == clean(original['environment'])
    for service in d.s.SERVICES:
        live = d.m.live(d.m.container('domestic', service))
        if service in ('api', 'api-image-worker', 'image-variants'):
            assert live['Image'] == identity and live['State']['Running']
            assert live['State'].get('Health', {}).get('Status', 'healthy') == 'healthy'
        else:
            name = d.m.container('domestic', service)
            assert live['Id'] == data['domestic']['ids'][name] and not live['State']['Running']
    d.s.unchanged(data)
    return data, current


def ready(d, row):
    cwd = Path(row['cwd'])
    result = subprocess.run(['runuser', '-u', 'codex', '--', str(cwd / '.venv/bin/python'),
        '-c', d.n.READINESS], cwd=cwd, env=dict(row['environment'], PYTHONPATH=str(cwd)),
        capture_output=True, text=True, timeout=45)
    assert result.returncode == 0 and result.stdout.strip() == 'NATIVE_WORKER_READY', 'Native readiness failed'
    assert d.n.show(d.n.UNIT, 'MainPID') == str(row['pid']), 'Native PID changed'


def recover(d, work):
    source, manifest, image = d.s.validate(work, RELEASE)
    data, row = preflight(d, work, source, manifest, image)
    ready(d, row)
    d.r.worker(source / 'scripts/release/image-inputs-worker.py', 'api-verify')
    d.m.private(work / 'SWITCH_RECOVERY_STARTED', hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    phase = 'recovery-publish'
    try:
        d.gate.verify_closed()
        d.r.publish(source)
        d.checks.frontend(source)
        d.s.unchanged(data)
        phase = 'recovery-start-cleanup'
        d.m.private(work / 'CLEANUP_MAY_HAVE_DELETED', 'Forward-only; never restore old DB or erase receipts')
        d.checks.mark_start(work)
        d.m.run('systemctl', 'start', d.n.DELETE, d.n.RETENTION)
        d.checks.first_scan(work)
        d.n.verify(work)
        phase = 'recovery-resume-producers'
        d.m.compose(data['domestic'], 'up', '-d', '--no-deps', '--no-build', '--pull', 'never',
            '--wait', '--wait-timeout', '180', 'outbox', 'api-image-outbox', overlay=work / 'domestic-overlay.json')
        d.s.installed(work, data, image)
        d.r.sql('UPDATE api_image_channel SET paused=false WHERE id=1')
        phase = 'recovery-open-intake'
        d.gate.open_intake(work)
        d.s.p.base.public_verify(source)
        d.s.unchanged(data)
        for name in ('DOMESTIC_RELEASE.json', 'RETENTION_MANAGEMENT_RELEASE.json', 'FRONTEND_RELEASE.json'):
            d.m.private(d.m.APP / name, manifest)
        (work / 'RECOVERY_REQUIRED.json').rename(work / 'recovered-switch-failure.json')
        d.m.private(work / 'VERIFIED', RELEASE)
    except BaseException as error:
        d.m.private(work / 'RECOVERY_REQUIRED.json', dict(phase=phase, error=type(error).__name__, release=RELEASE))
        try:
            d.gate.close(work)
        finally:
            if (work / 'CLEANUP_MAY_HAVE_DELETED').exists():
                for unit in (d.n.RETENTION, d.n.DELETE):
                    try:
                        d.n.stop(unit)
                    except BaseException as stop_error:
                        d.m.private(work / (unit + '-STOP_REQUIRED'), type(stop_error).__name__)
        raise


if __name__ == '__main__':
    assert not sys.flags.optimize and sys.argv[1:] == [RELEASE, 'recover']
    os.umask(0o077)
    work = Path('/opt/hengxin-releases') / RELEASE
    runtime = load(work)
    runtime.m.module('release-retention').managed(lambda: recover(runtime, work))
