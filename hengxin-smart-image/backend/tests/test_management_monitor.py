from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4
import subprocess

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError
from sqlalchemy import event, select
from app.execution.diagnostics import failure_for
from app.core.config import get_settings
from app.models import Job, utcnow
from app.modules.management import health
from app.modules.management.monitor_router import router
from app.modules.tasks.attempts import ExecutionAttempt, ExecutionSession, WorkerHeartbeat
from app.modules.tasks.models import RoundRecord, TaskRecord
from app.resource_models import UserRecord
from app.worker import health as worker_health
from files_helpers import files_env
from test_tasks import body, submit, task_env
@pytest.fixture
def monitor_env(task_env, monkeypatch):
    client, factory, _, identity = task_env
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'super_admin'
    app = FastAPI()
    app.include_router(router, prefix='/api/v1')
    app.dependency_overrides.update(client.app.dependency_overrides)
    monkeypatch.setattr(health, 'dependency_checks', lambda: dict(
        postgresql='up', redis='up', minio='up'))
    with TestClient(app, raise_server_exceptions=False) as monitor:
        yield monitor, task_env

def heartbeat(env, *, age=0, state='ready', extra=None):
    with env[1].begin() as session:
        session.merge(WorkerHeartbeat(node='test-node', checked_at=utcnow()-timedelta(seconds=age),
            state=state, dependencies=dict(cli=True, isolation=True, authenticationConfigured=True,
            **(extra or {}))))
def report(monitor):
    response = monitor.get('/api/v1/management/monitor')
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['taskCount'] is None or data['taskCount'] >= len(data['tasks'])
    return data

def test_fresh_idle_and_legacy_fields_unknown(monitor_env):
    monitor, env = monitor_env
    heartbeat(env)
    data = report(monitor)
    assert data['state'] == 'idle'
    assert data['queueSize'] == data['runningCount'] == data['taskCount'] == 0
    assert data['detail']['cliVersion'] is None
    assert data['detail']['freeDiskBytes'] is None
    assert data['detail']['workers'][0]['concurrency'] == get_settings().generation_concurrency
    assert data['detail']['dependencies'][-1]['state'] == 'unknown'
    heartbeat(env, extra=dict(cliVersion='0.153.4', concurrency=2, freeDiskBytes=123456))
    data = report(monitor)
    assert data['detail']['freeDiskBytes'] == 123456
    assert data['detail']['cliVersion'] == '0.153.4'
    assert data['detail']['configured'] is True
@pytest.mark.parametrize('age', [31, -60, None])
def test_stale_future_and_missing_heartbeat_unknown(monitor_env, age):
    monitor, env = monitor_env
    if age is not None:
        heartbeat(env, age=age, extra=dict(cliVersion='0.153.4', freeDiskBytes=99, concurrency=2))
    data = report(monitor)
    assert data['state'] == 'unknown'
    assert data['detail']['configured'] is None
    assert data['detail']['freeDiskBytes'] is None
    assert data['detail']['cliVersion'] is None
    if age is not None:
        assert data['detail']['workers'][0]['state'] == 'unknown'
@pytest.mark.parametrize('dependency', ['postgresql', 'redis', 'minio', 'worker'])
def test_dependency_failure_is_unavailable(monitor_env, monkeypatch, dependency):
    monitor, env = monitor_env
    heartbeat(env, state='unavailable' if dependency == 'worker' else 'ready')
    checks = dict(postgresql='up', redis='up', minio='up')
    if dependency != 'worker':
        checks[dependency] = 'down'
    monkeypatch.setattr(health, 'dependency_checks', lambda: checks)
    data = report(monitor)
    assert data['state'] == 'unavailable'
    assert data['issue']['code'] == 'EXECUTION_UNAVAILABLE'
    if dependency != 'worker':
        assert next(x for x in data['detail']['dependencies'] if x['name'] == dependency)[
            'state'] == 'unavailable'

