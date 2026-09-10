from uuid import UUID, uuid4
import pytest
from sqlalchemy import select, func
from app.core.config import get_settings
from app.models import Outbox
from app.resource_models import UserRecord
from app.modules.tasks.models import RoundRecord, TaskRecord
from app.modules.tasks.attempts import ExecutionSession, ExecutionAttempt
from app.execution.fixture_runner import run_generation
from files_helpers import files_env
from test_tasks import task_env, submit, body, job_for


def revise(env, receipt, key='revision', **changes):
    data = dict(taskId=receipt['taskId'], target=None, note='增强文字')
    data.update(changes)
    return env[0].post('/api/v1/tasks/' + receipt['taskId'] + '/rounds',
                       json=data, headers={'Idempotency-Key': key})


def ready(env, mode='text'):
    receipt = submit(env, body(env, mode)).json()
    run_generation(job_for(env[1], receipt), env[1], env[2])
    return receipt


def detail(env, receipt):
    return env[0].get('/api/v1/tasks/' + receipt['taskId']).json()


def change_state(env, receipt, state):
    with env[1].begin() as session:
        session.get(RoundRecord, UUID(receipt['roundId'])).status = state


def test_revision_replay_keeps_old_images_until_success(task_env):
    receipt = ready(task_env, 'wallpaper')
    before = detail(task_env, receipt)
    assert before['executionControl'] == dict(canRevise=True, canRetry=False, blockedReason=None)
    response = revise(task_env, receipt, target=1)
    assert response.status_code == 202, response.text
    accepted = response.json()
    assert revise(task_env, receipt, target=1).json() == accepted
    assert revise(task_env, receipt, target=1, note='不同意见').status_code == 409
    assert revise(task_env, receipt, key='other').status_code == 409
    during = detail(task_env, receipt)
    assert during['slots'] == before['slots']
    assert not during['executionControl']['canRevise']
    with task_env[1]() as session:
        assert session.scalar(select(func.count()).select_from(RoundRecord)) == 2
        assert session.scalar(select(func.count()).select_from(Outbox)) == 2
    run_generation(job_for(task_env[1], accepted), task_env[1], task_env[2])
    after = detail(task_env, receipt)
    assert after['slots'][0] == before['slots'][0]
    assert len(after['slots'][1]['versions']) == 2
    assert after['slots'][1]['currentVersionId'] != before['slots'][1]['currentVersionId']


@pytest.mark.parametrize('changes', [dict(taskId='bad'), dict(taskId=str(uuid4())),
    dict(target=-1), dict(target=True), dict(target=1.1), dict(target='0'),
    dict(target=9), dict(note=''), dict(note=' '), dict(note='x'*1001),
    dict(sourceRoundId='bad')])
def test_revision_input_rejects_invalid_values(task_env, changes):
    receipt = ready(task_env)
    assert revise(task_env, receipt, **changes).status_code == 422


def test_header_and_path_required(task_env):
    receipt = ready(task_env)
    data = dict(taskId=receipt['taskId'], target=None, note='意见')
    path = '/api/v1/tasks/' + receipt['taskId'] + '/rounds'
    assert task_env[0].post(path, json=data).status_code == 422
    assert revise(task_env, receipt, key=' ').status_code == 422
    assert task_env[0].post('/api/v1/tasks/bad/rounds', json=data,
        headers={'Idempotency-Key': 'key'}).status_code == 422


@pytest.mark.parametrize('status', ['queued', 'running', 'collecting', 'cancelling', 'uncertain'])
def test_all_active_states_block_new_rounds(task_env, status):
    receipt = ready(task_env)
    change_state(task_env, receipt, status)
    control = detail(task_env, receipt)['executionControl']
    assert not control['canRevise'] and not control['canRetry'] and control['blockedReason']
    assert revise(task_env, receipt).status_code == 409
    assert revise(task_env, receipt, retry=True, sourceRoundId=receipt['roundId']).status_code == 409


@pytest.mark.parametrize('state', ['failed', 'partial'])
def test_retry_freezes_source_note_target_and_replays(task_env, state):
    receipt = ready(task_env)
    change_state(task_env, receipt, state)
    assert detail(task_env, receipt)['executionControl']['canRetry']
    args = dict(retry=True, sourceRoundId=receipt['roundId'], note='修改文字')
    assert revise(task_env, receipt, **{**args, 'sourceRoundId': str(uuid4())}).status_code == 409
    assert revise(task_env, receipt, **{**args, 'note': '新意见'}).status_code == 409
    assert revise(task_env, receipt, **{**args, 'target': 0}).status_code == 409
    response = revise(task_env, receipt, **args)
    assert response.status_code == 202, response.text
    assert revise(task_env, receipt, **args).json() == response.json()
    run_generation(job_for(task_env[1], response.json()), task_env[1], task_env[2])
    assert revise(task_env, receipt, key='stale', **args).status_code == 409


