"""Activity endpoint integration checks against isolated, real business tables."""
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, select

from app.models import Job, utcnow
from app.modules.api_image_edits.models import ApiAttempt, ApiItem, ApiTask
from app.modules.api_image_edits.conversation_models import Conversation, ConversationTurn
from app.modules.management.api_stats.facts import fact, put
from app.modules.management.api_stats.models import ApiUsageFact
from app.resource_models import UserRecord
from files_helpers import files_env
from test_api_image_domain import create, enabled_api

URL = '/api/v1/management/activity'


@pytest.fixture
def env(files_env):
    with files_env[1].begin() as session:
        session.get(UserRecord, files_env[3][0]).role = 'super_admin'
    return files_env


def report(env, **params):
    response = env[0].get(URL, params=params)
    assert response.status_code == 200, response.text
    return response.json()


@pytest.mark.parametrize('role,code', [('super_admin', 200), ('design_manager', 200),
                                    ('operator', 403), ('designer', 403)])
def test_permissions(files_env, role, code):
    with files_env[1].begin() as session:
        session.get(UserRecord, files_env[3][0]).role = role
    assert files_env[0].get(URL).status_code == code


@pytest.mark.parametrize('params', [dict(page=0), dict(pageSize=101), dict(userId='bad'),
    {'from': '2026-2-1'}, {'from': '2026-11-11', 'to': '2026-11-10'},
    dict(generationType='bad'), dict(status='bad'), dict(view='bad'),
    dict(userId=str(uuid4()), unassigned=True), dict(keyword='x' * 201)])
def test_invalid_query(env, params):
    assert env[0].get(URL, params=params).status_code == 422


def test_pending_queue_current_counts_and_read_only(env):
    task_id, _ = create(env[0], count=2)
    with env[1].begin() as session:
        items = session.scalars(select(ApiItem)).all()
        items[1].next_attempt_at = utcnow() + timedelta(minutes=5)
        items[1].error = 'Bearer secret https://private.example/request?api_key=secret'
    engine = env[1].kw['bind']
    statements = []
    def observe(conn, cursor, statement, params, context, many):
        statements.append(statement.strip().split()[0].upper())
    event.listen(engine, 'before_cursor_execute', observe)
    try:
        data = report(env, view='jobs')
    finally:
        event.remove(engine, 'before_cursor_execute', observe)
    assert set(statements) == {'SELECT'}
    assert data['live'] == dict(queued=1, running=1, uncertain=0, failed=0)
    assert data['summary'] == dict(images=0, api=0, cli=0)
    assert data['total'] == 2
    assert all(row['startedAt'] is None and row['current'] for row in data['records'])
    assert 'secret' not in str(data)
    for status in ('queued', 'running', 'uncertain', 'failed'):
        matching = report(env, view='jobs', currentOnly=True, status=status)
        assert matching['total'] == data['live'][status]
    with env[1].begin() as session:
        session.get(ApiTask, UUID(task_id)).deleted_at = utcnow()
    assert report(env, view='jobs', currentOnly=True)['total'] == 0


def test_combinations_dates_pagination_and_unknown_identity(env):
    task_id, _ = create(env[0], count=1)
    actor = env[3][0]
    boundary = datetime(2026, 11, 10, 16, tzinfo=timezone.utc)
    with env[1].begin() as session:
        task = session.get(ApiTask, UUID(task_id))
        session.scalar(select(ApiItem)).state = 'succeeded'
        for index in range(24):
            put(session, fact(task, 'api_request', uuid4(), kind='generation', operator_id=actor,
                occurred_at=boundary + timedelta(seconds=index), state='failed',
                is_retry=index > 0, attribution='verified'))
        put(session, fact(task, 'api_request', uuid4(), operator_id=actor,
            occurred_at=boundary - timedelta(seconds=1), state='failed', kind='generation'))
        put(session, fact(task, 'api_request', uuid4(), operator_id=None,
            occurred_at=boundary, state='uncertain'))
    params = dict(view='jobs', userId=str(actor), generationType='initial', status='failed',
                  keyword='接口换', **{'from': '2026-11-11', 'to': '2026-11-11'})
    first, second = report(env, **params), report(env, page=2, **params)
    assert first['total'] == second['total'] == 24
    assert len(first['records']) == 20 and len(second['records']) == 4
    assert first['summary'] == second['summary'] == dict(images=None, api=24, cli=0)
    assert not {r['id'] for r in first['records']} & {r['id'] for r in second['records']}
    selected = first['records'][0]['id']
    assert report(env, view='jobs', keyword=selected)['total'] == 1
    unknown = report(env, view='jobs', unassigned=True)
    assert unknown['total'] == 1
    assert unknown['records'][0]['personId'] is None
    assert unknown['records'][0]['kind'] is None
    assert report(env, view='jobs', generationType='api_edit')['total'] == 0


