"""Permission and version checked cancellation; running slots remain occupied."""
from fastapi import HTTPException
from app.overseas.permissions import principal_for, require_task_access
from app.overseas.tasks.queries import get_task
from app.overseas.tasks.service import lock_actor
from .claims import locked_job, end
from .events import record, serialize
from .models import Job, TERMINAL


def cancel(session, actor, job_id, version):
    actor = lock_actor(session, actor, 'task.design')
    reference = session.get(Job, job_id)
    if reference is None:
        raise HTTPException(404, '海外执行作业不存在')
    task = get_task(session, reference.task_id, lock=True)
    require_task_access(principal_for(session, actor), task.created_by, task.designer_id, 'task.design')
    job = locked_job(session, job_id)
    if job.version != version:
        raise HTTPException(409, '执行状态已变化，请刷新后重试')
    if job.status in TERMINAL:
        raise HTTPException(409, '执行已经结束')
    if not job.cancel_requested:
        job.cancel_requested = True
        if job.status == 'queued':
            job.process_exited = True
            end(session, job, 'cancelled')
        else:
            # Uncertain retains its uncertainty and occupied slot until verified.
            job.status = 'uncertain' if job.status == 'uncertain' else 'cancelling'
            job.version += 1
            record(session, job)
    session.flush()
    result = serialize(job)
    session.commit()
    return result
