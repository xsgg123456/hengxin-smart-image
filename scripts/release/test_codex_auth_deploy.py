"""Deploy safety invariants: fail before touching active or unrelated production."""
import importlib.util
import json
from pathlib import Path
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).parent))
import codex_auth_runtime as r
import codex_auth_worker as w

spec = importlib.util.spec_from_file_location('codex_auth_deploy', Path(__file__).with_name('codex-auth-deploy.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(value if isinstance(value, str) else json.dumps(value))


def manifest(tmp_path, baseline=None, name='app/core/config.py'):
    domains = {}
    for domain in r.DOMAINS:
        path = tmp_path / 'src' / domain / name
        save(path, domain)
        domains[domain] = {'files': {name: {'baseline': baseline, 'sha256': r.digest(path)}}}
    save(tmp_path / 'patch.json', {'domains': domains})
    return domains


def test_per_domain_content_is_not_shared(tmp_path):
    manifest(tmp_path)
    domestic = r.patch(tmp_path, 'domestic')
    overseas = r.patch(tmp_path, 'overseas')
    assert domestic['app/core/config.py']['sha256'] != overseas['app/core/config.py']['sha256']


@pytest.mark.parametrize('name', ['../app/core/config.py', 'app/overseas/auth/router.py', '.env'])
def test_unreviewed_paths_are_rejected(tmp_path, name):
    manifest(tmp_path, name=name)
    with pytest.raises(RuntimeError, match='allowlist'):
        r.patch(tmp_path, 'domestic')


def test_mutated_package_is_rejected(tmp_path):
    manifest(tmp_path)
    save(tmp_path / 'src/domestic/app/core/config.py', 'drift')
    with pytest.raises(RuntimeError, match='checksum'):
        r.patch(tmp_path, 'domestic')


def test_live_baseline_drift_is_rejected(tmp_path):
    save(tmp_path / 'app/core/config.py', 'already deployed newer code')
    files = {'app/core/config.py': {'baseline': '0' * 64}}
    with pytest.raises(RuntimeError, match='baseline differs'):
        r.baseline(tmp_path, files)


def test_new_file_must_not_already_exist(tmp_path):
    save(tmp_path / 'app/core/config.py', 'existing')
    with pytest.raises(RuntimeError, match='baseline differs'):
        r.baseline(tmp_path, {'app/core/config.py': {'baseline': None}})


@pytest.mark.parametrize('marker', [None, 'stale-manifest'])
def test_switch_requires_installed_test_receipt_before_any_service_call(tmp_path, monkeypatch, marker):
    save(tmp_path / 'patch.json', '{}')
    save(tmp_path / 'prepared.json', {'manifest': r.digest(tmp_path / 'patch.json')})
    if marker:
        save(tmp_path / 'INSTALL_TESTS_PASSED', marker)
    calls = []
    monkeypatch.setattr(r, 'run', lambda *a, **k: calls.append(a))
    with pytest.raises((FileNotFoundError, RuntimeError)):
        d.switch(tmp_path, 'domestic')
    assert calls == []


def test_unrelated_topology_change_rejects_validation(tmp_path, monkeypatch):
    save(tmp_path / 'patch.json', '{}')
    fingerprint = r.digest(tmp_path / 'patch.json')
    save(tmp_path / 'prepared.json', dict(manifest=fingerprint, unrelated={'old': 1}))
    save(tmp_path / 'INSTALL_TESTS_PASSED', fingerprint)
    monkeypatch.setattr(r, 'topology', lambda: {'changed': 1})
    with pytest.raises(RuntimeError, match='topology changed'):
        d.validate(tmp_path)


class Control:
    def __init__(self):
        self.cancelled, self.resumed = [], []

    def cancel_consumer(self, queue, **kwargs):
        self.cancelled.append(queue)
        return [{'node': {'ok': 'cancelled'}}]

    def add_consumer(self, queue, **kwargs):
        self.resumed.append(queue)
        return [{'node': {'ok': 'restored'}}]


@pytest.mark.parametrize('problem', ['active', 'reserved', 'scheduled', 'database', 'inspection'])
def test_unproven_drain_never_stops_worker(tmp_path, monkeypatch, problem):
    calls, control = [], Control()
    def inspect(_, __, name):
        if problem == 'inspection':
            raise RuntimeError('unavailable')
        return ['busy'] if name == problem else []
    monkeypatch.setattr(w, 'inspect', inspect)
    monkeypatch.setattr(w, 'database_idle', lambda *_: problem != 'database')
    monkeypatch.setattr(r, 'run', lambda *a, **k: calls.append(a))
    with pytest.raises(RuntimeError):
        w.drain_stop(control, None, 'overseas', 'node', tmp_path, wait_seconds=-1)
    assert calls == []
    assert control.cancelled == control.resumed == ['overseas.cli']


def test_proven_drain_stops_only_selected_worker_and_never_outbox(tmp_path, monkeypatch):
    calls, control = [], Control()
    monkeypatch.setattr(w, 'inspect', lambda *_: [])
    monkeypatch.setattr(w, 'database_idle', lambda *_: True)
    monkeypatch.setattr(w.time, 'sleep', lambda _: None)
    monkeypatch.setattr(r, 'run', lambda *a, **k: calls.append(a) or ('0' if a[1] == 'show' else ''))
    w.drain_stop(control, None, 'overseas', 'node', tmp_path)
    assert calls[0] == ('systemctl', 'stop', 'hengxin-overseas-worker.service')
    assert all('outbox' not in str(call) and 'docker' not in str(call) for call in calls)
    assert control.resumed == []
    assert json.loads((tmp_path / 'overseas-stage.json').read_text())['phase'] == 'stopped'


def test_stop_failure_does_not_resume_or_blindly_rollback(tmp_path, monkeypatch):
    calls, control = [], Control()
    monkeypatch.setattr(w, 'inspect', lambda *_: [])
    monkeypatch.setattr(w, 'database_idle', lambda *_: True)
    monkeypatch.setattr(w.time, 'sleep', lambda _: None)
    def fail(*args, **kwargs):
        calls.append(args)
        raise RuntimeError('stop outcome unknown')
    monkeypatch.setattr(r, 'run', fail)
    with pytest.raises(RuntimeError, match='unknown'):
        w.drain_stop(control, None, 'domestic', 'node', tmp_path)
    assert calls == [('systemctl', 'stop', 'hengxin-vps-codex-worker.service')]
    assert control.resumed == []
    assert json.loads((tmp_path / 'domestic-stage.json').read_text())['phase'] == 'drained-stop-requested'


def test_worker_identity_requires_actual_pid(monkeypatch):
    control = SimpleNamespace(inspect=lambda **_: SimpleNamespace(stats=lambda: {'node': {'pid': 21}}))
    with pytest.raises(RuntimeError, match='MainPID'):
        w.identify(control, 22, 'domestic')


def test_overrides_preserve_users_and_isolate_access():
    for domain in r.DOMAINS:
        text = r.dropin(domain, 'node@host')
        assert 'SupplementaryGroups=hengxin-codex-auth' in text
        assert 'User=' not in text and 'Group=' not in text
        assert '--concurrency=5' in text
        assert r.DOMAINS[domain]['prefix'] + 'CODEX_AUTH_BROKER_SOCKET=' in text
    broker = r.broker_unit()
    assert 'User=codex' in broker and 'RuntimeDirectoryMode=0750' in broker
    assert '--source /home/codex/auth/auth.json' in broker
    assert '/var/lib/hengxin-overseas/auth' not in broker
    assert '--allowed-uid 1001 --allowed-uid 999' in broker


def test_unsafe_node_name_rejected():
    with pytest.raises(RuntimeError, match='Unsafe'):
        r.dropin('domestic', 'node\nUser=root')


def test_probe_runs_access_only_as_intended_uid(monkeypatch):
    calls = []
    def run(*args, **kwargs):
        calls.append((args, kwargs))
        return 'hengxin-codex-auth:x:1987:' if args[0] == 'getent' else 'ACCESS_ONLY_OK'
    monkeypatch.setattr(r, 'run', run)
    r.probe_access('overseas')
    args, kwargs = calls[-1]
    assert '--reuid=999' in args and '--regid=987' in args and '--groups=1987' in args
    assert 'refresh_token' in args[-1]
    assert set(kwargs['env']) == {'PATH', 'PYTHONPATH'}


def test_failed_switch_is_recorded_without_automatic_rollback(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, 'argv', ['codex-auth-deploy.py', 'switch-domestic', '--work', str(tmp_path)])
    monkeypatch.setattr(d.os, 'geteuid', lambda: 0, raising=False)
    monkeypatch.setitem(sys.modules, 'fcntl', SimpleNamespace(LOCK_EX=2, LOCK_NB=4, flock=lambda *_: None))
    monkeypatch.setattr(d, 'switch', lambda *_: (_ for _ in ()).throw(RuntimeError('started but unhealthy')))
    calls = []
    monkeypatch.setattr(r, 'run', lambda *a, **k: calls.append(a))
    with pytest.raises(RuntimeError):
        d.main()
    assert calls == []
    assert json.loads((tmp_path / 'FAILURE.json').read_text())['action'] == 'switch-domestic'


@pytest.mark.parametrize('changed', ['installed', 'original', 'other-worker'])
def test_validation_rechecks_all_source_and_worker_identities(tmp_path, monkeypatch, changed):
    save(tmp_path / 'patch.json', '{}')
    fingerprint = r.digest(tmp_path / 'patch.json')
    saved = dict(old='/old', pid=123, node='node', files={'file': 'hash'},
                 source={'old': 'hash'}, installed={'new': 'hash'})
    save(tmp_path / 'prepared.json', dict(manifest=fingerprint, unrelated={}, domains={'overseas': saved}))
    save(tmp_path / 'INSTALL_TESTS_PASSED', fingerprint)
    monkeypatch.setattr(r, 'topology', lambda: {})
    monkeypatch.setattr(r, 'patch', lambda *_: saved['files'])
    def tree(path):
        if path == Path('/old'):
            return {} if changed == 'original' else saved['source']
        return {} if changed == 'installed' else saved['installed']
    monkeypatch.setattr(r, 'tree', tree)
    monkeypatch.setattr(r, 'live', lambda _: (Path('/old'), {}, 456))
    with pytest.raises(RuntimeError, match='drift|identity changed'):
        d.validate(tmp_path)


def test_switch_does_not_write_override_when_drain_fails(tmp_path, monkeypatch):
    saved = dict(old=str(Path('/old')), pid=123, node='node')
    monkeypatch.setattr(d, 'validate', lambda _: {'domains': {'overseas': saved}})
    save(tmp_path / 'broker-stage.json', {'phase': 'ready-both-uids'})
    save(tmp_path / 'overseas-unit-before.txt', 'unit')
    monkeypatch.setattr(r, 'live', lambda _: (Path('/old'), {}, 123))
    drop = tmp_path / 'untouched.conf'
    monkeypatch.setattr(r, 'drop_path', lambda _: drop)
    monkeypatch.setattr(r, 'probe_access', lambda _: None)
    monkeypatch.setattr(r, 'worker_probe', lambda *_: (_ for _ in ()).throw(RuntimeError('busy')))
    calls = []
    monkeypatch.setattr(r, 'run', lambda *a, **k: calls.append(a) or 'unit')
    with pytest.raises(RuntimeError, match='busy'):
        d.switch(tmp_path, 'overseas')
    assert not drop.exists()
    assert calls == [('systemctl', 'cat', 'hengxin-overseas-worker.service')]
