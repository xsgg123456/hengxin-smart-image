from datetime import timedelta
from types import SimpleNamespace
from uuid import UUID, uuid4
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select, event
from sqlalchemy.exc import OperationalError
from app.models import Job, utcnow
from app.modules.management import api_monitor, execution_settings
from app.modules.api_image_edits.models import ApiTask, ApiItem, ApiAttempt, ApiChannel
from app.modules.api_image_edits.heartbeat_models import ApiWorkerHeartbeat
from app.modules.api_image_edits.conversation_models import Conversation, ConversationTurn
from app.modules.api_image_edits import worker_health
from app.modules.tasks.attempts import WorkerHeartbeat
from app.modules.management.models import SystemSettings
from app.resource_models import UserRecord
from files_helpers import files_env
from test_api_image_domain import enabled_api, create

@pytest.fixture
def env(files_env, monkeypatch):
    client, factory, _, identity = files_env
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'super_admin'
    app = FastAPI()
    app.include_router(api_monitor.router)
    app.include_router(execution_settings.router)
    app.dependency_overrides.update(client.app.dependency_overrides)
    monkeypatch.setattr(api_monitor, 'get_settings', lambda: SimpleNamespace(enable_codex_executor=True))
    with TestClient(app) as management:
        yield management, files_env

def report(env):
    response = env[0].get('/management/api-monitor')
    assert response.status_code == 200, response.text
    return response.json()

def metric(channel, phase):
    return next(row for row in channel['metrics'] if row['phase'] == phase)

@pytest.mark.parametrize('age', [None, 31, -60])
def test_missing_stale_future_heartbeats_preserve_queue(env, age):
    _, original = env
    create(original[0])
    if age is not None:
        with original[1].begin() as session:
            session.add(ApiWorkerHeartbeat(id='api', checked_at=utcnow()-timedelta(seconds=age), state='ready', capacity=5))
            session.add(WorkerHeartbeat(node='cli', checked_at=utcnow()-timedelta(seconds=age), state='ready', dependencies=dict(cli=True,isolation=True,authenticationConfigured=True,capacity=5)))
    data = report(env)
    assert [c['state'] for c in data['channels']] == ['unknown', 'unknown']
    assert metric(data['channels'][0], 'queued')['images'] == 2
    assert all(w['capacity'] is None for c in data['channels'] for w in c['workers'])

def test_independent_heartbeats_pause_retry_history_deleted(env):
    _, original = env
    task_id, _ = create(original[0])
    with original[1].begin() as session:
        items = session.scalars(select(ApiItem).where(ApiItem.task_id == UUID(task_id))).all()
        items[0].state = 'succeeded'; items[1].state = 'retry_wait'
        session.add(ApiAttempt(item_id=items[0].id, operator_id=original[3][0], state='retryable'))
        session.add(WorkerHeartbeat(node='cli', checked_at=utcnow(), state='ready', dependencies=dict(cli=True,isolation=True,authenticationConfigured=True,capacity=5)))
        gate = session.get(ApiChannel, 1)
        gate.paused, gate.reason = True, 'private-secret'
    data = report(env); api, cli = data['channels']
    assert api['state'] == 'unknown' and cli['state'] == 'available'
    assert api['paused'] and 'private-secret' not in str(data)
    assert metric(api, 'failed')['images'] == 0
    assert metric(api, 'retry_wait')['images'] == 1
    assert len(data['incidents']) == 1
    with original[1].begin() as session:
        session.get(ApiTask, UUID(task_id)).deleted_at = utcnow()
    assert metric(report(env)['channels'][0], 'retry_wait')['images'] == 0

def test_cli_latest_turn_and_shared_capacity(env):
    _, original = env
    task_id, _ = create(original[0], count=1)
    with original[1].begin() as session:
        item = session.scalar(select(ApiItem).where(ApiItem.task_id == UUID(task_id)))
        conversation = Conversation(item_id=item.id)
        session.add(conversation); session.flush()
        for index, status in enumerate(('failed','waiting_user')):
            job = Job(idempotency_key=str(uuid4()), payload_hash='x', value='', kind='api_cli_edit', status='succeeded')
            session.add(job); session.flush()
            session.add(ConversationTurn(conversation_id=conversation.id, job_id=job.id, operator_id=original[3][0], status=status,text='',prompt='',snapshot={},base_file_id=item.source_id,created_at=utcnow()+timedelta(seconds=index)))
        session.add(Job(idempotency_key=str(uuid4()),payload_hash='x',value='',kind='generation',status='running'))
    cli = report(env)['channels'][1]
    assert metric(cli, 'failed')['turns'] == 0
    assert cli['otherActiveTurns'] == cli['sharedActiveTurns'] == 1

def test_query_failure_reports_unknown_other_channel_survives(env):
    engine = env[1][1].kw['bind']
    def fail(conn, cursor, statement, params, context, executemany):
        if 'SELECT api_image_tasks.id' in statement and 'api_edit_turns' not in statement:
            raise OperationalError(statement, params, Exception('private'))
    event.listen(engine, 'before_cursor_execute', fail)
    try:
        api, cli = report(env)['channels']
        assert api['queueState'] == 'unknown' and metric(api, 'queued')['images'] is None
        assert cli['queueState'] == 'available'
    finally:
        event.remove(engine, 'before_cursor_execute', fail)

def test_settings_actual_values_no_secrets_and_permissions(env, monkeypatch):
    _, original = env
    monkeypatch.setattr(execution_settings, 'TASK_CONCURRENCY', 7)
    from app.core.config import get_settings
    from app.modules.management import settings as settings_service
    config = get_settings().model_copy(update={'generation_concurrency':8,'codex_timeout_seconds':8000})
    monkeypatch.setattr(execution_settings, 'get_settings', lambda: config)
    monkeypatch.setattr(settings_service, 'get_settings', lambda: config)
    with original[1].begin() as session:
        session.add(SystemSettings(id=1,version=2,values={'concurrency':2,'timeoutSeconds':600,'maxUploadBytes':1048576}))
    data = env[0].get('/management/execution-settings').json()
    assert data['api']['taskConcurrency'] == 7
    assert data['cli']['concurrency'] == 2 and data['cli']['timeoutSeconds'] == 600
    assert data['cli']['model'] == 'gpt-6-astra' and data['cli']['usesSkills'] is False
    assert data['retention'] == {'enabled': False, 'cacheIdleDays': 1, 'historyIdleDays': 7}
    assert 'api_key' not in str(data) and 'broker' not in str(data)
    with original[1].begin() as session:
        session.get(UserRecord, original[3][0]).role = 'design_manager'
    assert env[0].get('/management/execution-settings').status_code == 403
    assert env[0].get('/management/api-monitor').status_code == 200
    with original[1].begin() as session:
        session.get(UserRecord, original[3][0]).role = 'operator'
    assert env[0].get('/management/api-monitor').status_code == 403

def test_real_api_pulse_independent_model(env, monkeypatch):
    monkeypatch.setenv('API_IMAGE_API_KEY', 'private-test-key')
    from app.modules.api_image_edits.config import get_api_settings
    get_api_settings.cache_clear()
    worker_health.pulse(env[1][1], 'api-node', 3)
    api = report(env)['channels'][0]
    assert api['state'] == 'available' and api['workers'][0]['capacity'] == 3
    assert 'private-test-key' not in str(api)