@pytest.mark.parametrize('role', ['super_admin', 'design_manager', 'designer', 'operator'])
def test_cross_owner_actor_and_permission_before_replay(task_env, role):
    receipt = ready(task_env)
    with task_env[1].begin() as session:
        user = UserRecord(id=uuid4(), name='返工者', role=role, status='active', identity_source='development')
        session.add(user)
        task_env[3][0] = user.id
    response = revise(task_env, receipt)
    assert response.status_code == 202
    with task_env[1].begin() as session:
        assert session.get(RoundRecord, UUID(response.json()['roundId'])).operator_id == user.id
        session.get(UserRecord, user.id).status = 'disabled'
    assert revise(task_env, receipt).status_code == 403
    task_env[3][0] = None
    assert revise(task_env, receipt).status_code == 401


def test_executor_source_and_cli_missing_identity(task_env, monkeypatch):
    receipt = ready(task_env)
    monkeypatch.setattr(get_settings(), 'enable_fixture_executor', False)
    monkeypatch.setattr(get_settings(), 'enable_codex_executor', True)
    assert not detail(task_env, receipt)['executionControl']['canRevise']
    assert revise(task_env, receipt).status_code == 409
    with task_env[1].begin() as session:
        session.get(TaskRecord, UUID(receipt['taskId'])).execution_source = 'cli'
    assert not detail(task_env, receipt)['executionControl']['canRevise']
    change_state(task_env, receipt, 'failed')
    assert detail(task_env, receipt)['executionControl']['canRetry']
    with task_env[1].begin() as session:
        session.add(ExecutionSession(task_id=UUID(receipt['taskId'])))
    assert not detail(task_env, receipt)['executionControl']['canRetry']
    with task_env[1].begin() as session:
        session.get(ExecutionSession, UUID(receipt['taskId'])).session_id = 'real-session'
    assert detail(task_env, receipt)['executionControl']['canRevise']


def test_retry_empty_initial_note_preserved(task_env):
    receipt = ready(task_env)
    with task_env[1].begin() as session:
        current = session.get(RoundRecord, UUID(receipt['roundId']))
        current.note, current.status = '', 'failed'
    assert revise(task_env, receipt, retry=True, sourceRoundId=receipt['roundId'], note='').status_code == 202


@pytest.mark.parametrize('attempt_status,pid,allowed', [
    ('finished', None, True), ('finished', 123, False), ('starting', None, False),
    ('uncertain', None, False)])
def test_empty_cli_session_only_retries_known_unstarted_attempt(task_env, monkeypatch,
        attempt_status, pid, allowed):
    receipt = ready(task_env)
    monkeypatch.setattr(get_settings(), 'enable_codex_executor', True)
    with task_env[1].begin() as session:
        task = session.get(TaskRecord, UUID(receipt['taskId']))
        task.execution_source = 'cli'
        session.get(RoundRecord, UUID(receipt['roundId'])).status = 'failed'
        session.add(ExecutionSession(task_id=task.id))
        session.add(ExecutionAttempt(task_id=task.id, round_id=UUID(receipt['roundId']),
            operator_id=task.owner_id, claim_token=uuid4(), node='test', workspace='isolated',
            cli_version='test', status=attempt_status, process_id=pid))
    control = detail(task_env, receipt)['executionControl']
    assert not control['canRevise'] and control['canRetry'] is allowed
    result = revise(task_env, receipt, retry=True, sourceRoundId=receipt['roundId'], note='修改文字')
    assert result.status_code == (202 if allowed else 409)


def test_integrity_race_rolls_back_and_returns_conflict(task_env, monkeypatch):
    from sqlalchemy.orm import Session
    from sqlalchemy.exc import IntegrityError
    receipt = ready(task_env)
    def conflict(session):
        raise IntegrityError('injected concurrent constraint conflict', {}, Exception('conflict'))
    monkeypatch.setattr(Session, 'commit', conflict)
    response = revise(task_env, receipt)
    assert response.status_code == 409, response.text
    with task_env[1]() as session:
        assert session.scalar(select(func.count()).select_from(RoundRecord)) == 1
        assert session.scalar(select(func.count()).select_from(Outbox)) == 1
