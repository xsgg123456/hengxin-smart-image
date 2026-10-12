from uuid import uuid4
from hashlib import sha256
from fastapi import HTTPException
from app.overseas.execution.models import Job
from app.overseas.execution.queue import enqueue
from app.overseas.pictures.models import Picture
from app.overseas.pictures.queries import slots
from app.overseas.plans.service import mutation, complete
from app.overseas.tasks.queries import detail


def create_slots(session, task, plan, job, sku):
    for position, picture in enumerate(sku['pictures']):
        session.add(Picture(task_id=task.id, plan_id=plan.id, job_id=job.id,
                            sku=sku['code'], position=position, title=picture['title']))


def retry(session, actor, task_id, body, key):
    target = str(task_id) + sha256(body.sku.encode('utf-8')).hexdigest()
    actor, task, digest, previous = mutation(session, actor, task_id, body, key, 'generation_retry', target)
    if previous:
        result = detail(session, task.id, actor)
        session.commit()
        return result
    pictures = [p for p in slots(session, task.id) if p.sku == body.sku]
    if task.status == 'archived' or not pictures or any(p.version for p in pictures):
        raise HTTPException(409, '当前SKU不能重试生图')
    jobs = {p.job_id for p in pictures}
    old = session.get(Job, pictures[0].job_id)
    if len(jobs) != 1 or old.kind != 'generation' or old.status not in ('failed', 'cancelled'):
        raise HTTPException(409, '作业仍在执行或等待核实')
    job = enqueue(session, task.id, 'generation', f'generation-retry:{uuid4()}', old.payload)
    for picture in pictures:
        picture.job_id = job.id
    task.status = 'generating'
    return complete(session, actor, task, 'generation_retry', target, key, digest)
