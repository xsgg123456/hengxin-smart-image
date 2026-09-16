from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from app.models import Job
from app.modules.tasks.attempts import ExecutionAttempt, ExecutionUsage
from app.modules.tasks.models import ImageVersion, ResultSlotRecord, RoundRecord, TaskRecord, TaskSource
from app.resource_models import UserRecord
from files_helpers import files_env
from test_tasks import body, submit, task_env


def _real_attempt(factory, receipt, *, started_at, status='succeeded', operator_id=None,
                  usage=None, output=True, error=None):
    with factory.begin() as session:
        task = session.get(TaskRecord, UUID(receipt['taskId']))
        round = session.get(RoundRecord, UUID(receipt['roundId']))
        job = session.get(Job, round.job_id)
        task.execution_source = 'cli'
        task.created_at = started_at
        round.created_at = started_at - timedelta(seconds=12)
        round.started_at = started_at
        round.status, round.error = status, error
        round.finished_at = started_at + timedelta(seconds=45) if status in ('succeeded', 'partial', 'failed') else None
        job.status = status
        attempt = ExecutionAttempt(
            round_id=round.id, task_id=task.id, operator_id=operator_id or task.owner_id,
            claim_token=uuid4(), node='test-node', workspace='test-workspace',
            cli_version='0.1.0', status='finished' if status in ('succeeded', 'partial', 'failed') else 'running',
            started_at=started_at, finished_at=round.finished_at,
            error=error,
        )
        session.add(attempt)
        session.flush()
        if usage is not None:
            session.add(ExecutionUsage(attempt_id=attempt.id, data=usage))
        if output:
            slot = session.scalar(select(TaskSource).where(TaskSource.task_id == task.id))
            result_slot = session.scalar(select(ResultSlotRecord).where(ResultSlotRecord.task_id == task.id))
            session.add(ImageVersion(slot_id=result_slot.id, round_id=round.id, version=1, file_id=slot.file_id))
        return attempt.id


def test_usage_reads_real_attempts_and_keeps_missing_usage_unknown(task_env):
    client, factory, _, _ = task_env
    first = submit(task_env, body(task_env), key='usage-one').json()
    second = submit(task_env, body(task_env), key='usage-two').json()
    _real_attempt(factory, first, started_at=datetime(2026, 9, 14, 1, 0, tzinfo=timezone.utc),
                  usage={'input_tokens': 12, 'output_tokens': 7})
    _real_attempt(factory, second, started_at=datetime(2026, 9, 14, 2, 0, tzinfo=timezone.utc),
                  status='partial', usage=None)

    response = client.get('/api/v1/management/usage?from=2026-09-14&to=2026-09-14')

    assert response.status_code == 200, response.text
    report = response.json()
    assert report['scope'] == 'personal'
    assert report['summary']['tasks'] == 2
    assert report['summary']['attempts'] == 2
    assert report['summary']['success'] == 1
    assert report['summary']['partial'] == 1
    assert report['summary']['outputImages'] == 2
    assert report['summary']['inputTokens'] is None
    assert report['summary']['outputTokens'] is None
    assert len(report['rows']) == 1
    assert {item['state'] for item in report['rows'][0]['details']} == {'success', 'partial'}


def test_usage_personal_scope_rejects_other_operator_and_invalid_dates(task_env):
    client, factory, _, identity = task_env
    other = UserRecord(id=uuid4(), name='其他设计师', role='designer', status='active', identity_source='development')
    with factory.begin() as session:
        session.add(other)

    assert client.get(f'/api/v1/management/usage?userId={other.id}').status_code == 403
    assert client.get('/api/v1/management/usage?from=2026-2-1').status_code == 422
    assert client.get('/api/v1/management/usage?from=2026-09-15&to=2026-09-14').status_code == 422


def test_usage_all_scope_can_filter_actual_operator(task_env):
    client, factory, _, identity = task_env
    with factory.begin() as session:
        current = session.get(UserRecord, identity[0])
        current.role = 'super_admin'
        other = UserRecord(id=uuid4(), name='其他设计师', role='designer', status='active', identity_source='development')
        session.add(other)
    receipt = submit(task_env, body(task_env), key='usage-other').json()
    _real_attempt(factory, receipt, started_at=datetime(2026, 9, 15, 1, 0, tzinfo=timezone.utc),
                  operator_id=other.id, usage={'input_tokens': 3, 'output_tokens': 2})

    response = client.get(f'/api/v1/management/usage?userId={other.id}&from=2026-09-15')

    assert response.status_code == 200, response.text
    report = response.json()
    assert report['scope'] == 'all'
    assert report['summary']['attempts'] == 1
    assert report['summary']['inputTokens'] == 3
    assert report['users']
    assert any(item['id'] == str(other.id) for item in report['users'])


def test_usage_distinguishes_running_and_timeout(task_env):
    client, factory, _, _ = task_env
    running = submit(task_env, body(task_env), key='usage-running').json()
    timeout = submit(task_env, body(task_env), key='usage-timeout').json()
    _real_attempt(factory, running, started_at=datetime(2026, 9, 15, 3, 0, tzinfo=timezone.utc),
                  status='running', output=False)
    _real_attempt(factory, timeout, started_at=datetime(2026, 9, 15, 4, 0, tzinfo=timezone.utc),
                  status='failed', output=False, error='timeout')

    report = client.get('/api/v1/management/usage?from=2026-09-15').json()

    assert report['summary']['running'] == 1
    assert report['summary']['timeout'] == 1
    assert report['summary']['failed'] == 0
    states = {detail['state'] for row in report['rows'] for detail in row['details']}
    assert states == {'running', 'timeout'}


def test_usage_exposes_uncertain_execution_as_terminal_observation(task_env):
    client, factory, _, _ = task_env
    receipt = submit(task_env, body(task_env), key='usage-uncertain').json()
    _real_attempt(factory, receipt, started_at=datetime(2026, 9, 15, 5, 0, tzinfo=timezone.utc),
                  status='uncertain', output=False, error='执行状态待核实')

    report = client.get('/api/v1/management/usage?from=2026-09-15').json()

    detail = report['rows'][0]['details'][0]
    assert detail['state'] == 'failed'
    assert detail['finishedAt'] is not None
