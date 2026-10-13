from fastapi import HTTPException
from sqlalchemy import update
from app.core.idempotency import fingerprint_payload, lookup_request
from app.db.timestamps import utcnow
from app.overseas.permissions import principal_for, require_task_access
from app.overseas.archives.models import Archive
from .models import TaskRequest
from .queries import detail, get_task
from .service import lock_actor, record_change, request_record, require_designer


def assign(session, actor, task_id, body, key):
    actor = lock_actor(session, actor, 'task.reassign')
    body_hash = fingerprint_payload(body.model_dump(mode='json'))
    previous = lookup_request(session, TaskRequest, actor.id, 'assignment', str(task_id), key, body_hash)
    task = get_task(session, task_id, lock=True)
    require_task_access(principal_for(session, actor), task.created_by, task.designer_id, 'task.reassign')
    if previous:
        result = detail(session, task.id, actor)
        session.commit()
        return result
    require_designer(session, body.designerId)
    if task.version != body.version:
        raise HTTPException(409, '任务已被修改，请刷新后重试')
    if task.designer_id == body.designerId:
        raise HTTPException(409, '该成员已经是当前负责人')
    before = task.designer_id
    task.designer_id = body.designerId
    # The parent lock also serializes archiving and deletion; transfer access atomically.
    session.execute(update(Archive).where(Archive.task_id == task.id)
        .values(designer_id=body.designerId))
    task.version += 1
    task.updated_at = utcnow()
    record_change(session, task, actor, 'task.assigned', before)
    request_record(session, actor, 'assignment', str(task_id), key, body_hash, task)
    session.flush()
    result = detail(session, task.id, actor)
    session.commit()
    return result
