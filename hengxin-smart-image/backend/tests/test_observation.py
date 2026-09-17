import importlib.util
import json
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, inspect, select, text

from app.execution.observation import EventTail, Observer
from app.execution.workspace import Workspace
from app.models import Job
from app.modules.tasks.attempts import ExecutionAttempt
from app.modules.tasks.claims import claim, end, locked_execution
from app.modules.tasks.models import RoundRecord
from app.resource_models import UserRecord
from files_helpers import files_env  # noqa: F401
from test_tasks import task_env, submit, job_for  # noqa: F401


def test_tail_handles_partial_unicode_and_never_exposes_raw_content(tmp_path):
    path = tmp_path / 'events'
    raw = json.dumps({'type': 'item.completed', 'item': {'type': 'command_execution',
                     'aggregated_output': '秘密 token=secret /home/private'}}).encode() + b'\n'
    path.write_bytes(raw[:30])
    tail = EventTail()
    assert tail.read(path) == []
    with path.open('ab') as stream:
        stream.write(raw[30:])
    assert tail.read(path) == ['一次工具调用已结束']
    assert tail.read(path) == []


def test_tail_skips_malformed_oversize_and_thinking(tmp_path):
    path = tmp_path / 'events'
    path.write_bytes(b'x' * (300 * 1024) + b'\n' + b'{"type":[]}\n' +
        b'{"type":"item.completed","item":{"type":"reasoning","text":"secret"}}\n' +
        b'{"type":"turn.completed"}\n')
    tail = EventTail()
    assert tail.read(path) == []
    assert tail.read(path) == ['模型本轮处理结束，等待结果校验']


def observing(env, tmp_path):
    receipt = submit(env).json()
    factory = env[1]
    job = job_for(factory, receipt)
    token = claim(factory, job)
    with factory.begin() as session:
        attempt = ExecutionAttempt(round_id=UUID(receipt['roundId']), task_id=UUID(receipt['taskId']),
            operator_id=env[3][0], claim_token=token, node='test', workspace=str(tmp_path), cli_version='test')
        session.add(attempt)
        session.flush()
        aid = attempt.id
    ws = Workspace(tmp_path / 'home', tmp_path / 'work', tmp_path / 'control')
    for p in (ws.home, ws.work, ws.control):
        p.mkdir()
    return receipt, Observer(factory, job, token, aid, ws, 1)


def test_observations_are_durable_and_stale_claim_cannot_write(task_env, tmp_path):
    receipt, observer = observing(task_env, tmp_path)
    observer.phase('preparing')
    response = task_env[0].get('/api/v1/tasks/' + receipt['taskId'] + '/execution')
    assert response.status_code == 200, response.text
    data = response.json()
    assert data['stage'] == 'preparing' and data['diagnosticId'] == str(observer.attempt_id)
    assert not data['legacy'] and data['totalImages'] == 1
    with task_env[1].begin() as session:
        session.get(Job, observer.job_id).claim_token = uuid4()
    observer.phase('storing')
    assert task_env[0].get('/api/v1/tasks/' + receipt['taskId'] + '/execution').json()['stage'] == 'preparing'


def test_database_terminal_state_overrides_old_heartbeat(task_env, tmp_path):
    receipt, observer = observing(task_env, tmp_path)
    observer.phase('generating')
    with task_env[1].begin() as session:
        _, round, job = locked_execution(session, observer.job_id)
        end(session, round, job, 'cancelled')
    data = task_env[0].get('/api/v1/tasks/' + receipt['taskId'] + '/execution').json()
    assert data['stage'] == 'cancelled' and data['status'] == 'cancelled'


def test_round_ownership_deleted_task_and_legacy_are_checked(task_env):
    one = submit(task_env, key='one').json()
    two = submit(task_env, key='two').json()
    client = task_env[0]
    endpoint = '/api/v1/tasks/' + one['taskId'] + '/execution'
    data = client.get(endpoint).json()
    assert data['legacy'] and data['events'] == [] and data['stage'] == 'queued'
    assert client.get(endpoint, params={'roundId': two['roundId']}).status_code == 404
    client.delete('/api/v1/tasks/' + one['taskId'])
    assert client.get(endpoint).status_code == 404


def test_observation_is_best_effort_and_bounded(task_env, tmp_path, monkeypatch):
    _, observer = observing(task_env, tmp_path)
    for i in range(110):
        observer.event(f'模型活动 {i}')
    assert len(observer.data['events']) == 100
    monkeypatch.setattr(observer.tail, 'read', lambda *args: (_ for _ in ()).throw(OSError('secret')))
    observer.tick(force=True)  # Must not interrupt the actual CLI.


