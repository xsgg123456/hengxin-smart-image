from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import func, select

from app.contracts.business import RevisionInput
from app.models import Job, Outbox
from app.modules.archives.models import ArchiveRecord
from app.modules.archives.service import create_archive
from app.modules.tasks.models import ImageVersion, ResultSlotRecord, RoundRecord, TaskSource
from app.modules.tasks.service import create_task, accept_round
from app.modules.tasks.cancellations import delete_task
from test_tasks_concurrency import pg_tasks, compete


def prepared(env):
    factory, user, _, body = env
    with factory() as session:
        receipt = create_task(session, user, body, 'archive-initial')
    with factory.begin() as session:
        current = session.get(RoundRecord, UUID(receipt.roundId))
        current.status = session.get(Job, current.job_id).status = 'succeeded'
        slot = session.scalar(select(ResultSlotRecord).where(ResultSlotRecord.task_id == UUID(receipt.taskId)))
        source = session.scalar(select(TaskSource).where(TaskSource.task_id == UUID(receipt.taskId)))
        version = ImageVersion(slot_id=slot.id, round_id=current.id, version=1, file_id=source.file_id)
        session.add(version)
        session.flush()
        slot.current_version_id = version.id
    return UUID(receipt.taskId)


def test_cross_user_concurrent_archives_are_one_snapshot_without_cli(pg_tasks):
    factory, user, other, _ = pg_tasks
    task_id = prepared(pg_tasks)
    def call(i):
        with factory() as session:
            return create_archive(session, [user, other][i], task_id, None, 'same-action')
    results = compete(call)
    assert results[0] == results[1]
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ArchiveRecord)) == 1
        assert session.scalar(select(func.count()).select_from(RoundRecord)) == 1
        assert session.scalar(select(func.count()).select_from(Outbox)) == 1


def test_archive_and_revision_share_task_lock(pg_tasks):
    factory, user, other, _ = pg_tasks
    task_id = prepared(pg_tasks)
    def call(i):
        with factory() as session:
            try:
                if i == 0:
                    return create_archive(session, user, task_id, None)
                return accept_round(session, other, task_id,
                    RevisionInput(taskId=str(task_id), target=None, note='修改'), 'revision')
            except HTTPException as error:
                return error.status_code
    results = compete(call)
    assert results[1].state == '排队中'
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ArchiveRecord)) == (0 if results[0] == 409 else 1)
        assert session.scalar(select(func.count()).select_from(RoundRecord)) == 2


def test_delete_and_archive_do_not_resurrect_task(pg_tasks):
    factory, user, other, _ = pg_tasks
    task_id = prepared(pg_tasks)
    def call(i):
        with factory() as session:
            try:
                return create_archive(session, user, task_id, None) if i == 0 else delete_task(session, other, task_id)
            except HTTPException as error:
                return error.status_code
    results = compete(call)
    assert results[1].resourceType == 'task'
    with factory() as session:
        assert session.scalar(select(func.count()).select_from(ArchiveRecord)) == (0 if results[0] == 404 else 1)
