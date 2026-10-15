"""Read-only activity summaries exercise real SQL against isolated fixture data."""
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, select

from app.models import Job, utcnow
from app.modules.api_image_edits.activity import activities
from app.modules.api_image_edits.conversation_models import Conversation, ConversationTurn
from app.modules.api_image_edits.models import ApiFile, ApiItem
from files_helpers import files_env
from test_api_image_domain import ROOT, enabled_api
from test_api_image_versions import setup_result


def seed_turn(factory, item_id, state, job_state, finished=True):
    with factory.begin() as session:
        item = session.get(ApiItem, UUID(item_id))
        conversation = session.scalar(select(Conversation).where(Conversation.item_id == item.id))
        if not conversation:
            conversation = Conversation(item_id=item.id)
            session.add(conversation)
            session.flush()
        job = Job(idempotency_key=str(uuid4()), payload_hash='test', value='PRIVATE_JOB',
                  kind='api_cli_edit', status=job_state, completed_at=utcnow() if finished else None)
        session.add(job)
        session.flush()
        turn = ConversationTurn(conversation_id=conversation.id, job_id=job.id,
            operator_id=session.get(ApiFile, item.source_id).owner_id,
            status=state, text='PRIVATE_TEXT', prompt='PRIVATE_PROMPT' * 1000,
            snapshot={}, base_version=1, base_file_id=item.result_id, messages=['PRIVATE_MESSAGES'] * 1000,
            finished_at=utcnow() if finished else None)
        session.add(turn)
        session.flush()
        return turn.id, job.id


@pytest.mark.parametrize('state,job_state,finished,expected', [
    ('queued', 'queued', False, 'queued'), ('running', 'running', False, 'running'),
    ('running', 'cancelling', False, 'running'), ('uncertain', 'uncertain', True, 'uncertain'),
    ('candidate', 'succeeded', True, 'idle'), ('waiting_user', 'succeeded', True, 'idle'),
    ('adopted', 'succeeded', True, 'idle'), ('failed', 'failed', True, 'idle'),
    ('cancelled', 'cancelled', True, 'idle'), ('candidate', 'running', True, 'uncertain'),
    ('candidate', 'succeeded', False, 'uncertain'), ('future_state', 'succeeded', True, 'uncertain'),
])
def test_activity_keeps_api_result_and_requires_confirmed_end(files_env, state, job_state, finished, expected):
    client, factory, _, _ = files_env
    task_id, item, _ = setup_result(client, factory)
    seed_turn(factory, item['id'], state, job_state, finished)
    detail = client.get(f'{ROOT}/tasks/{task_id}').json()
    summary = client.get(ROOT + '/tasks?view=summary').json()['items'][0]
    assert detail['cliActivity'] == summary['cliActivity'] == expected
    assert detail['items'][0]['cliActivity'] == expected
    assert detail['status'] == detail['items'][0]['state'] == 'succeeded'
    assert detail['items'][0]['result'] == item['result']
    assert len(detail['items'][0]['versions']) == 1
    if expected != 'idle':
        assert summary['canDelete'] is False


def test_activity_aggregates_all_active_items_and_uses_one_narrow_query(files_env):
    client, factory, _, _ = files_env
    first, item, _ = setup_result(client, factory, count=3)
    second, other, _ = setup_result(client, factory)
    seed_turn(factory, item['id'], 'queued', 'queued', False)
    with factory() as session:
        items = session.scalars(select(ApiItem).where(ApiItem.task_id == UUID(first)).order_by(ApiItem.position)).all()
    seed_turn(factory, str(items[1].id), 'running', 'running', False)
    seed_turn(factory, str(items[2].id), 'candidate', 'succeeded', True)
    statements = []
    engine = factory.kw['bind']
    def capture(conn, cursor, statement, *args):
        statements.append(statement)
    event.listen(engine, 'before_cursor_execute', capture)
    try:
        with factory() as session:
            tasks, images = activities(session, [UUID(first), UUID(second)])
    finally:
        event.remove(engine, 'before_cursor_execute', capture)
    assert len(statements) == 1
    assert all(word not in statements[0] for word in ('prompt', 'messages', 'snapshot', 'job_records.value'))
    assert tasks[UUID(first)] == 'running'
    assert tasks.get(UUID(second), 'idle') == 'idle'
    assert images[UUID(item['id'])] == 'queued'
    assert images[items[1].id] == 'running'


def test_terminal_turn_with_execution_lease_is_not_idle(files_env):
    client, factory, _, _ = files_env
    task_id, item, _ = setup_result(client, factory)
    _, job_id = seed_turn(factory, item['id'], 'candidate', 'succeeded')
    with factory.begin() as session:
        session.get(Job, job_id).lease_until = utcnow()
    detail = client.get(f'{ROOT}/tasks/{task_id}').json()
    assert detail['cliActivity'] == 'uncertain'
    assert detail['canDelete'] is False
