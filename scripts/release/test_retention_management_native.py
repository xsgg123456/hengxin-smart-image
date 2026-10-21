import importlib.util
import json
from pathlib import Path, PurePosixPath

import pytest

spec = importlib.util.spec_from_file_location('retention_native', Path(__file__).with_name('retention-management-native.py'))
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)
TARGET = '/opt/hengxin-native-releases/domestic-retention-20261021-abcdef0/backend'


def rows():
    result = {}
    for unit in n.UNITS:
        root = '/opt/hengxin-native-releases/' + ('domestic-codex-auth-20261019' if unit == n.UNIT else 'domestic-retire-old') + '/backend'
        argv = [root + '/.venv/bin/python']
        argv += [root + '/.venv/bin/celery', '-A', 'app.worker.celery_app:celery_app'] if unit == n.UNIT else ['-m', 'app.retention.worker', '--loop']
        if unit == n.DELETE:
            argv += ['--deletions-only', '--interval', '5']
        result[unit] = dict(cwd=root, argv=argv, pid=1, policy={'SupplementaryGroups': 'hengxin-codex-auth'},
            environment={'CLI_RETENTION_ENABLED': 'true', 'CODEX_AUTH_BROKER_SOCKET': '/run/broker', 'INVOCATION_ID': 'old'})
    return result


def test_different_old_directories_and_original_commands_preserved():
    for row in rows().values():
        value = n.render(row, TARGET)
        assert row['cwd'] not in value
        assert 'WorkingDirectory=' + TARGET in value
        assert 'Environment=' not in value and 'SupplementaryGroups=' not in value
    assert '--deletions-only' in n.render(rows()[n.DELETE], TARGET)
    assert 'app.worker.celery_app:celery_app' in n.render(rows()[n.UNIT], TARGET)


@pytest.mark.parametrize('bad', ['bad\nvalue', 'bad%value', 'bad$value', 'bad"value', 'bad\\value'])
def test_systemd_argument_injection_rejected(bad):
    row = rows()[n.UNIT]
    row['argv'].append(bad)
    with pytest.raises(AssertionError):
        n.render(row, TARGET)


def test_prepare_uses_latest_cli_dependencies_without_requiring_equal_cwds(monkeypatch, tmp_path):
    events = []
    monkeypatch.setattr(n.m, 'prepare_domestic_native', lambda source, release, previous:
        events.append(('prepare', previous)) or PurePosixPath(TARGET))
    monkeypatch.setattr(n.m, 'private', lambda path, body: events.append((path.name, body)))
    monkeypatch.setattr(n.m, 'run', lambda *args, **kw: events.append(args))
    n.prepare(tmp_path, tmp_path / 'src', 'release', rows())
    assert events[0] == ('prepare', Path(rows()[n.UNIT]['cwd']))
    assert len([event for event in events if event[0].endswith('.conf')]) == 3


def test_native_stop_never_uses_systemd_timeout_escalation(monkeypatch):
    events = []
    monkeypatch.setattr(n, 'show', lambda unit, key: 'on-failure' if key == 'Restart' else '101')
    monkeypatch.setattr(n.m, 'run', lambda *args, **kw: events.append(args) or '0')
    n.stop(n.UNIT)
    assert events[0] == ('systemctl', 'kill', '--kill-whom=main', '--signal=SIGTERM', n.UNIT)
    assert all('SIGKILL' not in str(e) and 'stop' not in e for e in events)


def test_restart_always_refuses_signal_stop(monkeypatch):
    monkeypatch.setattr(n, 'show', lambda *_: 'always')
    monkeypatch.setattr(n.m, 'run', lambda *_args, **_kw: pytest.fail('Must not signal'))
    with pytest.raises(AssertionError):
        n.stop(n.UNIT)


def test_stop_refuses_restarted_pid(monkeypatch):
    monkeypatch.setattr(n, 'show', lambda unit, key: 'on-failure' if key == 'Restart' else '101')
    monkeypatch.setattr(n.m, 'run', lambda *args, **kw: '202')
    with pytest.raises(AssertionError, match='restarted'):
        n.stop(n.UNIT)


