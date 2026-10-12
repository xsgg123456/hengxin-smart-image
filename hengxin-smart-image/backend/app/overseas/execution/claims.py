"""A database singleton serializes all transitions and the five shared slots."""
from datetime import timedelta, timezone
from uuid import UUID, uuid4
from sqlalchemy import func, or_, select
from app.core.config import get_settings
from app.db.timestamps import utcnow
from .models import ACTIVE, TERMINAL, Job, JobOutbox
from .events import MESSAGES, record
from .queue import lock_gate
from app.overseas.management.models import Settings


def locked_job(session, job_id, gate=True):
    # Gate first also preserves event cursor commit order across workers.
    if gate:
        lock_gate(session)
    return session.scalar(select(Job).where(Job.id == UUID(str(job_id)))
                          .with_for_update().execution_options(populate_existing=True))


def lease_active(job):
    return bool(job.lease_until and job.lease_until.replace(tzinfo=timezone.utc) > utcnow())


def valid(job, token):
    return bool(job and job.claim_token == token and job.status in ('running', 'collecting')
                and not job.cancel_requested and lease_active(job))


def mark_uncertain(session, job):
    if job.status != 'uncertain':
        job.status, job.error = 'uncertain', MESSAGES['uncertain']
        job.version += 1
        record(session, job)


def end(session, job, status, error=None, result=None):
    if status not in TERMINAL:
        raise ValueError('Invalid terminal status')
    job.status, job.error, job.result = status, MESSAGES[status] if error else None, result
    job.completed_at, job.lease_until = utcnow(), None
    job.version += 1
    row = session.get(JobOutbox, job.id)
    if row:
        row.completed_at = job.completed_at
    record(session, job)


def sweep_expired(factory):
    with factory.begin() as session:
        lock_gate(session)
        jobs = session.scalars(select(Job).where(Job.status.in_(('running', 'collecting', 'cancelling')),
            or_(Job.lease_until.is_(None), Job.lease_until <= utcnow())).with_for_update()).all()
        for job in jobs:
            mark_uncertain(session, job)
        return len(jobs)


def claim(factory, job_id, admission=None):
    with factory.begin() as session:
        gate = lock_gate(session)
        job = locked_job(session, job_id, gate=False)
        if not job:
            return None
        if job.status in ('running', 'collecting', 'cancelling') and not lease_active(job):
            mark_uncertain(session, job)
        if job.status != 'queued':
            return None
        if job.cancel_requested:
            job.process_exited = True  # A queued job has never started a process.
            end(session, job, 'cancelled')
            return None
        occupied = session.scalar(select(func.count()).select_from(Job).where(Job.status.in_(ACTIVE)))
        config = session.get(Settings, 1)
        capacity = (config.values.get('concurrency', 5) if config else 5)
        if (gate.paused or (config and config.values.get('paused', False))
                or occupied >= min(5, capacity, get_settings().generation_concurrency)
                or (admission is not None and not admission())):
            return None
        job.claim_token, job.status = uuid4(), 'running'
        job.lease_until = utcnow() + timedelta(seconds=get_settings().job_lease_seconds)
        job.started_at, job.error = utcnow(), None
        job.process_exited = False
        job.execution_count += 1
        job.version += 1
        record(session, job)
        return job.claim_token


def renew(factory, job_id, token):
    with factory.begin() as session:
        job = locked_job(session, job_id)
        if not job or job.claim_token != token or job.status not in ('running', 'collecting', 'cancelling'):
            return False
        if not lease_active(job):
            mark_uncertain(session, job)
            return False
        job.lease_until = utcnow() + timedelta(seconds=get_settings().job_lease_seconds)
        return True


def finish(factory, job_id, token, status, result=None, error=None, publish=None):
    if status not in TERMINAL:
        raise ValueError('Invalid terminal status')
    with factory.begin() as session:
        if publish is not None:
            # Business publishers update this task. Match cancellation/enqueue lock order.
            from app.overseas.tasks.models import Task
            task_id = session.scalar(select(Job.task_id).where(Job.id == UUID(str(job_id))))
            if task_id is not None:
                session.scalar(select(Task).where(Task.id == task_id).with_for_update())
        job = locked_job(session, job_id)
        if not job or job.claim_token != token or job.status not in ACTIVE or not job.process_exited:
            return False
        if status == 'succeeded' and not valid(job, token):
            if job.status in ('running', 'collecting') and not lease_active(job):
                mark_uncertain(session, job)
            return False
        # Cancellation can never publish a result, even if completion races it.
        if job.cancel_requested and status != 'cancelled':
            return False
        if status == 'succeeded' and publish is not None:
            publish(session, job, result)
        end(session, job, status, error, result if status == 'succeeded' else None)
        return True
