from fastapi import HTTPException
from app.core.idempotency import fingerprint_payload, lookup_request
from app.overseas.permissions import principal_for, require_task_access
from app.overseas.tasks.models import TaskRequest
from app.overseas.tasks.queries import get_task, detail
from app.overseas.tasks.service import lock_actor
from app.overseas.plans.service import complete
from app.overseas.execution.models import Job
from .models import Picture


def mutation(session, actor, picture_id, body, key, operation):
    actor = lock_actor(session, actor, 'task.design')
    picture = session.get(Picture, picture_id)
    if not picture:
        raise HTTPException(404, '图片不存在')
    task = get_task(session, picture.task_id, lock=True)
    require_task_access(principal_for(session, actor), task.created_by, task.designer_id, 'task.design')
    session.refresh(picture)
    digest = fingerprint_payload(body.model_dump(mode='json'))
    previous = lookup_request(session, TaskRequest, actor.id, operation, str(picture.id), key, digest)
    if not previous:
        if task.status == 'archived' or task.version != body.taskVersion or picture.version != body.version:
            raise HTTPException(409, '任务或图片版本已改变，请刷新')
        if session.get(Job, picture.job_id).status not in ('succeeded', 'failed', 'cancelled'):
            raise HTTPException(409, '图片仍在执行或等待核实')
    return actor, task, picture, digest, previous


def replay(session, actor, task):
    result = detail(session, task.id, actor)
    session.commit()
    return result


def approve(session, actor, picture_id, body, key):
    operation = 'picture_approved'
    actor, task, picture, digest, previous = mutation(session, actor, picture_id, body, key, operation)
    if previous:
        return replay(session, actor, task)
    from .queries import version
    if session.get(Job, picture.job_id).status != 'succeeded' or not picture.version or not version(session, picture):
        raise HTTPException(409, '请先完成当前图片生成或返工')
    picture.approved_version = picture.version
    return complete(session, actor, task, operation, str(picture.id), key, digest)