def running_task(env, status='running', error=None):
    receipt = submit(env, body(env), key=str(uuid4())).json()
    with env[1].begin() as session:
        round_ = session.get(RoundRecord, UUID(receipt['roundId']))
        operator = UserRecord(id=uuid4(), name='实际操作者', role='designer', status='active',
                              identity_source='development')
        session.add(operator)
        session.flush()
        round_.status, round_.started_at, round_.error = status, utcnow()-timedelta(seconds=20), error
        session.get(Job, round_.job_id).status = status
        finished = utcnow() if status in ('failed', 'succeeded') else None
        round_.finished_at = finished
        session.add(ExecutionAttempt(round_id=round_.id, task_id=round_.task_id,
            operator_id=operator.id, claim_token=uuid4(), node='test-node', workspace='/secret/path',
            cli_version='0.153.4', status='finished' if finished else 'running',
            started_at=round_.started_at, finished_at=finished, error=error))
        session.add(ExecutionSession(task_id=round_.task_id, session_id='private-session'))
    return receipt

def test_pg_queue_running_actual_operator_and_manager_redaction(monitor_env):
    monitor, env = monitor_env
    heartbeat(env)
    running_task(env)
    submit(env, body(env), key='queued')
    data = report(monitor)
    assert data['state'] == 'running'
    assert (data['runningCount'], data['queueSize']) == (1, 1)
    task = next(x for x in data['tasks'] if x['state'] == '执行中')
    assert task['operatorName'] == '实际操作者'
    assert task['sessionId'] == 'private-session'
    assert task['elapsedSeconds'] >= 20
    assert data['detail']['workers'][0]['runningCount'] == 1
    with env[1].begin() as session:
        session.get(UserRecord, env[3][0]).role = 'design_manager'
    data = report(monitor)
    assert data['detail'] is None
    assert all(task['sessionId'] is None for task in data['tasks'])
    assert 'private-session' not in str(data) and '/secret/path' not in str(data)
@pytest.mark.parametrize('role,status,expected', [
    ('designer', 'active', 403), ('operator', 'active', 403),
    ('super_admin', 'disabled', 403), ('design_manager', 'pending', 403),
    ('super_admin', 'active', 200), ('design_manager', 'active', 200),
])
def test_permission_rechecked(monitor_env, monkeypatch, role, status, expected):
    monitor, env = monitor_env
    with env[1].begin() as session:
        user = session.get(UserRecord, env[3][0])
        user.role, user.status = role, status
    if expected == 403:
        monkeypatch.setattr(health, 'dependency_checks', lambda: pytest.fail('unauthorized probe'))
    assert monitor.get('/api/v1/management/monitor').status_code == expected
@pytest.mark.parametrize('error,expected', [
    ('authentication_failed', '认证失败'), ('rate_limited', '限流'), ('timeout', '执行时限'),
    ('Bearer secret-token /secret/path https://user:password@internal traceback', '原因暂未确定'),
])
def test_errors_are_fixed_diagnostics_and_history_not_health(monitor_env, error, expected):
    monitor, env = monitor_env
    running_task(env, 'failed', error)
    data = report(monitor)
    assert data['state'] == 'unknown'
    assert expected in data['tasks'][0]['error']
    assert expected in data['detail']['lastResult']
    assert 'secret-token' not in str(data) and 'password' not in str(data)
    with env[1].begin() as session:
        session.get(UserRecord, env[3][0]).role = 'design_manager'
    data = report(monitor)
    assert expected in data['tasks'][0]['error'] and data['detail'] is None

def test_database_failure_explicitly_unknown():
    class BrokenSession:
        def get(self, *args):
            raise OperationalError('secret-query', {}, Exception('secret-password'))
        def execute(self, query):
            raise OperationalError('secret-query', {}, Exception('secret-password'))
        def rollback(self):
            pass
    data = health.build_monitor(BrokenSession(), SimpleNamespace(role='super_admin'))
    assert data['state'] == 'unknown' and data['issue']['code'] == 'MONITOR_UNAVAILABLE'
    assert data['queueSize'] is data['runningCount'] is data['taskCount'] is None
    assert 'secret' not in str(data)
