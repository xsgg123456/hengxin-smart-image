"""Domestic Studio claim and lease fencing; ambiguous executions never rerun."""
from datetime import timedelta
from uuid import UUID, uuid4

from sqlalchemy import or_, select

from app.capacity.admission import WAITING, reserve
from app.core.config import get_settings
from app.db.timestamps import utcnow
from app.execution.cli_capacity import active_count
from app.models import Job, Outbox
from app.worker.leases import lease_active
from .bindings import lock_admission
from .conversation_models import Conversation, Workspace
from .skill_references import JOB_KIND
from .turn_models import Turn


def locked(session, job_id):
    turn = session.scalar(select(Turn).where(Turn.job_id == UUID(str(job_id))))
    if turn is None:
        return (None,) * 4
    channel = session.scalar(select(Conversation).where(Conversation.id == turn.conversation_id)
                             .with_for_update().execution_options(populate_existing=True))
    if channel is None:
        return (None,) * 4
    state = session.scalar(select(Workspace).where(Workspace.owner_id == channel.owner_id,
        Workspace.workspace == channel.workspace).execution_options(populate_existing=True))
    turn = session.scalar(select(Turn).where(Turn.id == turn.id).with_for_update()
                          .execution_options(populate_existing=True))
    job = session.scalar(select(Job).where(Job.id == turn.job_id).with_for_update()
                         .execution_options(populate_existing=True)) if turn else None
    if not state or not turn or not job or turn.actor_id != channel.owner_id or job.kind != JOB_KIND:
        return (None,) * 4
    return state, channel, turn, job


def changed(state, channel, turn):
    state.version += 1
    channel.version += 1
    turn.version += 1


def finish(session, state, channel, turn, job, status, error=None):
    turn.error, turn.finished_at = error, utcnow()
    job.status, job.error = status, error
    job.completed_at, job.lease_until = utcnow(), None
    outbox = session.get(Outbox, job.id)
    if outbox is None:
        raise RuntimeError('Domestic Studio outbox missing')
    outbox.completed_at = None if status == 'uncertain' and turn.cancel_requested else utcnow()
    changed(state, channel, turn)


def valid(turn, job, token):
    return (not turn.cancel_requested and job.status == 'running'
            and job.claim_token == token and lease_active(job))


def claim(factory, job_id):
    with factory.begin() as session:
        lock_admission(session)
        state, channel, turn, job = locked(session, job_id)
        if job is None:
            return None
        if job.status == 'running' and not lease_active(job):
            finish(session, state, channel, turn, job, 'uncertain', '执行状态待核实，禁止自动重试')
        if job.status != 'queued':
            return None
        if turn.cancel_requested:
            finish(session, state, channel, turn, job, 'cancelled')
            return None
        limit = min(turn.snapshot.get('concurrency', get_settings().generation_concurrency),
                    get_settings().generation_concurrency)
        if active_count(session) >= limit:
            return None
        if not reserve(session, turn.id, 'cli', turn.id, 20 * 1024 * 1024):
            turn.error = WAITING
            return None
        token = uuid4()
        job.status, job.claim_token = 'running', token
        job.lease_until = utcnow() + timedelta(seconds=get_settings().job_lease_seconds)
        job.execution_count += 1
        turn.started_at, turn.error = utcnow(), None
        changed(state, channel, turn)
        return token


def sweep(factory):
    with factory() as session:
        ids = session.scalars(select(Job.id).where(Job.kind == JOB_KIND, Job.status == 'running',
            or_(Job.lease_until.is_(None), Job.lease_until <= utcnow()))).all()
    for identity in ids:
        with factory.begin() as session:
            lock_admission(session)
            state, channel, turn, job = locked(session, identity)
            if job and job.status == 'running' and not lease_active(job):
                finish(session, state, channel, turn, job, 'uncertain', '执行中断，禁止自动重试')
