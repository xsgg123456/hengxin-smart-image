import importlib.util
import json
from pathlib import Path
import subprocess

import pytest

spec = importlib.util.spec_from_file_location('retry_deploy', Path(__file__).with_name('api-retry-deploy.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


@pytest.fixture
def release(monkeypatch, tmp_path):
    events = []
    data = {'domestic': {'project': 'domestic'}}
    (tmp_path / 'PREPARED').write_text('sha256:candidate')
    (tmp_path / 'topology.json').write_text(json.dumps(data))
    (tmp_path / 'domestic-compose.private.json').write_text('{}')
    monkeypatch.setattr(d, 'BACKUPS', tmp_path / 'backup')
    monkeypatch.setattr(d.m, 'image_id', lambda *_: 'sha256:candidate')
    monkeypatch.setattr(d, 'topology', lambda: data)
    monkeypatch.setattr(d, 'baseline', lambda: None)
    monkeypatch.setattr(d, 'same_settings', lambda *_: None)
    monkeypatch.setattr(d.m, 'assets_safe', lambda *_: None)
    monkeypatch.setattr(d.m, 'private', lambda path, value: events.append(('save', path.name, value)))
    def compose(_data, *args, **kw):
        events.append(('compose', *args))
        return '{}' if args[0] == 'config' else ''
    monkeypatch.setattr(d.m, 'compose', compose)
    def sql(query):
        if query.startswith('SELECT version_num'): return '0031'
        if query.startswith('SELECT paused'): return 'f'
        events.append(('sql', query))
        return '0'
    monkeypatch.setattr(d.r, 'sql', sql)
    for owner, name in ((d.gate, 'close'), (d.gate, 'verify_closed'), (d.gate, 'open_intake'),
                        (d, 'graceful_stop'), (d, 'drain'), (d, 'backup'), (d, 'verify_migration'),
                        (d, 'verify'), (d, 'unchanged'), (d.r, 'publish'), (d.base, 'public_verify')):
        monkeypatch.setattr(owner, name, lambda *args, label=name: events.append((label, *args)))
    return tmp_path, tmp_path / 'source', {'release': 'domestic-api-retry-20261020-abcdef0'}, 'image', events


def test_cutover_only_switches_api_services_and_protects_activation(release):
    *args, events = release
    d.deploy(*args)
    labels = [row[0] for row in events]
    assert labels.index('close') < labels.index('drain') < labels.index('backup')
    assert labels.index('backup') < labels.index('verify_migration') < labels.index('verify')
    assert labels.index('verify') < labels.index('publish') < labels.index('open_intake')
    switch = next(row for row in events if row[:2] == ('compose', 'up'))
    assert switch[-3:] == d.SERVICES
    protect = next(i for i, row in enumerate(events) if row[:2] == ('save', 'NEW_POLICY_MAY_BE_ACTIVE'))
    unpause = next(i for i, row in enumerate(events) if row[0] == 'sql' and 'paused=false' in row[1])
    assert protect < unpause
    assert not any('systemctl' in row for row in events)


@pytest.mark.parametrize('failure', ['drain', 'backup', 'verify_migration', 'verify', 'public_verify'])
def test_failures_close_intake_and_never_restart_old_consumers(release, monkeypatch, failure):
    *args, events = release
    owner = d.base if failure == 'public_verify' else d
    monkeypatch.setattr(owner, failure, lambda *_: (_ for _ in ()).throw(RuntimeError('injected')))
    with pytest.raises(RuntimeError, match='injected'):
        d.deploy(*args)
    assert events[-1][0] == 'close'
    assert any(row[:2] == ('save', 'RECOVERY_REQUIRED.json') for row in events)
    assert not any(row[0] == 'compose' and ('restart' in row or 'down' in row) for row in events)


def test_overlay_rejects_auth_or_unrelated_policy_drift():
    old = {'services': {name: {'image': 'old', 'environment': {'SECRET': 'retained'}}
                        for name in (*d.SERVICES, 'migrate', 'outbox')}}
    new = json.loads(json.dumps(old))
    for name in (*d.SERVICES, 'migrate'):
        new['services'][name]['image'] = 'new'
    for name in d.SERVICES:
        new['services'][name]['environment'].update(d.SETTINGS)
        new['services'][name]['stop_grace_period'] = '11m0s'
    d.same_settings(old, new)
    new['services']['api']['environment']['SECRET'] = 'changed'
    with pytest.raises(AssertionError): d.same_settings(old, new)
    new['services']['api']['environment']['SECRET'] = 'retained'
    new['services']['outbox']['image'] = 'changed'
    with pytest.raises(AssertionError): d.same_settings(old, new)


def test_graceful_stop_never_uses_kill_escalation(monkeypatch):
    calls = []
    monkeypatch.setattr(d.m, 'run', lambda *args, **kw: calls.append((args, kw)))
    monkeypatch.setattr(d.m, 'live', lambda *_: {'State': {'Running': False}})
    d.graceful_stop('api-image-worker', 3)
    assert calls == [(('docker', 'stop', '--timeout=-1', 'hengxin-vps-staging-api-image-worker-1'), {'timeout': 3})]
    monkeypatch.setattr(d.m, 'run', lambda *a, **kw: (_ for _ in ()).throw(subprocess.TimeoutExpired(a, 3)))
    with pytest.raises(subprocess.TimeoutExpired): d.graceful_stop('api-image-worker', 3)


def test_drain_checks_broker_twice_after_outbox_exit(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(d.m, 'private', lambda *_: None)
    monkeypatch.setattr(d, 'wait_empty', lambda *_: calls.append('idle'))
    monkeypatch.setattr(d, 'graceful_stop', lambda service: calls.append(service))
    monkeypatch.setattr(d.r, 'sql', lambda *_: '0')
    d.drain(tmp_path, {})
    assert calls == ['idle', 'api-image-outbox', 'idle', 'api-image-worker']


def test_wait_empty_requires_unknown_attempts_to_clear(monkeypatch, tmp_path):
    empty = {'states': [{'w': []}] * 3, 'queues': {'api_image_edits': 0}, 'unacked': 0}
    ticks = iter([0, 0, 0, 0.1, 1.1])
    monkeypatch.setattr(d.m, 'private', lambda *_: None)
    monkeypatch.setattr(d.time, 'monotonic', lambda: next(ticks))
    monkeypatch.setattr(d.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(d.m, 'run', lambda *args, **kw: json.dumps(empty) if 'python' in args else '1')
    with pytest.raises(AssertionError, match='busy/unknown'):
        d.wait_empty(tmp_path, 1)
    assert "WHERE state='running'" in d.PENDING
    assert 'api_image_channel WHERE item_id IS NOT NULL' in d.PENDING


def test_retry_cycle_probe_includes_finished_cycles(monkeypatch):
    queries = []
    monkeypatch.setattr(d.r, 'sql', lambda query: queries.append(query) or '1')
    assert d.new_cycles() == 1
    assert "retry_policy_version='bounded-v2'" in queries[0]
    assert 'state' not in queries[0]
