import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


r = module('retention-management-recover-switch')
base = module('test_retention_management_deploy')
d, release = base.d, base.release


@pytest.fixture
def recovery(release, monkeypatch):
    work, source, manifest, image, events = release
    manifest['release'] = r.RELEASE
    (work / 'RECOVERY_REQUIRED.json').write_text(json.dumps(dict(phase='switch', error='AssertionError', release=r.RELEASE)))
    monkeypatch.setattr(d.s, 'validate', lambda *_: (source, manifest, image))
    monkeypatch.setattr(r, 'preflight', lambda *_: ({'domestic': {}}, {}))
    monkeypatch.setattr(r, 'ready', lambda *_: events.append(('ready',)))
    return work, events


def test_recovery_only_finishes_after_switch_without_replaying_migration(recovery):
    work, events = recovery
    r.recover(d, work)
    labels = [e[0] for e in events]
    assert labels.index('ready') < labels.index('publish') < labels.index('first_scan') < labels.index('open_intake')
    assert not any(e[0] in ('backup', 'switch', 'stop') or e[:2] == ('compose', 'run') for e in events)
    assert (work / 'VERIFIED').read_text() == r.RELEASE
    assert not (work / 'RECOVERY_REQUIRED.json').exists()
    assert (work / 'recovered-switch-failure.json').exists()


@pytest.mark.parametrize('owner,name', [('checks', 'first_scan'), ('s', 'installed'), ('gate', 'open_intake')])
def test_failed_recovery_keeps_receipts_and_stops_cleanup(recovery, monkeypatch, owner, name):
    work, events = recovery
    def fail(*_):
        raise RuntimeError('injected')
    monkeypatch.setattr(getattr(d, owner), name, fail)
    with pytest.raises(RuntimeError, match='injected'):
        r.recover(d, work)
    assert not (work / 'VERIFIED').exists()
    assert (work / 'CLEANUP_MAY_HAVE_DELETED').exists()
    assert [e[1] for e in events if e[0] == 'pause-cleanup'] == [d.n.RETENTION, d.n.DELETE]
    assert json.loads((work / 'RECOVERY_REQUIRED.json').read_text())['phase'].startswith('recovery-')


@pytest.mark.parametrize('mode', ['wrong-phase', 'cleanup-started', 'already-recovered'])
def test_preflight_rejects_uninspected_state_before_operations(tmp_path, mode):
    (tmp_path / 'RECOVERY_REQUIRED.json').write_text(json.dumps(dict(
        release=r.RELEASE, phase='start-cleanup' if mode == 'wrong-phase' else 'switch', error='AssertionError')))
    for name in ('MIGRATION_STARTED', 'EXECUTORS_STOPPED'):
        (tmp_path / name).write_text('yes')
    if mode != 'wrong-phase':
        (tmp_path / ('CLEANUP_MAY_HAVE_DELETED' if mode == 'cleanup-started' else 'SWITCH_RECOVERY_STARTED')).write_text('yes')
    with pytest.raises(AssertionError):
        r.preflight(SimpleNamespace(), tmp_path, tmp_path, {'release': r.RELEASE}, 'image')


def test_readiness_allows_real_twenty_second_probe_and_checks_same_pid(monkeypatch):
    row = dict(cwd='/opt/backend', environment={'MARKER': 'test'}, pid=12)
    native = SimpleNamespace(READINESS='fixed code', UNIT='native', show=lambda *_: '12')
    def run(args, **kw):
        assert kw['timeout'] == 45 and kw['env']['MARKER'] == 'test'
        return SimpleNamespace(returncode=0, stdout='NATIVE_WORKER_READY\n')
    monkeypatch.setattr(r.subprocess, 'run', run)
    r.ready(SimpleNamespace(n=native), row)
    native.show = lambda *_: '13'
    with pytest.raises(AssertionError, match='PID'):
        r.ready(SimpleNamespace(n=native), row)


@pytest.mark.parametrize('change', ['heartbeats', 'business', 'schedule', 'columns'])
def test_preserved_only_allows_live_heartbeat_changes(tmp_path, monkeypatch, change):
    before = {'api_worker_heartbeats': 'old1', 'worker_heartbeats': 'old2', 'api_image_versions': 'saved'}
    after = dict(before, api_worker_heartbeats='new-node', worker_heartbeats='new-time')
    after.update({name: 'empty' for name in d.checks.ADDED})
    if change == 'business':
        after['api_image_versions'] = 'changed'
    for name, value in {'fingerprints-preserved.json': before, 'columns.json': {'api_image_versions': ['id']},
                        'expected-schedules.json': {'row': 'same'}}.items():
        (tmp_path / name).write_text(json.dumps(value))
    monkeypatch.setattr(d.backup, 'fingerprint', lambda *_: after)
    monkeypatch.setattr(d.backup.p, 'columns', lambda *_: {'api_image_versions': ['wrong' if change == 'columns' else 'id']})
    monkeypatch.setattr(d.backup.b, 'query', lambda *_: json.dumps({'row': 'wrong' if change == 'schedule' else 'same'}))
    if change == 'heartbeats':
        r.preserved(d, tmp_path)
    else:
        with pytest.raises(AssertionError):
            r.preserved(d, tmp_path)
