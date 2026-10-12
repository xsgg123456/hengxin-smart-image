from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from app.core.idempotency import fingerprint_payload, lookup_request
from app.db.timestamps import utcnow
from app.overseas.execution.models import Job, TERMINAL
from app.overseas.execution.queue import enqueue
from app.overseas.permissions import principal_for, require_task_access
from app.overseas.tasks.models import TaskRequest
from app.overseas.tasks.queries import detail, get_task
from app.overseas.tasks.service import lock_actor, record_change, request_record
from .models import Plan
from .schemas import validate_content
from .snapshot import freeze, GENERATION_SKILL
from app.overseas.management.settings import freeze as freeze_settings


def latest(session, task_id):
    return session.scalar(select(Plan).where(Plan.task_id == task_id).order_by(Plan.version.desc()).limit(1))


def plan_status(session, plan):
    job = session.get(Job, plan.job_id)
    if plan.status == 'pending' and job.status in ('failed', 'cancelled', 'uncertain'):
        return job.status
    return plan.status


def task_status(session, task):
    if task.status == 'analyzing':
        plan = latest(session, task.id)
        if plan and plan_status(session, plan) in ('failed', 'cancelled'):
            return 'analysisFailed'
    return task.status


def history(session, actor, task_id):
    task = get_task(session, task_id)
    require_task_access(principal_for(session, actor), task.created_by, task.designer_id)
    plans = session.scalars(select(Plan).where(Plan.task_id == task_id).order_by(Plan.version.desc()))
    return {'items': [{'id': str(p.id), 'taskId': str(p.task_id), 'version': p.version,
        'status': plan_status(session, p), 'jobId': str(p.job_id), 'feedback': p.feedback,
        'content': p.content, 'createdAt': p.created_at} for p in plans], 'taskVersion': task.version}


def enqueue_analysis(session, task, feedback=''):
    previous = latest(session, task.id)
    if previous:
        job = session.get(Job, previous.job_id)
        if job.status not in TERMINAL:
            raise HTTPException(409, '分析仍在执行或等待核实，不能重复启动')
        if previous.status == 'confirmed':
            raise HTTPException(409, '方案已经确认')
        if previous.status == 'ready' and not feedback.strip():
            raise HTTPException(422, '请填写修改意见')
    snapshot = freeze(session, task)
    identity, version = uuid4(), previous.version + 1 if previous else 1
    job = enqueue(session, task.id, 'reanalysis' if previous else 'analysis', f'plan:{identity}',
        {**snapshot, 'planId': str(identity), 'feedback': feedback,
         'previousPlan': previous.content if previous else None})
    plan = Plan(id=identity, task_id=task.id, version=version, job_id=job.id, feedback=feedback)
    session.add(plan)
    task.status = 'analyzing'
    session.flush()
    return plan


def mutation(session, actor, task_id, body, key, operation, target):
    actor = lock_actor(session, actor, 'task.design')
    digest = fingerprint_payload(body.model_dump(mode='json'))
    previous = lookup_request(session, TaskRequest, actor.id, operation, target, key, digest)
    task = get_task(session, task_id, lock=True)
    require_task_access(principal_for(session, actor), task.created_by, task.designer_id, 'task.design')
    if not previous and task.version != body.version:
        raise HTTPException(409, '任务已被修改，请刷新后重试')
    return actor, task, digest, previous


def complete(session, actor, task, operation, target, key, digest):
    task.version += 1
    task.updated_at = utcnow()
    record_change(session, task, actor, 'task.' + operation)
    request_record(session, actor, operation, target, key, digest, task)
    session.flush()
    result = detail(session, task.id, actor)
    session.commit()
    return result


def analyze(session, actor, task_id, body, key):
    target = str(task_id)
    actor, task, digest, previous = mutation(session, actor, task_id, body, key, 'analysis', target)
    if previous:
        result = detail(session, task.id, actor)
        session.commit()
        return result
    if task.status not in ('submitted', 'analyzing', 'plan'):
        raise HTTPException(409, '当前任务不能开始分析')
    enqueue_analysis(session, task, body.feedback)
    return complete(session, actor, task, 'analysis', target, key, digest)


def confirm(session, actor, task_id, plan_id, body, key):
    target = str(plan_id)
    actor, task, digest, previous = mutation(session, actor, task_id, body, key, 'plan_confirmed', target)
    if previous:
        result = detail(session, task.id, actor)
        session.commit()
        return result
    plan = latest(session, task.id)
    if not plan or plan.id != plan_id or plan.status != 'ready' or task.status != 'plan':
        raise HTTPException(409, '只能确认当前已完成的方案，请刷新')
    job = session.get(Job, plan.job_id)
    if job.status != 'succeeded':
        raise HTTPException(409, '分析尚未完成')
    content = validate_content(plan.content, [s['code'] for s in job.payload['task']['skus']])
    runtime = freeze_settings(session, 'generation', GENERATION_SKILL)
    for index, sku in enumerate(content['skus']):
        generation_job = enqueue(session, task.id, 'generation', f'plan:{plan.id}:sku:{index}',
            {**job.payload, **runtime, 'plan': content, 'sku': sku, 'planVersion': plan.version})
        from app.overseas.generation.service import create_slots
        create_slots(session, task, plan, generation_job, sku)
    plan.status = 'confirmed'
    plan.updated_at = utcnow()
    task.status = 'generating'
    return complete(session, actor, task, 'plan_confirmed', target, key, digest)
