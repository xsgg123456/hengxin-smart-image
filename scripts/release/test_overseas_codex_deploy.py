import importlib.util
import json
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location('codex_release_test', Path(__file__).with_name('overseas-codex-deploy.py'))
d = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d)

EDGE = ('server {\n    ssl_prefer_server_ciphers off;\n'
        'location ^~ /api/identity/v1/ { proxy_pass http://identity; }\n'
        'location ^~ /api/overseas/v1/ { proxy_pass http://overseas; }\n}\n')


def save(path, value):
    Path(path).write_text(value if isinstance(value, str) else json.dumps(value))


@pytest.mark.parametrize('explicit', [False, True])
def test_close_both_businesses_without_closing_identity(explicit):
    edge = EDGE.replace('server {', 'server {\nlocation ^~ /api/v1/ { proxy_pass http://domestic; }') if explicit else EDGE
    closed = d.closed_config(edge)
    assert closed.count('return 503;') == 2
    assert 'location ^~ /api/identity/v1/ { proxy_pass http://identity; }' in closed


def test_ambiguous_edge_aborts():
    with pytest.raises(AssertionError):
        d.closed_config(EDGE + 'location ^~ /api/overseas/v1/ { return 200; }')


def test_close_waits_for_both_routes_after_graceful_reload(monkeypatch):
    statuses = iter(['503', '401', '503', '503'])
    sleeps = []
    monkeypatch.setattr(d, 'admission_status', lambda _, timeout: next(statuses))
    monkeypatch.setattr(d.time, 'sleep', sleeps.append)
    d.closed()
    assert sleeps == [1]


def test_close_timeout_never_accepts_partial_closure(monkeypatch):
    statuses = iter(['503', '401'])
    monkeypatch.setattr(d, 'admission_status', lambda _, timeout: next(statuses))
    with pytest.raises(AssertionError, match='Admission not closed'):
        d.closed(timeout=0)


def test_late_success_cannot_pass_deadline(monkeypatch):
    clock = iter([0, 1, 10, 21])
    budgets = []
    monkeypatch.setattr(d.time, 'monotonic', lambda: next(clock))
    def status(_, timeout):
        budgets.append(timeout)
        return '503'
    monkeypatch.setattr(d, 'admission_status', status)
    with pytest.raises(AssertionError, match='Admission not closed'):
        d.closed(timeout=20)
    assert budgets == [19, 10]


def test_network_probe_obeys_remaining_budget(monkeypatch):
    calls = []
    def output(args, **kwargs):
        calls.append((args, kwargs))
        raise d.subprocess.TimeoutExpired(args, kwargs['timeout'])
    monkeypatch.setattr(d.subprocess, 'check_output', output)
    with pytest.raises(d.subprocess.TimeoutExpired):
        d.admission_status('https://example.test', 0.5)
    assert calls[0][1]['timeout'] == 0.5
    assert calls[0][0][2] == '0.5'


def test_domestic_override_only_changes_runtime_file():
    text = d.dropin(d.UNITS[0], Path('/new/backend'))
    assert 'EnvironmentFile=' in text
    assert 'ExecStart' not in text and 'WorkingDirectory' not in text
    assert 'gpt-6-astra' not in text and 'model_reasoning' not in text
    assert 'WorkingDirectory=' + str(Path('/new/backend')) in d.dropin(d.UNITS[1], Path('/new/backend'))


def test_busy_or_unknown_drain_never_succeeds(monkeypatch, tmp_path):
    monkeypatch.setattr(d, 'WORK', tmp_path)
    monkeypatch.setattr(d.m, 'private', save)
    monkeypatch.setattr(d, 'idle_evidence', lambda: dict(workers={}, domestic=1, overseas=0, deleting=0))
    monkeypatch.setattr(d.h.drain, 'idle', lambda _: True)
    with pytest.raises(RuntimeError, match='not drained'):
        d.wait_idle('busy', timeout=0)


@pytest.fixture
def cutover(monkeypatch, tmp_path):
    calls = []
    edge = tmp_path / 'edge.conf'
    edge.write_text(EDGE)
    monkeypatch.setattr(d, 'WORK', tmp_path)
    monkeypatch.setattr(d.m, 'EDGE', edge)
    monkeypatch.setattr(d, 'validate', lambda: dict(old='/old', files={}, baseline={}))
    monkeypatch.setattr(d.p, 'tree', lambda _: {})
    monkeypatch.setattr(d, 'runtime', lambda unit: dict(actual='codex-cli 0.156.1'))
    monkeypatch.setattr(d.m, 'topology', lambda: dict(native={d.UNITS[0]: '/domestic'}, edgeHash=d.m.digest(edge)))
    monkeypatch.setattr(d.r, 'sql', lambda _: '0028')
    monkeypatch.setattr(d.u, 'sql', lambda _: 'overseas_0015')
    def run(*args, **kwargs):
        calls.append(args)
        return 'old config' if kwargs.get('capture') else None
    monkeypatch.setattr(d.m, 'run', run)
    monkeypatch.setattr(d.u, 'reload_edge', lambda: calls.append(('reload',)))
    monkeypatch.setattr(d, 'closed', lambda: None)
    # Capture service overrides into an isolated directory, never /etc.
    def private(path, value):
        path = Path(path)
        if path.as_posix().startswith('/etc/'):
            calls.append(('override', str(path)))
            return
        save(path, value)
    monkeypatch.setattr(d.m, 'private', private)
    return calls, edge


@pytest.mark.parametrize('failure', ['before-outbox-stop', 'after-outbox-stop'])
def test_drain_failure_does_not_stop_executors(cutover, monkeypatch, failure):
    calls, edge = cutover
    def wait(label):
        if label == failure:
            raise RuntimeError('busy')
    monkeypatch.setattr(d, 'wait_idle', wait)
    with pytest.raises(RuntimeError, match='busy'):
        d.deploy()
    assert not any(c[:2] == ('systemctl', 'stop') and any(u in c for u in d.UNITS[:2]) for c in calls)
    assert not any(c[0] == 'override' for c in calls)
    assert edge.read_text() == d.closed_config(EDGE)
    assert (d.WORK / 'FAILURE.json').exists()


def test_new_worker_failure_keeps_intake_closed(cutover, monkeypatch):
    calls, edge = cutover
    def wait(label):
        calls.append(('drain', label))
        if label == 'new-workers-ready':
            raise RuntimeError('unknown new worker')
    monkeypatch.setattr(d, 'wait_idle', wait)
    with pytest.raises(RuntimeError, match='unknown new worker'):
        d.deploy()
    stop = ('systemctl', 'stop', *d.UNITS[:2])
    assert calls.index(('drain', 'after-outbox-stop')) < calls.index(stop)
    assert edge.read_text() == d.closed_config(EDGE)
    assert ('docker', 'start', *d.APIS) not in calls


def test_prior_attempt_cannot_replay(cutover):
    (d.WORK / 'DEPLOY_STARTED').write_text('started')
    with pytest.raises(AssertionError, match='prior attempt'):
        d.deploy()