def test_output_totals_do_not_count_requests_adoption_or_restore(env):
    task_id, _ = create(env[0], count=1)
    with env[1].begin() as session:
        task = session.get(ApiTask, UUID(task_id))
        session.scalar(select(ApiItem)).state = 'succeeded'
        for category, channel, kind, quantity, state in [
            ('api_request', 'api', 'generation', 1, 'succeeded'),
            ('api_request', 'api', 'generation', 1, 'retryable'),
            ('version_published', 'api', 'generation', 1, 'succeeded'),
            ('version_published', 'api', 'text_edit', 1, 'succeeded'),
            ('cli_round', 'cli', 'image_edit', 1, 'candidate'),
            ('cli_candidate', 'cli', 'image_edit', 1, 'succeeded'),
            ('cli_round', 'cli', 'image_edit', 0, 'unverified'),
            ('adopt', 'cli', 'adopt', 1, 'succeeded'),
            ('restore', 'api', 'restore', 1, 'succeeded')]:
            put(session, fact(task, category, uuid4(), channel=channel, kind=kind,
                quantity=quantity, state=state, operator_id=env[3][0]))
    data = report(env)
    assert data['summary'] == dict(images=3, api=2, cli=1)
    assert data['people'][0]['images'] == 3
    assert report(env, generationType='initial')['summary'] == dict(images=1, api=2, cli=0)
    assert report(env, generationType='cli_edit')['summary'] == dict(images=1, api=0, cli=1)
    assert all(row['images'] is None for row in data['records'] if row['kind'] == 'initial')


def test_latest_cli_current_not_old_failure_and_real_start_only(env):
    task_id, _ = create(env[0], count=1)
    with env[1].begin() as session:
        item = session.scalar(select(ApiItem))
        item.state = 'succeeded'
        conversation = Conversation(item_id=item.id)
        session.add(conversation)
        session.flush()
        for index, status in enumerate(('failed', 'waiting_user')):
            job = Job(idempotency_key=str(uuid4()), payload_hash='x', value='',
                      kind='api_cli_edit', status='succeeded')
            session.add(job)
            session.flush()
            session.add(ConversationTurn(conversation_id=conversation.id, job_id=job.id,
                operator_id=env[3][0], status=status, text='', prompt='', snapshot={},
                base_file_id=item.source_id, created_at=utcnow() + timedelta(seconds=index),
                started_at=utcnow(), process_identity={'pid': 123} if index == 0 else None))
    data = report(env, view='jobs', generationType='cli_edit')
    assert data['live']['failed'] == 0 and data['summary']['cli'] == 1
    assert report(env, view='jobs', currentOnly=True, status='failed')['total'] == 0
    assert report(env, view='jobs', status='failed')['total'] == 1
    assert sum(row['current'] for row in data['records']) == 1


