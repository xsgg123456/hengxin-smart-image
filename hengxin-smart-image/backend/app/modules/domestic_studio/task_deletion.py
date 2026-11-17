"""Persistent task deletion aggregates the existing private cleanup receipts."""
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select

from app.db.timestamps import utcnow
from . import conversation_deletion, task_service
from .bindings import lock_admission
from .conversation_models import Conversation, ConversationDeletion
from .conversation_service import lock_actor
from .task_models import Task


def state(session, task):
    if task.deletion_status not in ('deleting', 'delete_failed'):
        return task.deletion_status, task.deletion_error
    receipts = [session.get(ConversationDeletion, UUID(value)) for value in task.deletion_manifest]
    remaining = session.scalar(select(Conversation.id).where(Conversation.task_id == task.id).limit(1))
    if remaining is None and all(row and row.status == 'deleted' for row in receipts):
        return 'deleted', None
    failed = next((row for row in receipts if row and row.status == 'delete_failed'), None)
    if failed:
        return 'delete_failed', failed.error or '会话清理未完成，请重试删除'
    return 'deleting', None


def dto(session, task):
    status, error = state(session, task)
    if status is None:
        raise HTTPException(404, '任务尚未请求删除')
    return dict(status=status, error=error)


def request(session, actor_id, identity, version):
    lock_actor(session, actor_id)
    lock_admission(session)
    task = task_service.owned(session, actor_id, identity, lock=True, include_deleted=True)
    if task.deletion_status:
        status, _ = state(session, task)
        if status in ('deleted', 'deleting'):
            return dto(session, task)
    elif task.version != version:
        raise HTTPException(409, '任务已更新，请刷新后重试')
    channels = task_service.idle(session, task)
    # All per-conversation requests belong to this transaction. A single
    # rejection rolls back the complete task request, never partially freezes it.
    for channel in channels:
        conversation_deletion.request(session, actor_id, task.workspace, channel.id,
                                      channel.version, task_delete=True)
    task.deletion_manifest = list(dict.fromkeys(task.deletion_manifest + [str(row.id) for row in channels]))
    task.deletion_status, task.deletion_error = 'deleting', None
    task.version += 1
    task.updated_at = utcnow()
    session.flush()
    task.deletion_status, task.deletion_error = state(session, task)
    return dto(session, task)


def reconcile(session, identity):
    task = session.scalar(select(Task).where(Task.id == identity).with_for_update())
    if task and task.deletion_status in ('deleting', 'delete_failed'):
        status, error = state(session, task)
        if (status, error) != (task.deletion_status, task.deletion_error):
            task.deletion_status, task.deletion_error = status, error
            task.version += 1
            task.updated_at = utcnow()
