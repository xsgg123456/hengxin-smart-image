"""Real HTTP + PostgreSQL timestamptz preserves offset instants on both paths."""
from datetime import datetime, timedelta, timezone
from uuid import UUID
import pytest
from app.db.session import get_session
from app.overseas.execution.models import ExecutionGate, Job
from app.overseas.studio.models import Transcript, Turn
from app.overseas.tasks.models import Task
from test_overseas_auth import overseas, seed, login
from test_overseas_members_postgres import pg_factory
from test_overseas_tasks import create, payload, ROOT
from test_overseas_studio import send


@pytest.mark.parametrize('with_message', [False, True])
def test_http_postgres_offsets_preserve_actual_send_and_reply_instants(overseas, pg_factory, with_message):
    client, _, _ = overseas
    def database():
        with pg_factory() as session:
            yield session
    client.app.dependency_overrides[get_session] = database
    actor = seed(pg_factory, roles=('super_admin',))
    with pg_factory.begin() as session:
        session.add(ExecutionGate(id=1))
    assert login(client).status_code == 200
    response = create(client, payload(actor))
    assert response.status_code == 201, response.text
    task = response.json()
    with pg_factory.begin() as session:
        row = session.get(Task, UUID(task['id']))
        row.status, row.requirements_approved = 'studio', True
    response = send(client, task)
    assert response.status_code == 200, response.text
    turn_id = UUID(response.json()['turns'][0]['id'])
    sent = datetime(2026, 11, 2, 7, 30, 15, tzinfo=timezone(timedelta(hours=8)))
    replied = datetime(2026, 11, 1, 17, 1, 2, tzinfo=timezone(timedelta(hours=-7)))
    with pg_factory.begin() as session:
        turn = session.get(Turn, turn_id)
        turn.created_at, turn.reply = sent, '真实回复'
        job = session.get(Job, turn.job_id)
        job.status, job.completed_at = 'succeeded', replied
        if with_message:
            job.completed_at = replied + timedelta(minutes=1)
            session.add(Transcript(task_id=turn.task_id, turn_id=turn.id, item_id='public',
                kind='message', text=turn.reply, state='completed', created_at=replied))
    response = client.get(f"{ROOT}/tasks/{task['id']}/studio")
    assert response.status_code == 200, response.text
    row = response.json()['turns'][0]
    assert row['actor']['id'] == str(actor)
    assert row['createdAt'] == '2026-11-01T23:30:15+00:00'
    assert row['replyAt'] == '2026-11-02T00:01:02+00:00'
    assert row['replyTimeSource'] == ('message' if with_message else 'completed')
