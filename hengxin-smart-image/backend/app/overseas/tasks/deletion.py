"""Request erasure durably; maintenance performs and verifies the actual cleanup."""
from fastapi import HTTPException
from sqlalchemy import select
from app.overseas.permissions import authorize_member
from app.overseas.execution.models import Job, TERMINAL
from app.overseas.execution.queue import lock_gate
from app.overseas.execution.claims import end
from app.overseas.execution.events import record
from .models import Task, TaskDeletion
from .service import lock_actor


def dto(row):
    return dict(taskId=str(row.task_id), status=row.status, error=row.error)


def stopping(session, task_id):
    lock_gate(session)
    for job in session.scalars(select(Job).where(Job.task_id == task_id).with_for_update()):
        if job.status in TERMINAL:
            continue
        job.cancel_requested = True
        if job.status == 'queued':
            job.process_exited = True
            end(session, job, 'cancelled')
        elif job.status not in ('uncertain', 'cancelling'):
            job.status = 'cancelling'
            job.version += 1
            record(session, job)


def request(session, actor, task_id, body):
    actor = lock_actor(session, actor, 'task.delete')
    task = session.scalar(select(Task).where(Task.id == task_id).with_for_update()
        .execution_options(populate_existing=True))
    row = session.scalar(select(TaskDeletion).where(TaskDeletion.task_id == task_id).with_for_update())
    if row and row.status == 'deleted':
        result = dto(row)
        session.commit()
        return result
    if task is None:
        raise HTTPException(404, '海外任务不存在')
    if body.confirmationName != task.name:
        raise HTTPException(422, '请输入完整任务名称确认删除')
    if row is None:
        if task.version != body.version:
            raise HTTPException(409, '任务已修改，请刷新后重新确认删除')
        row = TaskDeletion(task_id=task.id, actor_id=actor.id, status='deleting', phase='stopping', manifest={})
        session.add(row)
        task.version += 1
    elif row.status == 'delete_failed':
        row.status, row.error = 'deleting', None
    stopping(session, task_id)
    session.flush()
    result = dto(row)
    session.commit()
    return result


def status(session, actor, task_id):
    authorize_member(session, actor, 'task.delete')
    row = session.get(TaskDeletion, task_id)
    if row is None:
        raise HTTPException(404, '任务删除记录不存在')
    return dto(row)
