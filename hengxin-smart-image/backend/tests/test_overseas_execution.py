"""Durable lifecycle and public execution contracts using isolated storage."""
from datetime import timedelta
from uuid import UUID, uuid4
import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from app.db.timestamps import utcnow
from app.overseas.execution import claims, queue
from app.overseas.execution.models import ExecutionGate, ExecutionEvent, Job, JobOutbox
from app.overseas.tasks.models import Task
from test_overseas_auth import overseas, HEADERS
from test_overseas_tasks import setup, create, payload, add_member


def prepared(overseas, roles=('super_admin',)):
    client, factory, actor, designer = setup(overseas, roles)
    task = UUID(create(client, payload(designer)).json()['id'])
    with factory.begin() as session:
        if session.get(ExecutionGate, 1) is None:
            session.add(ExecutionGate(id=1))
    return client, factory, task


def enqueue(factory, task, key='job', kind='analysis'):
    with factory.begin() as session:
        return queue.enqueue(session, task, kind, key, {'input': {'text': 'safe'}}).id


def test_enqueue_frozen_idempotent_atomic(overseas):
    _, factory, task = prepared(overseas)
    body = {'input': ['original']}
    with factory.begin() as session:
        job = queue.enqueue(session, task, 'analysis', 'same', body)
        body['input'].append('changed')
        assert job.payload == {'input': ['original']}
        assert queue.enqueue(session, task, 'analysis', 'same', {'input': ['original']}).id == job.id
    with pytest.raises(HTTPException):
        with factory.begin() as session:
            queue.enqueue(session, task, 'generation', 'same', {})
    with pytest.raises(RuntimeError):
        with factory.begin() as session:
            queue.enqueue(session, task, 'revision', 'rollback', {})
            raise RuntimeError('rollback')
    with factory() as session:
        assert [session.scalar(select(func.count()).select_from(model))
                for model in (Job, JobOutbox, ExecutionEvent)] == [1, 1, 1]


def test_shared_five_slots_uncertain_never_retried(overseas):
    _, factory, task = prepared(overseas)
    ids = [enqueue(factory, task, str(i), ('analysis', 'reanalysis', 'generation', 'revision')[i % 4])
           for i in range(6)]
    tokens = [claims.claim(factory, identity) for identity in ids]
    assert sum(token is not None for token in tokens) == 5
    assert claims.claim(factory, ids[0]) is None
    with factory.begin() as session:
        session.get(Job, ids[0]).lease_until = utcnow() - timedelta(seconds=1)
    assert claims.sweep_expired(factory) == 1
    assert claims.claim(factory, ids[0]) is None
    assert claims.claim(factory, ids[-1]) is None
    assert not claims.finish(factory, ids[0], tokens[0], 'failed')
    with factory.begin() as session:
        session.get(Job, ids[0]).process_exited = True
    assert not claims.finish(factory, ids[0], tokens[0], 'succeeded', result={'late': True})
    assert claims.finish(factory, ids[0], tokens[0], 'failed', error='secret stderr')
    assert claims.claim(factory, ids[-1])
    with factory() as session:
        assert session.get(Job, ids[0]).error != 'secret stderr'
        assert session.get(Job, ids[0]).execution_count == 1


def test_finish_requires_exit_token_lease_and_cancel_wins(overseas):
    client, factory, task = prepared(overseas)
    identity = enqueue(factory, task)
    token = claims.claim(factory, identity)
    assert not claims.finish(factory, identity, token, 'succeeded', {})
    with factory.begin() as session:
        session.get(Job, identity).process_exited = True
    assert not claims.finish(factory, identity, uuid4(), 'succeeded', {})
    response = client.post(f'/api/overseas/v1/jobs/{identity}/cancel', json={'version': 2}, headers=HEADERS)
    assert response.status_code == 200 and response.json()['status'] == 'cancelling'
    assert not claims.finish(factory, identity, token, 'succeeded', {'late': True})
    assert claims.finish(factory, identity, token, 'cancelled')
    with factory() as session:
        assert session.get(JobOutbox, identity).completed_at is not None
        assert session.get(Job, identity).result is None


def test_dispatch_failure_rollback_and_repeat_delivery(overseas):
    _, factory, task = prepared(overseas)
    identity = enqueue(factory, task)
    sent = []
    def fails(job_id):
        sent.append(job_id)
        raise RuntimeError('broker unavailable')
    with pytest.raises(RuntimeError):
        queue.dispatch_once(factory, fails)
    assert queue.dispatch_once(factory, sent.append) == 1
    with factory.begin() as session:
        row = session.get(JobOutbox, identity)
        assert row.dispatch_count == 1 and row.completed_at is None
        row.next_dispatch_at = utcnow() - timedelta(seconds=1)
    assert queue.dispatch_once(factory, sent.append) == 1
    assert sent == [identity] * 3
    assert claims.claim(factory, identity)
    assert queue.dispatch_once(factory, sent.append) == 0


def test_queries_resume_sanitization_revocation_and_cancel_conflict(overseas):
    client, factory, task = prepared(overseas)
    with factory.begin() as session:
        from app.overseas.auth.models import Member
        session.get(Task, task).designer_id = session.scalar(select(Member.id).where(Member.provider_user_id == 'member-1'))
    from test_overseas_assignment import change_roles
    with factory() as session:
        actor = session.get(Task, task).designer_id
    change_roles(factory, actor, ('designer',))
    identity = enqueue(factory, task)
    base = f'/api/overseas/v1/tasks/{task}'
    first = client.get(base + '/execution-events').json()
    assert len(first['items']) == 1
    assert client.get(base + '/execution-events?after=' + str(first['cursor'])).json()['items'] == []
    job = client.get(base + '/jobs').json()['items'][0]
    assert set(job) == {'id', 'taskId', 'kind', 'status', 'version', 'error', 'createdAt', 'startedAt', 'completedAt'}
    claims.claim(factory, identity)
    assert client.post(f'/api/overseas/v1/jobs/{identity}/cancel', json={'version': 1}, headers=HEADERS).status_code == 409
    assert len(client.get(base + '/execution-events?after=' + str(first['cursor'])).json()['items']) == 1
    other = add_member(factory)
    with factory.begin() as session:
        session.get(Task, task).designer_id = other
        session.get(Task, task).created_by = other
    assert client.get(base + '/jobs').status_code == 403
    assert client.get(base + '/execution-events?after=0').status_code == 403
    assert client.post(f'/api/overseas/v1/jobs/{identity}/cancel', json={'version': 2}, headers=HEADERS).status_code == 403


def test_paused_gate_and_queued_cancel(overseas):
    client, factory, task = prepared(overseas)
    identity = enqueue(factory, task)
    with factory.begin() as session:
        session.get(ExecutionGate, 1).paused = True
    assert claims.claim(factory, identity) is None
    result = client.post(f'/api/overseas/v1/jobs/{identity}/cancel', json={'version': 1}, headers=HEADERS)
    assert result.status_code == 200 and result.json()['status'] == 'cancelled'
    assert claims.claim(factory, identity) is None


def test_success_and_renew(overseas):
    _, factory, task = prepared(overseas)
    identity = enqueue(factory, task)
    token = claims.claim(factory, identity)
    assert claims.renew(factory, identity, token)
    assert not claims.renew(factory, identity, uuid4())
    with factory.begin() as session:
        session.get(Job, identity).process_exited = True
    assert claims.finish(factory, identity, token, 'succeeded', {'verified': True})
    assert not claims.finish(factory, identity, token, 'succeeded', {'overwrite': True})
    with factory() as session:
        assert session.get(Job, identity).result == {'verified': True}