def test_public_messages_reach_api_without_reasoning_and_deduplicate(task_env, tmp_path):
    receipt, observer = observing(task_env, tmp_path)
    event = {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '第 1 张已生成'}}
    hidden = {'type': 'item.completed', 'item': {'type': 'reasoning', 'text': '不要公开'}}
    path = {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': '保存于/用户/私有.png 和 /123/private.png'}}
    secret = {'type': 'item.completed', 'item': {'type': 'agent_message', 'text': 'pass<b></b>word=demo123'}}
    (observer.workspace.control / 'events.jsonl').write_text(
        '\n'.join(json.dumps(e) for e in [event, event, hidden, path, secret]) + '\n', encoding='utf-8')
    observer.tick(force=True)
    endpoint = '/api/v1/tasks/' + receipt['taskId'] + '/execution'
    data = task_env[0].get(endpoint).json()
    assert len(data['events']) == 2
    assert data['events'][0]['message'] == 'Codex：第 1 张已生成'
    assert all(term not in json.dumps(data, ensure_ascii=False) for term in ['私有', '/123', 'private', 'demo123'])
    assert data['events'][0]['at']
    assert data['stage'] != 'completed'  # Model prose never publishes results.
    with task_env[1].begin() as session:
        row = session.get(ExecutionAttempt, observer.attempt_id)
        observation = dict(row.observation)
        observation['events'] = [dict(observation['events'][0], at=None)]
        row.observation = observation
    assert task_env[0].get(endpoint).json()['events'][0]['at'] is None


def test_backfilled_diagnosis_does_not_invent_historical_events(task_env, tmp_path):
    receipt, observer = observing(task_env, tmp_path)
    with task_env[1].begin() as session:
        _, round, job = locked_execution(session, observer.job_id)
        end(session, round, job, 'failed')
        session.get(ExecutionAttempt, observer.attempt_id).observation = {
            'stage': 'failed', 'legacy': True, 'events': []}
    data = task_env[0].get('/api/v1/tasks/' + receipt['taskId'] + '/execution').json()
    assert data['legacy'] and data['events'] == [] and data['status'] == 'failed'


@pytest.mark.parametrize('name', ['jd-main-image-wallpaper-camera-swap',
                                'jd-main-image-wallpaper-camera-swap-it-optimized'])
def test_prepared_skill_name_reaches_persisted_api_observation(task_env, tmp_path, name):
    receipt, observer = observing(task_env, tmp_path)
    # Materials set the name after Observer construction in the production runner.
    observer.workspace.skill_name = name
    event = {'type': 'item.completed', 'item': {'type': 'agent_message',
             'text': f'我会使用“`${name}`”技能，先检查这5张图片。'}}
    (observer.workspace.control / 'events.jsonl').write_text(json.dumps(event) + '\n', encoding='utf-8')
    observer.tick(force=True)
    data = task_env[0].get('/api/v1/tasks/' + receipt['taskId'] + '/execution').json()
    assert data['events'][0]['message'] == f'Codex：我会使用“${name}”技能，先检查这5张图片。'
    assert data['stage'] != 'completed'


def test_zero_or_historical_images_do_not_claim_new_generation(task_env, tmp_path):
    _, observer = observing(task_env, tmp_path)
    root = observer.workspace.home / '.codex/generated_images/session'
    root.mkdir(parents=True)
    observer.phase('generating')
    observer.tick('session', force=True)
    assert observer.data['detectedImages'] == 0
    assert len(observer.data['events']) == 1
    (root / 'old.png').write_bytes(b'old')
    observer.baseline = {'old.png'}
    observer.tick(force=True)
    assert observer.data['detectedImages'] == 0 and len(observer.data['events']) == 1
    (root / 'new.png').write_bytes(b'new')
    observer.tick(force=True)
    assert observer.data['detectedImages'] == 1
    assert observer.data['events'][-1]['message'] == '检测到生成图片，尚待结果校验'
    (root / 'new.png').unlink()
    observer.tick(force=True)
    assert observer.data['detectedImages'] == 0 and len(observer.data['events']) == 2


@pytest.mark.parametrize('status', ['pending', 'disabled'])
def test_observation_respects_user_authorization(task_env, status):
    receipt = submit(task_env).json()
    with task_env[1].begin() as session:
        session.get(UserRecord, task_env[3][0]).status = status
    assert task_env[0].get('/api/v1/tasks/' + receipt['taskId'] + '/execution').status_code == 403


def test_migration_preserves_existing_attempt_rows_and_is_idempotent(monkeypatch):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / 'migrations/versions/0008_execution_observation.py'
    spec = importlib.util.spec_from_file_location('migration_observation', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    engine = create_engine('sqlite://')
    with engine.begin() as connection:
        connection.execute(text('CREATE TABLE execution_attempts (id TEXT PRIMARY KEY)'))
        connection.execute(text("INSERT INTO execution_attempts VALUES ('existing')"))
        monkeypatch.setattr(module, 'op', Operations(MigrationContext.configure(connection)))
        module.upgrade()
        module.upgrade()
        assert connection.execute(text('SELECT observation FROM execution_attempts')).scalar() is None
        assert connection.execute(text('SELECT id FROM execution_attempts')).scalar() == 'existing'