@pytest.mark.parametrize('version', ['codex-cli 0.153.4', 'codex-cli 0.1.0', 'secret output', None])
def test_worker_samples_version_disk_and_readiness(monitor_env, monkeypatch, tmp_path, version):
    _, env = monitor_env
    auth = tmp_path / 'auth.json'
    auth.write_text('{}')
    settings = get_settings()
    monkeypatch.setattr(settings, 'codex_binary', 'codex-test')
    monkeypatch.setattr(settings, 'codex_version', '0.153.4')
    monkeypatch.setattr(settings, 'codex_bwrap_binary', str(auth))
    monkeypatch.setattr(settings, 'codex_auth_file', str(auth))
    monkeypatch.setattr(settings, 'codex_execution_root', str(tmp_path))
    monkeypatch.setattr(worker_health.os, 'access', lambda *args: True)
    def run(argv, **kwargs):
        assert argv == ['codex-test', '--version'] and kwargs['timeout'] == 2
        if version is None:
            raise subprocess.TimeoutExpired(argv, 2)
        return SimpleNamespace(returncode=0, stdout=version)
    monkeypatch.setattr(worker_health.subprocess, 'run', run)
    sampled = []
    def disk(path):
        sampled.append(path)
        return SimpleNamespace(free=987654)
    monkeypatch.setattr(worker_health.shutil, 'disk_usage', disk)
    worker_health.pulse(env[1], concurrency=2)
    assert sampled == [str(tmp_path)]
    with env[1]() as session:
        beat = session.get(WorkerHeartbeat, settings.worker_node_name)
        assert beat.dependencies['freeDiskBytes'] == 987654
        assert beat.dependencies['concurrency'] == 2
        assert beat.dependencies['capacity'] == 2
        assert beat.state == ('ready' if version == 'codex-cli 0.153.4' else 'unavailable')
        assert 'secret' not in str(beat.dependencies)

def test_worker_missing_disk_keeps_unknown(monitor_env, monkeypatch):
    _, env = monitor_env
    monkeypatch.setattr(worker_health.subprocess, 'run', lambda *a, **k:
                        SimpleNamespace(returncode=1, stdout=''))
    def unavailable(path):
        raise OSError('private-worker-path')
    monkeypatch.setattr(worker_health.shutil, 'disk_usage', unavailable)
    worker_health.pulse(env[1])
    with env[1]() as session:
        data = session.get(WorkerHeartbeat, get_settings().worker_node_name).dependencies
        assert data['freeDiskBytes'] is None and data['concurrency'] is None
        assert 'private-worker-path' not in str(data)
@pytest.mark.parametrize('target,capacity,expected', [(1, 2, 1), (3, 2, 2), (3, 4, 3)])
def test_config_target_does_not_invent_pool_expansion(monitor_env, monkeypatch, target, capacity, expected):
    monitor, env = monitor_env
    monkeypatch.setattr(health, 'values', lambda session: {'concurrency': target})
    heartbeat(env, extra={'capacity': capacity})
    assert report(monitor)['detail']['workers'][0]['concurrency'] == expected

def test_recent_success_does_not_replace_stale_heartbeat(monitor_env):
    monitor, env = monitor_env
    running_task(env, 'succeeded')
    heartbeat(env, age=90)
    data = report(monitor)
    assert data['state'] == 'unknown'
    assert data['detail']['lastResult'] == '执行成功'
    assert data['tasks'] == []

def test_anonymous_cannot_probe(monitor_env, monkeypatch):
    from app.modules.auth.dependencies import get_identity_id
    monitor, _ = monitor_env
    monitor.app.dependency_overrides.pop(get_identity_id)
    monkeypatch.setattr(get_settings(), 'enable_dev_identity', False)
    monkeypatch.setattr(health, 'dependency_checks', lambda: pytest.fail('anonymous probe'))
    assert monitor.get('/api/v1/management/monitor').status_code == 401
