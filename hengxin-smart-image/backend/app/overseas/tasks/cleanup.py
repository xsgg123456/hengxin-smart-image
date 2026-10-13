"""Resumable erasure runs on the native overseas maintenance worker, never in HTTP."""
from sqlalchemy import select
from app.overseas.db import require_overseas_context
from app.overseas.archives.models import Archive
from app.overseas.archives.snapshot import protect
from app.storage.minio_store import get_store
from .models import Task, TaskDeletion
from .deletion import stopping
from . import cleanup_files, cleanup_process, cleanup_records

ERRORS = dict(stopping='执行停止状态尚未核实，任务资料已保留，请稍后重试',
    protecting='归档文件保护或完整性校验失败，原任务已保留，请修复后重试',
    inventory='任务文件归属或目录校验失败，已停止清理，请联系管理员',
    erasing='任务文件清理未完成，已归档成品保留，可重试继续清理')


def locked(session, task_id):
    # Same order as HTTP mutation and archive access: task, then deletion receipt.
    task = session.scalar(select(Task).where(Task.id == task_id).with_for_update())
    row = session.scalar(select(TaskDeletion).where(TaskDeletion.task_id == task_id)
        .with_for_update(skip_locked=True).execution_options(populate_existing=True))
    return task, row


def process(factory, store, task_id):
    phase = 'stopping'
    try:
        with factory.begin() as session:
            task, row = locked(session, task_id)
            if row is None or row.status != 'deleting':
                return False
            if task is None:
                raise ValueError('Missing task before verified erasure')
            stopping(session, task_id)
            if not cleanup_process.confirmed(session, task_id):
                row.error = ERRORS['stopping']
                return False
            phase = 'protecting'
            for record in session.scalars(select(Archive).where(Archive.task_id == task_id)):
                protect(session, store, record, task)
            # The independent archive transaction commits before storage erasure.
            if not row.manifest:
                phase = 'inventory'
                row.manifest = cleanup_files.inventory(session, task_id, store)
            row.phase, row.error = 'erasing', None
        phase = 'erasing'
        with factory.begin() as session:
            task, row = locked(session, task_id)
            if row is None or row.status != 'deleting':
                return False
            if not cleanup_process.confirmed(session, task_id):
                raise ValueError('Process state changed')
            cleanup_files.erase(store, row.manifest)
            cleanup_records.erase(session, task_id)
            row.status, row.phase, row.error, row.manifest = 'deleted', 'done', None, {}
        return True
    except Exception:
        with factory.begin() as session:
            _, row = locked(session, task_id)
            if row and row.status != 'deleted':
                row.status, row.error = 'delete_failed', ERRORS[phase]
        return False


def cleanup_once(factory, store=None):
    require_overseas_context()
    store = store or get_store()
    with factory() as session:
        identities = session.scalars(select(TaskDeletion.task_id).where(
            TaskDeletion.status == 'deleting').order_by(TaskDeletion.created_at).limit(20)).all()
    return sum(process(factory, store, identity) for identity in identities)