def test_switch_last_override_only_after_all_three_are_stopped(monkeypatch, tmp_path):
    monkeypatch.setattr(n, 'SYSTEMD', tmp_path / 'units')
    n.SYSTEMD.mkdir()
    for unit in n.UNITS:
        (tmp_path / (unit + '.conf')).write_text(n.render(rows()[unit], TARGET))
    (tmp_path / 'native-target').write_text(TARGET)
    monkeypatch.setattr(n, 'show', lambda unit, key: '0' if key == 'MainPID' else TARGET)
    monkeypatch.setattr(n.m, 'run', lambda *args, **kw: None)
    monkeypatch.setattr(n.m, 'private', lambda path, value: path.write_text(value))
    n.switch(tmp_path)
    for unit in n.UNITS:
        assert (n.SYSTEMD / (unit + '.service.d') / 'zzzzz-retention-management.conf').exists()


@pytest.mark.parametrize('field', ['policy', 'environment', 'argv'])
def test_verify_rejects_policy_env_or_command_drift(monkeypatch, tmp_path, field):
    before = rows()
    (tmp_path / 'native-snapshots.private.json').write_text(json.dumps(before))
    (tmp_path / 'native-target').write_text(TARGET)
    after = json.loads(json.dumps(before))
    for unit, row in after.items():
        row.update(cwd=TARGET, pid=2, argv=n.target_argv(before[unit], TARGET))
        row['environment']['INVOCATION_ID'] = 'new'
    monkeypatch.setattr(n, 'snapshot', lambda unit: after[unit])
    n.verify(tmp_path)
    if field == 'argv':
        after[n.UNIT][field].append('--bad')
    else:
        after[n.UNIT][field]['extra'] = 'changed'
    with pytest.raises(AssertionError):
        n.verify(tmp_path)


@pytest.mark.parametrize('bad', [None, 'ping', 'queue', 'pool'])
def test_readiness_imports_current_modules_and_checks_actual_worker(monkeypatch, capsys, bad):
    from types import SimpleNamespace
    import sys
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'hengxin-smart-image/backend'))
    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://test:test@localhost/retention_test')
    monkeypatch.setenv('MINIO_ACCESS_KEY', 'test')
    monkeypatch.setenv('MINIO_SECRET_KEY', 'test-secret')
    from app.worker.celery_app import celery_app
    inspector = SimpleNamespace(
        ping=lambda: None if bad == 'ping' else {'worker': {'ok': 'pong'}},
        active_queues=lambda: {'worker': [{'name': 'wrong' if bad == 'queue' else 'celery'}]},
        stats=lambda: {'worker': {'pool': {'max-concurrency': 1 if bad == 'pool' else 5}}})
    monkeypatch.setattr(celery_app.control, 'inspect', lambda **kw: inspector)
    if bad:
        with pytest.raises(AssertionError):
            exec(n.READINESS, {})
    else:
        exec(n.READINESS, {})
        assert capsys.readouterr().out.strip() == 'NATIVE_WORKER_READY'
        assert 'app.modules.api_image_edits.conversation_runner' in sys.modules


@pytest.mark.parametrize('drift', [False, True])
def test_ready_uses_snapshot_environment_and_rejects_pid_drift(monkeypatch, tmp_path, drift):
    from types import SimpleNamespace
    row = rows()[n.UNIT]
    monkeypatch.setattr(n, 'snapshot', lambda _: row)
    monkeypatch.setattr(n, 'show', lambda *_: '2' if drift else '1')
    def run(argv, **kw):
        assert argv[:4] == ['runuser', '-u', 'codex', '--']
        assert kw['env']['PYTHONPATH'] == str(Path(row['cwd']))
        assert kw['env']['CODEX_AUTH_BROKER_SOCKET'] == '/run/broker'
        assert kw['timeout'] <= 20
        return SimpleNamespace(returncode=0, stdout='NATIVE_WORKER_READY\n', stderr='')
    monkeypatch.setattr(n.subprocess, 'run', run)
    if drift:
        with pytest.raises(AssertionError, match='restarted'):
            n.ready(tmp_path)
    else:
        n.ready(tmp_path)


def test_ready_timeout_remains_bounded(monkeypatch, tmp_path):
    monkeypatch.setattr(n.m, 'private', lambda path, value: path.write_text(value))
    monkeypatch.setattr(n, 'snapshot', lambda _: rows()[n.UNIT])
    clock = iter([0, 0, 2, 2])
    monkeypatch.setattr(n.time, 'monotonic', lambda: next(clock))
    monkeypatch.setattr(n.time, 'sleep', lambda _: None)
    def expired(*args, **kw):
        raise n.subprocess.TimeoutExpired(args[0], kw['timeout'])
    monkeypatch.setattr(n.subprocess, 'run', expired)
    with pytest.raises(AssertionError, match='readiness'):
        n.ready(tmp_path, timeout=1)
    assert 'timed out' in (tmp_path / 'native-readiness.private.log').read_text()