def test_retained_deleted_facts_and_absent_history_not_fabricated(env):
    actor = env[3][0]
    missing_id = uuid4()
    with env[1].begin() as session:
        session.add(ApiUsageFact(key=f'api_request:{uuid4()}', category='api_request',
            channel='api', kind='legacy_unknown', task_id=missing_id, task_name='已删除历史',
            owner_id=actor, operator_id=None, occurred_at=utcnow(), state='succeeded',
            quantity=1, is_retry=None, attribution='historical_unverified'))
    data = report(env, view='jobs')
    assert data['total'] == 1 and data['summary'] == dict(images=0, api=1, cli=0)
    row = data['records'][0]
    assert row['taskDeleted'] and not row['current']
    assert row['personId'] is row['kind'] is row['images'] is row['retry'] is None
    assert report(env, currentOnly=True, view='jobs')['total'] == 0


def test_current_api_attempt_is_not_duplicated_or_reused_across_retry_cycle(env):
    create(env[0], count=1)
    with env[1].begin() as session:
        item = session.scalar(select(ApiItem))
        item.state = 'collecting'
        attempt = ApiAttempt(item_id=item.id, operator_id=env[3][0], state='succeeded',
            retry_cycle_id=item.retry_cycle_id, completed_at=utcnow(), error='token=private')
        session.add(attempt)
    data = report(env, view='jobs', currentOnly=True, status='running')
    assert data['total'] == data['live']['running'] == 1
    assert data['summary'] == dict(images=None, api=1, cli=0)
    row = data['records'][0]
    assert row['status'] == 'collecting' and row['finishedAt'] is None and row['seconds'] is None
    assert 'private' not in str(data)
    with env[1].begin() as session:
        item = session.scalar(select(ApiItem))
        item.retry_cycle_id = uuid4()
        item.state = 'failed'
    data = report(env, view='jobs', currentOnly=True, status='failed')
    assert data['total'] == data['live']['failed'] == 1
    assert data['records'][0]['id'].startswith('api_queue:')
    assert data['records'][0]['startedAt'] is None
    assert data['summary']['api'] == 0


def test_real_execution_uses_output_evidence_and_retry_request_counts(env):
    from app.modules.api_image_edits.execution import execute_next
    from app.modules.api_image_edits.relay import RelayError
    from test_api_image_execution import Client, due
    create(env[0], count=1)
    relay = Client([RelayError('retryable', 'HTTP_429', 'safe')])
    assert execute_next(env[1], env[2], relay)
    assert report(env)['summary']['api'] == 1
    running = report(env, view='jobs', currentOnly=True, status='running')
    assert running['total'] == 1 and running['records'][0]['status'] == 'retry_wait'
    due(env[1])
    assert execute_next(env[1], env[2], Client())
    data = report(env, view='jobs')
    assert data['summary'] == dict(images=1, api=2, cli=0)
    assert data['total'] == 2
    assert sum(row['retry'] is True for row in data['records']) == 1
    assert data['live'] == dict(queued=0, running=0, uncertain=0, failed=0)
    assert all(row['images'] is None for row in data['records'])


def test_cli_submission_and_start_across_beijing_midnight(env):
    task_id, _ = create(env[0], count=1)
    submitted = datetime(2026, 11, 10, 15, 59, tzinfo=timezone.utc)
    started = submitted + timedelta(minutes=2)
    turn_id = uuid4()
    with env[1].begin() as session:
        task = session.get(ApiTask, UUID(task_id))
        session.scalar(select(ApiItem)).state = 'succeeded'
        put(session, fact(task, 'cli_submission', turn_id, channel='cli', kind='image_edit',
            operator_id=env[3][0], occurred_at=submitted, state='submitted'))
        put(session, fact(task, 'cli_round', turn_id, channel='cli', kind='image_edit',
            operator_id=env[3][0], occurred_at=started, state='running'))
    previous = report(env, view='jobs', generationType='cli_edit', **{'from':'2026-11-10','to':'2026-11-10'})
    current = report(env, view='jobs', generationType='cli_edit', **{'from':'2026-11-11','to':'2026-11-11'})
    assert previous['total'] == previous['summary']['cli'] == 0
    assert current['total'] == current['summary']['cli'] == 1
    row = current['records'][0]
    assert datetime.fromisoformat(row['createdAt']) == submitted
    assert datetime.fromisoformat(row['startedAt']) == started
