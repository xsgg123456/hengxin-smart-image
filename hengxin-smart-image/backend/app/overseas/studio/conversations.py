"""Task-locked conversation mutations and durable erasure requests."""
from fastapi import HTTPException
from sqlalchemy import func, select
from app.core.idempotency import fingerprint_payload, lookup_request
from app.db.timestamps import utcnow
from app.overseas.tasks.models import TaskRequest
from app.overseas.tasks.service import lock_actor
from .models import Conversation, ConversationDeletion
from . import queries


def create(session, task, name=None):
    # Every caller holds the task row; concurrent inserts cannot exceed the cap.
    count = session.scalar(select(func.count()).select_from(Conversation).where(Conversation.task_id == task.id))
    if count >= 10:
        raise HTTPException(409, '每个任务最多保留10个会话，请先删除会话后重试')
    row = Conversation(task_id=task.id, name=name or f'会话 {count + 1}')
    session.add(row)
    session.flush()
    return row


def mutation(session, actor, task_id, identity, body, key, operation):
    actor = lock_actor(session, actor, 'task.design')
    task = queries.access(session, actor, task_id, write=True)
    digest = fingerprint_payload(body.model_dump(mode='json'))
    previous = lookup_request(session, TaskRequest, actor.id, operation, str(identity), key, digest)
    row = queries.conversation(session, task.id, identity)
    if not previous:
        if task.status != 'studio' or not task.requirements_approved:
            raise HTTPException(409, '当前任务不能修改会话')
        if row.version != body.version:
            raise HTTPException(409, '会话已更新，请刷新后重试')
    return actor, task, row, digest, previous


def finish(session, actor, task, row, key, digest, operation):
    session.add(TaskRequest(user_id=actor.id, operation=operation, target=str(row.id), key=key,
        body_hash=digest, task_id=task.id, conversation_id=row.id))
    session.flush()
    return replay(session, actor, task, row)


def replay(session, actor, task, row):
    result = queries.view(session, actor, task.id, row.id)
    session.commit()
    return result


def rename(session, actor, task_id, identity, body, key):
    actor, task, row, digest, previous = mutation(session, actor, task_id, identity, body, key, 'studio_rename')
    if previous:
        return replay(session, actor, task, row)
    queries.conversation(session, task.id, identity, writable=True)
    row.name, row.version, row.updated_at = body.name, row.version + 1, utcnow()
    return finish(session, actor, task, row, key, digest, 'studio_rename')


def remove(session, actor, task_id, identity, body, key):
    actor, task, row, digest, previous = mutation(session, actor, task_id, identity, body, key, 'studio_delete')
    if previous:
        return replay(session, actor, task, row)
    from .service import active
    if active(session, task, identity):
        raise HTTPException(409, '会话仍有排队或执行中的轮次，请先停止并等待结束')
    receipt = session.get(ConversationDeletion, identity)
    if receipt is None:
        session.add(ConversationDeletion(conversation_id=identity, task_id=task.id,
            actor_id=actor.id, status='deleting', manifest={}))
        row.version += 1
    elif receipt.status == 'delete_failed':
        receipt.status, receipt.error = 'deleting', None
    row.updated_at = utcnow()
    return finish(session, actor, task, row, key, digest, 'studio_delete')