@pytest.mark.parametrize('stored,legacy,expected', [
    (failure_for('invalid_output_manifest', 'validating'), '执行失败', '输出清单缺失或不符合约定'),
    (failure_for('authentication_failed', 'starting'), '执行失败', '图片执行工具认证失败'),
    (failure_for('rate_limited', 'generating'), '执行失败', '图片执行工具请求受到限流'),
    ({'code': 'UNKNOWN'}, 'timeout', '图片处理超过执行时限'),
    ({'code': ['OUTPUT_MANIFEST_INVALID']}, 'timeout', '图片处理超过执行时限'),
    ('malformed', None, '本轮处理失败，历史记录未保留详细诊断'),
    (None, '输出清单缺失或不符合约定', '输出清单缺失或不符合约定'),
    ({'code': 'UNRECOGNIZED'}, 'private-secret', '图片处理失败，原因暂未确定'),
])
def test_stored_progress_diagnostic_rebuilt_for_monitor(monitor_env, stored, legacy, expected):
    monitor, env = monitor_env
    receipt = running_task(env, 'failed', legacy)
    if isinstance(stored, dict):
        stored = {**stored, 'message': 'private-secret', 'action': 'private-secret',
                  'slotErrors': [{'slot': 0, 'message': 'private-secret'}]}
    with env[1].begin() as session:
        attempt = session.scalar(select(ExecutionAttempt).where(
            ExecutionAttempt.round_id == UUID(receipt['roundId'])))
        attempt.observation = {'stage': 'failed', 'failure': stored, 'events': [],
            'totalImages': 1, 'detectedImages': None, 'lastActivityAt': None,
            'updatedAt': utcnow().isoformat()} if stored is not None else None
    for role in ('super_admin', 'design_manager'):
        with env[1].begin() as session:
            session.get(UserRecord, env[3][0]).role = role
        data = report(monitor)
        assert data['tasks'][0]['error'] == expected
        if role == 'super_admin':
            assert data['detail']['lastResult'] == expected
        else:
            assert data['detail'] is None
        assert 'private-secret' not in str(data)
@pytest.mark.parametrize('recent_state', ['queued', 'failed', 'partial'])
def test_all_active_survive_101_newer_tasks_and_total_is_untruncated(monitor_env, recent_state):
    monitor, env = monitor_env
    payload = body(env)
    receipts = [submit(env, payload, key=f'crowded-{index}').json() for index in range(107)]
    with env[1].begin() as session:
        for index, receipt in enumerate(receipts):
            round_ = session.get(RoundRecord, UUID(receipt['roundId']))
            round_.status = health.RUNNING[index] if index < 4 else recent_state
            round_.updated_at = utcnow() + timedelta(seconds=index)
            session.get(Job, round_.job_id).status = round_.status
        # 4 active + 101 recent; neither deleted nor successful tasks count.
        session.get(TaskRecord, UUID(receipts[-1]['taskId'])).deleted_at = utcnow()
        session.get(RoundRecord, UUID(receipts[-2]['roundId'])).status = 'succeeded'
    for role in ('super_admin', 'design_manager'):
        with env[1].begin() as session:
            session.get(UserRecord, env[3][0]).role = role
        statements, engine = [], env[1].kw['bind']
        def capture(conn, cursor, statement, parameters, context, executemany):
            if statement.startswith('SELECT') and 'FROM task_records' in statement:
                statements.append(statement)
        event.listen(engine, 'before_cursor_execute', capture)
        try:
            data = report(monitor)
        finally:
            event.remove(engine, 'before_cursor_execute', capture)
        assert len(statements) == 1 and all(x in statements[0] for x in ('UNION ALL', 'AS total_count'))
        ids = [task['taskId'] for task in data['tasks']]
        assert data['taskCount'] == 105 and len(ids) == len(set(ids)) == 104
        assert ids[:4] == [item['taskId'] for item in reversed(receipts[:4])]
        assert ids[4:] == [item['taskId'] for item in reversed(receipts[5:105])]
        assert receipts[4]['taskId'] not in ids
