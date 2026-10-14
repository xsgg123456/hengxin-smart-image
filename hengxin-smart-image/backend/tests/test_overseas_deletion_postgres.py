"""Actual PostgreSQL lock ordering, independent archives and concurrent erasure."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from uuid import UUID
import pytest
from fastapi import HTTPException
from sqlalchemy import select, func
from app.core.config import get_settings
from app.overseas.auth.models import Member
from app.overseas.tasks.models import Task, TaskSku, TaskDeletion
from app.overseas.tasks.schemas import DeleteTask
from app.overseas.tasks import deletion, cleanup
from app.overseas.execution.models import Job, ExecutionGate
from app.overseas.studio.models import Conversation, Turn, Picture
from app.overseas.studio.service import archive
from app.overseas.studio.schemas import ArchiveRequest
from app.overseas.archives.models import Archive, ArchiveAsset
from test_overseas_members_postgres import pg_factory, member
from test_overseas_tasks import overseas
from test_overseas_studio import output
from test_overseas_materials import MemoryStore


@pytest.fixture
def ready(pg_factory, overseas, tmp_path):
    factory, store = pg_factory, MemoryStore()
    get_settings().codex_execution_root = str(tmp_path / 'private-execution')
    actor = member(factory)
    with factory.begin() as session:
        session.add(ExecutionGate(id=1))
        task = Task(name='待删除任务', product_name='产品', brand='品牌', platform='Amazon',
            market='US', created_by=actor, designer_id=actor, status='studio', workflow='studio',
            requirements_approved=True)
        session.add(task)
        session.flush()
        session.add(TaskSku(task_id=task.id, code='A', code_key='a', position=0))
        channel = Conversation(task_id=task.id)
        job = Job(task_id=task.id, kind='studio', dedupe_key='output', payload={}, status='succeeded',
            process_exited=True, execution_count=1)
        session.add_all([channel, job])
        session.flush()
        turn = Turn(task_id=task.id, conversation_id=channel.id, job_id=job.id, actor_id=actor, text='input')
        session.add(turn)
        session.flush()
        data = output(store)
        old = data['object_key']
        data['object_key'] = 'studio/pictures/' + data['id']
        store.data[data['object_key']] = store.data.pop(old)
        picture = Picture(**{**data, 'id': UUID(data['id'])}, task_id=task.id, turn_id=turn.id)
        session.add(picture)
        session.flush()
        identities = actor, task.id, picture.id
    return factory, store, identities


def remove(ready):
    factory, _, (actor, task, _) = ready
    with factory() as session:
        return deletion.request(session, session.get(Member, actor), task,
            DeleteTask(version=1))


def save(ready):
    factory, store, (actor, task, picture) = ready
    with factory() as session:
        try:
            archive(session, session.get(Member, actor), task,
                ArchiveRequest(pictureIds=[picture], sku='A'), 'archive', store)
            return 200
        except HTTPException as exc:
            return exc.status_code


@pytest.mark.parametrize('archive_first', [False, True])
def test_archive_delete_contention_has_deterministic_order(ready, monkeypatch, archive_first):
    factory, store, (_, task, _) = ready
    entered, release = Event(), Event()
    target = store if archive_first else deletion
    name = 'put' if archive_first else 'stopping'
    original = getattr(target, name)
    def held(*args, **kwargs):
        entered.set()
        assert release.wait(timeout=8)
        return original(*args, **kwargs)
    monkeypatch.setattr(target, name, held)
    with ThreadPoolExecutor(2) as pool:
        first = pool.submit(save if archive_first else remove, ready)
        assert entered.wait(timeout=8)
        second = pool.submit(remove if archive_first else save, ready)
        release.set()
        a, b = first.result(timeout=15), second.result(timeout=15)
    assert (a if archive_first else b) == (200 if archive_first else 409)
    assert cleanup.cleanup_once(factory, store) == 1
    with factory() as session:
        assert session.get(Task, task) is None
        records = session.scalars(select(Archive)).all()
        assert len(records) == int(archive_first)
        if records:
            assert records[0].task_id is None
            row = session.scalar(select(ArchiveAsset))
            assert store.stat(row) == row.size_bytes


def test_two_requests_and_two_maintenance_workers_erase_once(ready):
    factory, store, (_, task, _) = ready
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: remove(ready), range(2)))
    assert all(row['status'] == 'deleting' for row in results)
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(lambda _: cleanup.cleanup_once(factory, store), range(2)))
    assert sum(results) == 1
    with factory() as session:
        assert session.get(Task, task) is None
        assert session.scalar(select(func.count()).select_from(TaskDeletion)) == 1
        assert session.get(TaskDeletion, task).manifest == {}
