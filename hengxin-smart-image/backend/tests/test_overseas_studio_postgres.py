"""Concurrent duplicate and send/reset contention uses actual PostgreSQL locks."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from fastapi import HTTPException
from sqlalchemy import select, func
from app.overseas.auth.models import Member
from app.overseas.studio import service
from app.overseas.studio.models import Conversation, Turn
from app.overseas.studio.schemas import Complete, Send
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
            return service.new_conversation(session, person, task, Complete(), 'same')['conversationId']
    with ThreadPoolExecutor(2) as pool:
        jobs = [pool.submit(reset) for _ in range(2)]
        results = [j.result(timeout=15) for j in jobs]
    assert results[0] == results[1]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(Conversation)) == 2


def test_send_and_reset_serialize_without_active_context_replacement(ready):
    factory, _, (actor, task, _) = ready
    barrier = Barrier(2)
    def mutate(reset):
        with factory() as session:
            person = session.get(Member, actor)
            barrier.wait(timeout=5)
            try:
                method = service.new_conversation if reset else service.send
                return method(session, person, task, Complete() if reset else Send(text='hello'), 'key')
            except HTTPException as exc:
                assert exc.status_code == 409
                return None
    with ThreadPoolExecutor(2) as pool:
        jobs = [pool.submit(mutate, reset) for reset in (False, True)]
        sent, reset = [j.result(timeout=15) for j in jobs]
    assert sent and sent['activeTurnId']
    with factory() as session:
        latest = service.queries.current_conversation(session, task)
        current = session.scalar(select(Turn).where(Turn.text == 'hello'))
        assert current.conversation_id == latest.id
