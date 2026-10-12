"""Transactional enqueue and indefinitely replayable outbox publication."""
import json
from datetime import timedelta
from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select
from app.core.config import get_settings
from app.core.idempotency import fingerprint_payload
from app.db.timestamps import utcnow
from .models import Job, JobOutbox, ExecutionGate, KINDS
from .events import record


def lock_gate(session):
    gate = session.scalar(select(ExecutionGate).where(ExecutionGate.id == 1)
                          .with_for_update().execution_options(populate_existing=True))
    if gate is None:
        raise RuntimeError('Overseas execution gate missing; apply migrations')
    return gate


def enqueue(session, task_id, kind, dedupe_key, payload):
    if kind not in KINDS or not isinstance(payload, dict):
        raise ValueError('Invalid overseas execution input')
    if not dedupe_key or not dedupe_key.strip() or len(dedupe_key) > 200:
        raise ValueError('Invalid overseas execution dedupe key')
    frozen = json.loads(json.dumps(payload, allow_nan=False))
    # Serializes duplicate insert and admission without database-specific upsert semantics.
    lock_gate(session)
    previous = session.scalar(select(Job).where(Job.dedupe_key == dedupe_key))
    if previous:
        if (previous.task_id != UUID(str(task_id)) or previous.kind != kind
                or fingerprint_payload(previous.payload) != fingerprint_payload(frozen)):
            raise HTTPException(409, '同一执行幂等键不能提交不同内容')
        return previous
    job = Job(task_id=UUID(str(task_id)), kind=kind, dedupe_key=dedupe_key, payload=frozen)
    session.add(job)
    session.flush()
    session.add(JobOutbox(job_id=job.id))
    record(session, job)
    session.flush()
    return job


def publish(job_id):
    from app.overseas.execution.worker import celery_app
    celery_app.send_task('hengxin.overseas.job', args=[str(job_id)],
                         task_id=str(job_id), queue='overseas.cli', retry=False)


def dispatch_once(factory, sender=publish):
    from .claims import sweep_expired
    sweep_expired(factory)
    with factory.begin() as session:
        rows = session.scalars(select(JobOutbox).join(Job, Job.id == JobOutbox.job_id).where(
            JobOutbox.completed_at.is_(None), JobOutbox.next_dispatch_at <= utcnow(),
            Job.status == 'queued').order_by(JobOutbox.next_dispatch_at)
            .limit(100).with_for_update(of=JobOutbox, skip_locked=True)).all()
        for row in rows:
            sender(row.job_id)
            row.dispatch_count += 1
            row.next_dispatch_at = utcnow() + timedelta(seconds=get_settings().outbox_redispatch_seconds)
        return len(rows)
