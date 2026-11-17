"""Task ownership and lifecycle serialize with existing admission and row locks."""
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import OperationalError

from app.core.idempotency import fingerprint_payload, lookup_request
from app.db.timestamps import utcnow
from app.models import Job
from app.worker.leases import TERMINAL
from .bindings import lock_admission
from .conversation_models import Conversation, ConversationDeletion
from .conversation_service import lock_actor, workspace_state
from .task_models import Task, TaskRequest
from .turn_models import Turn, Upload


def owned(session, actor_id, identity, *, lock=False, include_deleted=False):
    statement = select(Task).where(Task.id == identity, Task.owner_id == actor_id)
    row = session.scalar((statement.with_for_update() if lock else statement)
                         .execution_options(populate_existing=True))
    if row is None or (row.deletion_status == 'deleted' and not include_deleted):
        raise HTTPException(404, '任务不存在或已删除')
    return row


def writable(task):
    if task.deletion_status:
        raise HTTPException(409, '任务正在删除或删除未完成，请重试删除')
    if task.completed:
        raise HTTPException(409, '任务已完成，请先重新打开')


def channel_task(session, channel, *, write=False, allow_deleting=False):
    scope = session.info.get('domestic_task_id')
    if scope is not None and channel.task_id != scope:
        raise HTTPException(404, '会话不属于当前任务')
    task = owned(session, channel.owner_id, channel.task_id)
    if task.workspace != channel.workspace:
        raise HTTPException(404, '会话业务不属于当前任务')
    if write and not allow_deleting:
        writable(task)
    return task


def receipt(session, actor_id, operation, target, key, payload):
    digest = fingerprint_payload(payload)
    return lookup_request(session, TaskRequest, actor_id, operation, target, key, digest), digest


def record(session, actor_id, operation, target, key, digest, identity):
    session.add(TaskRequest(user_id=actor_id, operation=operation, target=target,
                            key=key, body_hash=digest, task_id=identity))
    session.flush()


def create(session, actor_id, body, key):
    lock_actor(session, actor_id)
    lock_admission(session)
    old, digest = receipt(session, actor_id, 'create', body.workspace, key, body.model_dump(mode='json'))
    if old:
        return owned(session, actor_id, old.task_id)
    workspace_state(session, actor_id, body.workspace, create=True)
    task = Task(owner_id=actor_id, workspace=body.workspace, name=body.name)
    session.add(task)
    session.flush()
    record(session, actor_id, 'create', body.workspace, key, digest, task.id)
    return task


def idle(session, task, *, finishing=False):
    # A completion/deletion must serialize against uploads/recovery that do not
    # hold the admission lock during storage I/O. Never wait on those rows.
    try:
        channels = list(session.scalars(select(Conversation).where(Conversation.task_id == task.id)
                                       .with_for_update(nowait=True)))
    except OperationalError as exc:
        if getattr(exc.orig, 'sqlstate', None) == '55P03':
            raise HTTPException(409, '任务正在处理文件，请稍后重试') from None
        raise
    active = session.scalar(select(Turn.id).join(Conversation, Conversation.id == Turn.conversation_id)
        .join(Job, Job.id == Turn.job_id).where(Conversation.task_id == task.id,
                                              Job.status.not_in(TERMINAL)).limit(1))
    uploading = session.scalar(select(Upload.id).join(Conversation, Conversation.id == Upload.conversation_id)
        .where(Conversation.task_id == task.id, Upload.status != 'ready').limit(1))
    pending_outputs = False
    if finishing:
        intents = session.scalars(select(Turn.output_intents).join(Conversation, Conversation.id == Turn.conversation_id)
            .where(Conversation.task_id == task.id))
        pending_outputs = any(not isinstance(items, dict) or any(
            not isinstance(item, dict) or item.get('status') != 'ready' for item in items.values()) for items in intents)
    if finishing:
        from .archive_models import Archive, ArchiveDeletion
        pending_archive = session.scalar(select(Archive.id).join(Conversation,
            Conversation.id == Archive.source_conversation_id).outerjoin(ArchiveDeletion,
            ArchiveDeletion.archive_id == Archive.id).where(Conversation.task_id == task.id,
                (Archive.status != 'ready') | (ArchiveDeletion.status != 'deleted')).limit(1))
        pending_outputs = pending_outputs or bool(pending_archive)
    if active or (finishing and uploading) or pending_outputs:
        raise HTTPException(409, '任务存在执行或文件处理，请等待结束后重试')
    return channels


def update(session, actor_id, identity, body, key):
    lock_actor(session, actor_id)
    lock_admission(session)
    task = owned(session, actor_id, identity, lock=True)
    old, digest = receipt(session, actor_id, 'update', str(identity), key, body.model_dump(mode='json'))
    if old:
        return task
    if task.deletion_status:
        raise HTTPException(409, '任务删除尚未完成')
    if task.version != body.version:
        raise HTTPException(409, '任务已更新，请刷新后重试')
    if task.completed and body.name is not None:
        raise HTTPException(409, '任务已完成，请先重新打开')
    if body.completed is True:
        idle(session, task, finishing=True)
        pending = session.scalar(select(ConversationDeletion.conversation_id).join(Conversation,
            Conversation.id == ConversationDeletion.conversation_id).where(Conversation.task_id == task.id,
                ConversationDeletion.status != 'deleted').limit(1))
        if pending:
            raise HTTPException(409, '任务存在尚未完成的会话清理')
    if body.name is not None:
        task.name = body.name
    if body.completed is not None:
        task.completed = body.completed
    task.version += 1
    task.updated_at = utcnow()
    record(session, actor_id, 'update', str(identity), key, digest, task.id)
    return task
