"""Lifecycle races use PostgreSQL row locks and an isolated temporary schema."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from app.overseas.auth.models import Member
from app.overseas.archives.models import Archive, ArchiveDeletion
from app.overseas.archives import deletion
from app.overseas.tasks.models import Task, TaskEvent
from app.overseas.studio import service
from app.overseas.studio.schemas import Complete, Send
from test_overseas_deletion_postgres import ready, save
from test_overseas_members_postgres import pg_factory
from test_overseas_tasks import overseas


def mutate(ready, operation, version, key, barrier=None):
    factory, _, (actor, task, _) = ready
    with factory() as session:
        person = session.get(Member, actor)
        if barrier:
            barrier.wait(timeout=8)
        try:
            return getattr(service, operation)(session, person, task, Complete(version=version), key)
        except HTTPException as exc:
            return exc.status_code


@pytest.mark.parametrize('operation', ['complete', 'reopen'])
@pytest.mark.parametrize('same_key', [True, False])
def test_duplicate_lifecycle_request_serializes_once(ready, operation, same_key):
    factory, _, (_, task, _) = ready
    assert save(ready) == 200
    version = 1
    if operation == 'reopen':
        assert mutate(ready, 'complete', 1, 'initial')['completed']
        version = 2
    barrier = Barrier(2)
    with ThreadPoolExecutor(2) as pool:
        futures = [pool.submit(mutate, ready, operation, version, 'same' if same_key else str(i), barrier)
                   for i in range(2)]
        results = [future.result(timeout=20) for future in futures]
    if same_key:
        assert results[0] == results[1]
    else:
        assert sum(result == 409 for result in results) == 1
    with factory() as session:
        row = session.get(Task, task)
        assert row.version == version + 1
        kind = 'task.studio_completed' if operation == 'complete' else 'task.studio_reopened'
        assert session.scalar(select(func.count()).select_from(TaskEvent).where(TaskEvent.kind == kind)) == 1


def test_complete_and_send_cannot_leave_active_job_on_completed_task(ready):
    factory, _, (actor, task, _) = ready
    assert save(ready) == 200
    barrier = Barrier(2)
    def send():
        with factory() as session:
            person = session.get(Member, actor)
            barrier.wait(timeout=8)
            try:
                return service.send(session, person, task, Send(text='续聊'), 'send')
            except HTTPException as exc:
                return exc.status_code
    with ThreadPoolExecutor(2) as pool:
        completed = pool.submit(mutate, ready, 'complete', 1, 'complete', barrier)
        sent = pool.submit(send)
        results = [completed.result(timeout=20), sent.result(timeout=20)]
    assert sum(result == 409 for result in results) == 1
    result = next(result for result in results if isinstance(result, dict))
    assert not (result['completed'] and result['activeTurnId'])


def test_complete_and_archive_deletion_follow_same_task_lock(ready):
    factory, _, (actor, task, _) = ready
    assert save(ready) == 200
    with factory() as session:
        record = session.scalar(select(Archive))
        archive_id, token = record.id, deletion.token(session, record)
    barrier = Barrier(2)
    def remove():
        with factory() as session:
            person = session.get(Member, actor)
            barrier.wait(timeout=8)
            return deletion.request(session, person, archive_id, deletion.DeleteArchive(deleteToken=token))
    with ThreadPoolExecutor(2) as pool:
        completed = pool.submit(mutate, ready, 'complete', 1, 'complete', barrier)
        removed = pool.submit(remove)
        result, receipt = completed.result(timeout=20), removed.result(timeout=20)
    assert receipt['status'] == 'deleting'
    with factory() as session:
        row = session.get(Task, task)
        assert session.get(ArchiveDeletion, archive_id).status == 'deleting'
        assert row.status == ('studio' if result == 409 else 'completed')
        assert service.queries.view(session, session.get(Member, actor), task)['archiveId'] is None
