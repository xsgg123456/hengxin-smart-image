import importlib.util
from pathlib import Path, PurePosixPath
import subprocess

import pytest


def load(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


g, d, b, n = [load('domestic-' + name) for name in ('gate', 'drain', 'backup', 'runtime')]


def test_edge_closure_overrides_domestic_regex_and_preserves_other_domains():
    original = '''server { listen 80; return 301 https://$host$request_uri; }
server {
    listen 443 ssl;
    ssl_prefer_server_ciphers off;
    location ^~ /api/identity/v1/ { proxy_pass http://identity; }
    location ^~ /api/overseas/v1/ { client_max_body_size 500065536; proxy_pass http://overseas; }
    location ~ ^/api/v1/tasks/[^/]+/events$ { proxy_pass http://domestic; }
}
'''
    changed = g.closed_config(original, edge=True)
    assert changed.replace('\n' + g.BLOCK, '', 1) == original
    assert changed.index('listen 443') < changed.index(g.BLOCK)
    assert changed.count('location ^~ /api/v1/') == 1
    assert g.closed_config(changed, edge=True) == changed


def test_internal_closure_and_ambiguous_configuration():
    original = 'server {\n    location /api/ { proxy_pass http://api; }\n}\n'
    assert g.closed_config(original) == original.replace('    location /api/', g.BLOCK + '\n    location /api/')
    for value in ('server {}', original + original):
        with pytest.raises(AssertionError, match='ambiguous'):
            g.closed_config(value)


def test_both_gateway_layers_and_regex_route_are_verified(monkeypatch):
    calls = []
    monkeypatch.setattr(g.m, 'run', lambda *args, **kwargs: calls.append(args) or '503')
    g.verify_closed()
    assert len(calls) == 6
    assert sum('--resolve' in row for row in calls) == 2
    assert sum('conversation/events' in row[-1] for row in calls) == 3
    monkeypatch.setattr(g.m, 'run', lambda *args, **kwargs: '200')
    with pytest.raises(AssertionError, match='not closed'):
        g.verify_closed()


def test_deletion_service_only_runs_explicit_deletions_with_native_env():
    source = Path(__file__).resolve().parents[2] / 'hengxin-smart-image'
    target = PurePosixPath('/opt/hengxin-native-releases/domestic-20261015-abcdef0/backend')
    policy = {'environmentFiles': ['/etc/hengxin-smart-image/worker.env', '/opt/release/runtime.env'],
              'limits': {'MemoryMax': '1000000', 'TasksMax': '512'}}
    body = n.render_deletion(source, target, policy)
    assert '@BACKEND@' not in body and '@ENVIRONMENT_FILES@' not in body and '@LIMITS@' not in body
    assert '--deletions-only --loop --interval 5' in body
    assert 'CLI_RETENTION_ENABLED=false' in body
    assert body.index('EnvironmentFile=/etc/') < body.index('EnvironmentFile=/opt/')
    assert 'User=codex\nGroup=codex' in body and 'UMask=0077' in body
    assert 'MemoryMax=1000000' in body and 'TasksMax=512' in body
    assert n.DROPIN.name == '99-domestic-release.conf'


def test_migration_cannot_modify_existing_rows_or_enqueue_deletions():
    before = {'users': '2:abc', 'api_image_tasks': '3:def'}
    b.compare(before, {**before, 'api_task_deletions': '0:empty'})
    for after in ({**before, 'users': '2:changed', 'api_task_deletions': '0:x'},
                  {**before, 'api_task_deletions': '1:old'},
                  {**before, 'unexpected': '0:x', 'api_task_deletions': '0:x'}):
        with pytest.raises(AssertionError):
            b.compare(before, after)


def evidence(busy=False):
    return dict(workers={'native': {'states': [{'node': []}] * 3, 'queues': {'celery': int(busy)}, 'unacked': 0}},
                durable=0, variants=0)


def test_drain_requires_consecutive_empty_broker_checks(monkeypatch, tmp_path):
    values = iter([evidence(), evidence(True), evidence(), evidence()])
    seen = []
    monkeypatch.setattr(d, 'evidence', lambda *_: seen.append(1) or next(values))
    monkeypatch.setattr(d.time, 'sleep', lambda *_: None)
    monkeypatch.setattr(d.m, 'private', lambda *_: None)
    d.wait_empty(tmp_path, 'probe')
    assert len(seen) == 4


def test_busy_drain_never_reaches_executor_stop(monkeypatch, tmp_path):
    monkeypatch.setattr(d, 'evidence', lambda *_: evidence(True))
    monkeypatch.setattr(d.m, 'private', lambda *_: None)
    with pytest.raises(RuntimeError, match='no executor force-stop'):
        d.wait_empty(tmp_path, 'probe', timeout=0)
    monkeypatch.setattr(d, 'wait_empty', lambda *_: (_ for _ in ()).throw(RuntimeError('busy')))
    monkeypatch.setattr(d.m, 'compose', lambda *_: pytest.fail('must not stop before idle'))
    with pytest.raises(RuntimeError, match='busy'):
        d.stop(tmp_path, tmp_path, {'domestic': {}})


def test_hanging_probe_is_bounded_and_cannot_authorize_stop(monkeypatch, tmp_path):
    events = []

    class Process:
        pid = 123
        calls = 0

        def communicate(self, timeout):
            events.append(('wait', timeout))
            self.calls += 1
            if self.calls == 1:
                raise subprocess.TimeoutExpired('probe', timeout)
            return '', ''

        def kill(self):
            events.append(('kill',))

    monkeypatch.setattr(d.subprocess, 'Popen', lambda *args, **kw: Process())
    if d.os.name != 'nt':
        monkeypatch.setattr(d.os, 'killpg', lambda *args: events.append(('kill',)))
    with pytest.raises(RuntimeError, match='no executor force-stop'):
        d.evidence(tmp_path, 0.1)
    assert events == [('wait', 0.1), ('kill',), ('wait', 5)]


def test_deletion_readiness_rejects_unavailable_and_requires_two_real_loops(monkeypatch, tmp_path):
    verify = load('domestic-verify')
    monkeypatch.setattr(verify.d, 'native_probe', lambda *_: {'schema': '0029', 'receipts': 0, 'scan': 'PASS'})
    monkeypatch.setattr(verify.m, 'private', lambda *_: None)
    monkeypatch.setattr(verify.time, 'sleep', lambda *_: None)
    logs = iter(['[]', '[]\n[]'])
    calls = []

    def run(*args, **kwargs):
        calls.append(args)
        return next(logs) if args[0] == 'journalctl' else 'invocation'

    monkeypatch.setattr(verify.m, 'run', run)
    verify.deletion_ready(tmp_path)
    assert sum(row[0] == 'journalctl' for row in calls) == 2
    monkeypatch.setattr(verify.m, 'run', lambda *a, **kw: '{"status":"unavailable"}' if a[0] == 'journalctl' else 'invocation')
    with pytest.raises(AssertionError, match='startup scan'):
        verify.deletion_ready(tmp_path)
    assert 'SET TRANSACTION READ ONLY' in verify.PROBE
    assert 'run_pending' not in verify.PROBE and 'process(' not in verify.PROBE
