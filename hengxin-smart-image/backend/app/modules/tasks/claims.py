from datetime import timedelta
from uuid import UUID, uuid4
from sqlalchemy import func, select, or_
from app.core.config import get_settings
from app.models import Job, Outbox, utcnow
from app.worker.leases import lease_active
from .models import ExecutionGate, RoundRecord, TaskRecord


def locked_execution(session, job_id, gate=False):
    if gate:
        # Migration seeds this singleton; tests creating metadata seed it explicitly.
        if session.scalar(select(ExecutionGate).where(ExecutionGate.id == 1).with_for_update()) is None:
            raise RuntimeError('Execution gate missing; apply migrations before starting workers')
    round_info = session.scalar(select(RoundRecord).where(RoundRecord.job_id == UUID(str(job_id))))
    if not round_info:
        return None, None, None
    task = session.scalar(select(TaskRecord).where(TaskRecord.id == round_info.task_id)
        .with_for_update().execution_options(populate_existing=True))
    round = session.scalar(select(RoundRecord).where(RoundRecord.id == round_info.id)
        .with_for_update().execution_options(populate_existing=True))
    job = session.scalar(select(Job).where(Job.id == round.job_id).with_for_update()
                         .execution_options(populate_existing=True))
    return task, round, job


def end(session, round, job, status, error=None):
    round.status, round.error, round.finished_at = status, error, utcnow()
    job.status, job.error, job.completed_at, job.lease_until = status, error, utcnow(), None
    outbox = session.get(Outbox, job.id)
    if outbox:
        outbox.completed_at = job.completed_at


def mark_uncertain(round, job):
    round.status = job.status = 'uncertain'
    round.error = job.error = '执行状态待核实，禁止重新执行'


def sweep_expired(factory):
    with factory() as session:
        ids = session.scalars(select(Job.id).where(Job.kind == 'generation',
            Job.status.in_(['running', 'collecting', 'cancelling']),
            or_(Job.lease_until.is_(None), Job.lease_until <= utcnow()))).all()
    for job_id in ids:
        with factory.begin() as session:
            task, round, job = locked_execution(session, job_id, gate=True)
            if job and job.status in ('running', 'collecting', 'cancelling') and not lease_active(job):
                mark_uncertain(round, job)


def claim(factory, job_id):
    with factory.begin() as session:
        task, round, job = locked_execution(session, job_id, gate=True)
        if not job:
            return None
        if job.status in ('running', 'collecting', 'cancelling') and not lease_active(job):
            mark_uncertain(round, job)
        if job.status != 'queued' or round.status != 'queued':
            return None
        if task.deleted_at or round.cancel_requested or task.current_round_id != round.id:
            end(session, round, job, 'cancelled')
            return None
        occupied = session.scalar(select(func.count()).select_from(Job).where(
            Job.kind == 'generation', Job.status.in_(['running', 'collecting', 'cancelling', 'uncertain'])))
        if occupied >= get_settings().generation_concurrency:
            return None
        token = uuid4()
        job.claim_token, job.status = token, 'running'
        job.lease_until = utcnow() + timedelta(seconds=get_settings().job_lease_seconds)
        job.execution_count += 1
        round.status, round.started_at = 'running', utcnow()
        return token


def valid(task, round, job, token):
    return (task and not task.deleted_at and task.current_round_id == round.id
        and not round.cancel_requested and round.status in ('running', 'collecting')
        and job.status in ('running', 'collecting') and job.claim_token == token and lease_active(job))


def cancelled(factory, job_id, token):
    with factory.begin() as session:
        task, round, job = locked_execution(session, job_id)
        if not job or job.claim_token != token:
            return True
        if job.status not in ('running', 'collecting', 'cancelling', 'uncertain') or task.current_round_id != round.id:
            return True
        if round.cancel_requested or task.deleted_at:
            # Fixture has no external process: the caller has stopped execution before acknowledging.
            end(session, round, job, 'cancelled')
            return True
        if not valid(task, round, job, token):
            if job.status in ('running', 'collecting') and not lease_active(job):
                mark_uncertain(round, job)
            return True
        return False
