"""Concurrent duplicate and send/reset contention uses actual PostgreSQL locks."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from fastapi import HTTPException
from sqlalchemy import select, func
from app.overseas.auth.models import Member
from app.overseas.studio import service
from app.overseas.studio.models import Conversation, Turn
from app.overseas.studio.schemas import NewConversation, Send
from test_overseas_deletion_postgres import ready
from test_overseas_members_postgres import pg_factory
from test_overseas_tasks import overseas


def test_simultaneous_new_conversation_with_same_key_creates_one(ready):
    factory, _, (actor, task, _) = ready
    barrier = Barrier(2)
    def reset():
        with factory() as session:
            person = session.get(Member, actor)
            barrier.wait(timeout=5)
            return service.new_conversation(session, person, task, NewConversation(), 'same')['conversationId']
    with ThreadPoolExecutor(2) as pool:
        jobs = [pool.submit(reset) for _ in range(2)]
        results = [j.result(timeout=15) for j in jobs]
    assert results[0] == results[1]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Conversation)) == 2


def test_send_and_create_preserve_explicit_context_under_contention(ready):
    factory, _, (actor, task, _) = ready
    with factory() as session:
        original = service.queries.current_conversation(session, task).id
    barrier = Barrier(2)
    def mutate(reset):
        with factory() as session:
            person = session.get(Member, actor)
            barrier.wait(timeout=5)
            try:
                method = service.new_conversation if reset else service.send
                return method(session, person, task, NewConversation() if reset else Send(text='hello', conversationId=original), 'key')
            except HTTPException as exc:
                assert exc.status_code == 409
                return None
    with ThreadPoolExecutor(2) as pool:
        jobs = [pool.submit(mutate, reset) for reset in (False, True)]
        sent, reset = [j.result(timeout=15) for j in jobs]
    assert sent and sent['activeTurnId'] and reset
    with factory() as session:
        latest = service.queries.current_conversation(session, task)
        current = session.scalar(select(Turn).where(Turn.text == 'hello'))
        assert current.conversation_id == original and latest.id != original


def test_concurrent_create_enforces_ten_without_dropping_history(ready):
    factory, _, (actor, task, _) = ready
    with factory.begin() as session:
        session.add_all([Conversation(task_id=task) for _ in range(8)])
    barrier = Barrier(4)
    def create(index):
        with factory() as session:
            person = session.get(Member, actor)
            barrier.wait(timeout=8)
            try:
                service.new_conversation(session, person, task, NewConversation(name=f'并发{index}'), str(index))
                return 200
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(4) as pool:
        assert sorted(pool.map(create, range(4))) == [200, 409, 409, 409]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Conversation)) == 10


def test_distinct_sessions_claim_parallel_same_session_send_serialized(ready):
    from app.overseas.execution import claims
    from app.overseas.execution.models import Job
    factory, _, (actor, task, _) = ready
    with factory() as session:
        first = service.queries.current_conversation(session, task).id
        second = service.new_conversation(session, session.get(Member, actor), task, NewConversation(), 'second')['conversationId']
    from uuid import UUID
    barrier = Barrier(3)
    def send(index, channel):
        with factory() as session:
            person = session.get(Member, actor)
            barrier.wait(timeout=8)
            try:
                result = service.send(session, person, task, Send(text='并行', conversationId=channel), str(index))
                return result['turns'][-1]['jobId']
            except HTTPException as exc:
                assert exc.status_code == 409
                return None
    with ThreadPoolExecutor(3) as pool:
        pending = [pool.submit(send, i, channel) for i, channel in enumerate((first, first, UUID(second)))]
        jobs = [job.result(timeout=15) for job in pending]
    assert sum(job is not None for job in jobs) == 2
    with ThreadPoolExecutor(2) as pool:
        assert all(pool.map(lambda job: claims.claim(factory, job), filter(None, jobs)))
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Job).where(Job.status == 'running')) == 2
