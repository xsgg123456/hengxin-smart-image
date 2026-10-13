"""Failure-injection coverage for overseas-only, forward-only production updates."""
import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('update_deploy_test', Path(__file__).with_name('overseas-update-deploy.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)
r = d.r


def test_close_edge_keeps_domestic_and_identity_routes(tmp_path, monkeypatch):
    edge = tmp_path / 'edge.conf'
    other = 'location /api/v1/ { proxy_pass http://domestic; }\nlocation /api/identity/v1/ { proxy_pass http://identity; }\n'
    edge.write_text(other + 'location ^~ /api/overseas/v1/ { proxy_pass http://overseas; }')
    monkeypatch.setattr(r, 'EDGE', edge)
    monkeypatch.setattr(r, 'reload_edge', lambda: None)
    r.close_edge()
    assert edge.read_text() == other + 'location ^~ /api/overseas/v1/ { return 503; }'
    r.close_edge()  # Failure cleanup remains idempotent.
    assert edge.read_text().count('return 503;') == 1


def test_close_edge_refuses_unknown_proxy_layout(tmp_path, monkeypatch):
    edge = tmp_path / 'edge.conf'
    edge.write_text('location / { proxy_pass http://domestic; }')
    monkeypatch.setattr(r, 'EDGE', edge)
    monkeypatch.setattr(r, 'reload_edge', lambda: pytest.fail('must not reload unknown layout'))
    with pytest.raises(AssertionError):
        r.close_edge()


def test_drain_does_not_treat_unknown_worker_as_empty(monkeypatch):
    monkeypatch.setattr(r, 'pending', lambda: 0)
    monkeypatch.setattr(r, 'native_probe', lambda _: [None, None, None])
    with pytest.raises(AssertionError, match='replies unavailable'):
        r.drain(timeout=0)


def test_drain_timeout_never_stops_executor(monkeypatch):
    monkeypatch.setattr(r, 'pending', lambda: 1)
    monkeypatch.setattr(r, 'run', lambda *_: pytest.fail('must not kill a running task'))
    with pytest.raises(RuntimeError, match='remain running'):
        r.drain(timeout=0)


@pytest.mark.parametrize('states,expected', [([{'node': []}] * 3, True),
    ([{'node': [{'id': 'active'}]}, {'node': []}, {'node': []}], False)])
def test_worker_idle_checks_every_celery_state(monkeypatch, states, expected):
    monkeypatch.setattr(r, 'native_probe', lambda _: states)
    assert r.worker_idle() is expected


def setup_deploy(monkeypatch, tmp_path, failure=None):
    work = tmp_path / 'work'
    work.mkdir()
    for name in ('PREPARED', 'INSTALL_TEST_IMAGE_ID'):
        (work / name).write_text('sha256:tested')
    data = {'paths': ['old.yaml'], 'env': 'overseas.env', 'image': 'old-image'}
    (work / 'old-topology.json').write_text(json.dumps(data))
    (work / 'untouched.json').write_text('{}')
    (work / 'native-target').write_text('/opt/new/backend')
    edge = tmp_path / 'edge.conf'
    edge.write_text('original overseas route')
    events = []
    def event(name, *args):
        events.append((name, *args))
        if failure == name:
            raise RuntimeError(name)
    monkeypatch.setattr(r, 'EDGE', edge)
    monkeypatch.setattr(r, 'APP', tmp_path)
    monkeypatch.setattr(r, 'run', lambda *args, **kw: event('run', *args) or 'sha256:tested')
    monkeypatch.setattr(r, 'private', lambda p, v: event('private', str(p)))
    monkeypatch.setattr(r, 'sql', lambda _: 'overseas_0012' if any(e[0] == 'migrate' for e in events) else 'overseas_0010')
    monkeypatch.setattr(r, 'roles_migratable', lambda: event('roles'))
    monkeypatch.setattr(r, 'topology', lambda: data)
    monkeypatch.setattr(d, 'untouched', lambda: {})
    monkeypatch.setattr(r, 'close_edge', lambda: event('close'))
    monkeypatch.setattr(r, 'reload_edge', lambda: event('open'))
    monkeypatch.setattr(r, 'drain', lambda: event('drain'))
    monkeypatch.setattr(r, 'pending', lambda: 0)
    monkeypatch.setattr(r, 'worker_idle', lambda: True)
    monkeypatch.setattr(r, 'backup', lambda *args: event('backup'))
    monkeypatch.setattr(r, 'switch_native', lambda *args: event('native'))
    monkeypatch.setattr(r.r, 'publish', lambda *args: event('publish'))
    monkeypatch.setattr(r, 'verify', lambda *args: event('verify'))
    monkeypatch.setattr(d, 'public_verify', lambda *args: event('public'))
    def compose(data, *args, **kw):
        event('migrate' if args[0] == 'run' else 'compose', *args)
    monkeypatch.setattr(r, 'compose', compose)
    return work, events


@pytest.mark.parametrize('failure', ['drain', 'backup', 'migrate', 'native', 'publish', 'verify', 'public'])
def test_failures_close_intake_without_old_code_or_database_rollback(monkeypatch, tmp_path, failure):
    work, events = setup_deploy(monkeypatch, tmp_path, failure)
    with pytest.raises(RuntimeError, match=failure):
        d.deploy(work, tmp_path, {'release': 'test-release-not-on-server'}, 'image')
    assert events[-2][0] == 'close'
    assert events[-1] == ('compose', 'stop', '-t', '30', 'api')
    assert not any('restore' in str(e) or 'downgrade' in str(e) for e in events)
    if failure == 'drain':
        assert not any(e[:3] == ('run', 'systemctl', 'stop') for e in events)


def test_success_orders_drain_backup_migration_validation_open(monkeypatch, tmp_path):
    work, events = setup_deploy(monkeypatch, tmp_path)
    d.deploy(work, tmp_path, {'release': 'test-release-not-on-server'}, 'image')
    names = [e[0] for e in events]
    assert names.index('close') < names.index('drain') < names.index('backup') < names.index('migrate')
    assert names.index('migrate') < names.index('verify') < names.index('open') < names.index('public')
    assert ('run', 'systemctl', 'stop', r.UNITS[0]) in events
    assert not any('hengxin-vps' in str(e) and 'stop' in e for e in events)


@pytest.mark.parametrize('count', ['1', '2'])
def test_role_preflight_blocks_ambiguous_and_missing_roles(monkeypatch, count):
    monkeypatch.setattr(r, 'sql', lambda _: count)
    with pytest.raises(AssertionError, match='roles before migration'):
        r.roles_migratable()


def test_role_preflight_accepts_migratable_population(monkeypatch):
    monkeypatch.setattr(r, 'sql', lambda _: '0')
    r.roles_migratable()


def test_worker_readiness_waits_for_replies(monkeypatch):
    ready = {'stats': {'node': {'pool': {'max-concurrency': 5}}},
             'queues': {'node': [{'name': 'overseas.cli'}]}}
    replies = iter([{'stats': None, 'queues': None}, ready])
    monkeypatch.setattr(r, 'native_probe', lambda _: next(replies))
    monkeypatch.setattr(r.time, 'sleep', lambda _: None)
    r.wait_worker_ready()


def test_worker_readiness_never_accepts_absent_replies(monkeypatch):
    monkeypatch.setattr(r, 'native_probe', lambda _: {'stats': None, 'queues': None})
    with pytest.raises(RuntimeError, match='readiness timed out'):
        r.wait_worker_ready(timeout=0)


def test_worker_readiness_rejects_wrong_queue(monkeypatch):
    monkeypatch.setattr(r, 'native_probe', lambda _: {
        'stats': {'node': {'pool': {'max-concurrency': 5}}},
        'queues': {'node': [{'name': 'domestic'}]}})
    with pytest.raises(AssertionError, match='Wrong worker queues'):
        r.wait_worker_ready()
