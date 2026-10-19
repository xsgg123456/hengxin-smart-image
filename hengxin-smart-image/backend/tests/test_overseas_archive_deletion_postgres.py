"""Real PostgreSQL task/archive lock serialization, never production databases."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from fastapi import HTTPException
from sqlalchemy import select
from app.overseas.archives import deletion, cleanup
from app.overseas.archives.models import Archive, ArchiveDeletion
from app.overseas.auth.models import Member
from app.overseas.tasks import cleanup as task_cleanup
from app.overseas.tasks.models import Task
from app.overseas.studio import service
from app.overseas.studio.schemas import ArchiveRequest
from test_overseas_deletion_postgres import ready, save, remove as remove_task
from test_overseas_members_postgres import pg_factory
from test_overseas_tasks import overseas


def snapshot(ready):
    factory, _, _ = ready
    with factory() as session:
        record = session.scalar(select(Archive))
        return record.id, deletion.token(session, record)


def remove(ready, identity, token):
    factory, _, (actor, _, _) = ready
    with factory() as session:
        try:
            return deletion.request(session, session.get(Member, actor), identity,
                deletion.DeleteArchive(deleteToken=token))['status']
        except HTTPException as exc:
            return exc.status_code


def append(ready):
    factory, store, (actor, task, picture) = ready
    with factory() as session:
        try:
            service.archive(session, session.get(Member, actor), task,
                ArchiveRequest(pictureIds=[picture], sku='A'), 'append-key', store)
            return 200
        except HTTPException as exc:
            return exc.status_code


def test_delete_fences_concurrent_confirmation(ready, monkeypatch):
    assert save(ready) == 200
    identity, token = snapshot(ready)
    entered, release = Event(), Event()
    original = deletion.locked
    def held(*args):
        value = original(*args)
        entered.set()
        assert release.wait(8)
        return value
    monkeypatch.setattr(deletion, 'locked', held)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(remove, ready, identity, token)
        assert entered.wait(8)
        second = pool.submit(append, ready)
        release.set()
        assert first.result(15) == 'deleting'
        assert second.result(15) == 409
    assert cleanup.cleanup_once(ready[0], ready[1]) == 1


def test_confirmation_wins_and_old_snapshot_conflicts(ready, monkeypatch):
    from app.overseas.archives import audit
    assert save(ready) == 200
    identity, token = snapshot(ready)
    entered, release = Event(), Event()
    original = audit.record_confirmation
    def held(*args):
        value = original(*args)
        entered.set()
        assert release.wait(8)
        return value
    monkeypatch.setattr(audit, 'record_confirmation', held)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(append, ready)
        assert entered.wait(8)
        second = pool.submit(remove, ready, identity, token)
        release.set()
        assert first.result(15) == 200
        assert second.result(15) == 409


def test_task_cleanup_waits_then_both_workers_finish(ready, monkeypatch):
    factory, store, (_, task, _) = ready
    assert save(ready) == 200
    identity, token = snapshot(ready)
    assert remove(ready, identity, token) == 'deleting'
    # Save increments task version only for legacy flow, so ready's task stays version 1.
    assert remove_task(ready)['status'] == 'deleting'
    assert task_cleanup.cleanup_once(factory, store) == 0
    entered, release = Event(), Event()
    original = store.remove
    def held(*args):
        entered.set()
        assert release.wait(8)
        return original(*args)
    monkeypatch.setattr(store, 'remove', held)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(cleanup.cleanup_once, factory, store)
        assert entered.wait(8)
        second = pool.submit(task_cleanup.cleanup_once, factory, store)
        release.set()
        assert first.result(15) == 1
        assert second.result(15) == 1
    with factory() as session:
        assert session.get(Task, task) is None
        assert session.get(Archive, identity) is None
        assert session.get(ArchiveDeletion, identity).status == 'deleted'


def test_task_detach_races_archive_request_without_deadlock(ready, monkeypatch):
    factory, store, (_, task, _) = ready
    assert save(ready) == 200
    identity, _ = snapshot(ready)
    assert remove_task(ready)['status'] == 'deleting'
    entered, release = Event(), Event()
    original = task_cleanup.cleanup_records.erase
    def held(*args):
        value = original(*args)
        entered.set()
        assert release.wait(8)
        return value
    monkeypatch.setattr(task_cleanup.cleanup_records, 'erase', held)
    _, token = snapshot(ready)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(task_cleanup.cleanup_once, factory, store)
        assert entered.wait(8)
        second = pool.submit(remove, ready, identity, token)
        release.set()
        assert first.result(15) == 1
        assert second.result(15) == 409  # Source metadata changed; refresh confirmation.
    identity, token = snapshot(ready)
    assert remove(ready, identity, token) == 'deleting'
    assert cleanup.cleanup_once(factory, store) == 1


def test_archive_request_between_task_cleanup_transactions_waits(ready, monkeypatch):
    factory, store, (_, task, _) = ready
    assert save(ready) == 200
    identity, token = snapshot(ready)
    assert remove_task(ready)['status'] == 'deleting'
    entered, release = Event(), Event()
    original = task_cleanup.locked
    calls = []
    def held(*args):
        calls.append(True)
        if len(calls) == 2:
            # Before phase two takes its task lock: phase one has committed.
            entered.set()
            assert release.wait(8)
        return original(*args)
    monkeypatch.setattr(task_cleanup, 'locked', held)
    with ThreadPoolExecutor(1) as pool:
        worker = pool.submit(task_cleanup.cleanup_once, factory, store)
        assert entered.wait(8)
        assert remove(ready, identity, token) == 'deleting'
        release.set()
        assert worker.result(15) == 0
    with factory() as session:
        assert session.get(Task, task) is not None
        assert session.get(Archive, identity).task_id == task
    assert cleanup.cleanup_once(factory, store) == 1
    assert task_cleanup.cleanup_once(factory, store) == 1
