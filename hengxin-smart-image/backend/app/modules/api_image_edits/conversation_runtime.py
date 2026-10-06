"""Lease fencing, shared CLI admission and durable public events."""
import json
import time
from datetime import timedelta
from uuid import UUID, uuid4
from sqlalchemy import func, or_, select
from app.capacity.admission import reserve, WAITING
from app.core.config import get_settings
from app.models import Job, Outbox, utcnow
from app.modules.tasks.models import ExecutionGate
from app.worker.leases import lease_active
from app.execution.public_messages import public_message
from .conversation import emit
from .conversation_models import Conversation, ConversationTurn
from .models import ApiItem, ApiTask


def locked(session, job_id):
    turn = session.scalar(select(ConversationTurn).where(ConversationTurn.job_id == UUID(str(job_id))))
    if not turn:
        return (None,) * 5
    conversation = session.get(Conversation, turn.conversation_id)
    item = session.get(ApiItem, conversation.item_id)
    task = session.scalar(select(ApiTask).where(ApiTask.id == item.task_id).with_for_update())
    session.refresh(item, with_for_update=True)
    session.refresh(conversation, with_for_update=True)
    session.refresh(turn, with_for_update=True)
    job = session.scalar(select(Job).where(Job.id == turn.job_id).with_for_update())
    return task, item, conversation, turn, job


def finish(session, conversation, turn, job, status, error=None):
    turn.status, turn.error, turn.finished_at = status, error, utcnow()
    job.status = 'succeeded' if status in ('candidate', 'waiting_user') else status
    job.error, job.completed_at, job.lease_until = error, utcnow(), None
    dispatch = session.get(Outbox, job.id)
    dispatch.completed_at = None if status == 'uncertain' and turn.cancel_requested else utcnow()
    emit(session, conversation, turn)


def claim(factory, job_id):
    with factory.begin() as session:
        if not session.scalar(select(ExecutionGate).where(ExecutionGate.id == 1).with_for_update()):
            raise RuntimeError('Execution gate missing')
        task, item, conversation, turn, job = locked(session, job_id)
        if not job:
            return None
        if job.status == 'running' and not lease_active(job):
            finish(session, conversation, turn, job, 'uncertain', '执行状态待核实，禁止自动重试')
        if job.status != 'queued' or turn.status != 'queued':
            return None
        if task.deleted_at or turn.cancel_requested:
            finish(session, conversation, turn, job, 'cancelled')
            return None
        count = session.scalar(select(func.count()).select_from(Job).where(
            Job.kind.in_(('generation', 'api_cli_edit')),
            Job.status.in_(('running', 'collecting', 'cancelling', 'uncertain'))))
        if count >= min(turn.snapshot.get('concurrency', get_settings().generation_concurrency),
                        get_settings().generation_concurrency):
            return None
        if not reserve(session, turn.id, 'cli', turn.id, 20 * 1024 * 1024):
            turn.error = WAITING
            return None
        token = uuid4()
        job.status, job.claim_token = 'running', token
        job.lease_until = utcnow() + timedelta(seconds=get_settings().job_lease_seconds)
        job.execution_count += 1
        turn.status, turn.started_at, turn.error = 'running', utcnow(), None
        emit(session, conversation, turn)
        return token


def valid(task, turn, job, token):
    return (not task.deleted_at and not turn.cancel_requested and turn.status == 'running'
            and job.status == 'running' and job.claim_token == token and lease_active(job))


class Monitor:
    def __init__(self, factory, job_id, token, path, previous):
        self.factory, self.job_id, self.token = factory, job_id, token
        self.path, self.previous, self.offset = path, previous, 0
        self.last_poll = 0

    def __call__(self):
        if time.monotonic() - self.last_poll < .5:
            return False
        self.last_poll = time.monotonic()
        events = []
        if self.path.exists():
            with self.path.open('rb') as stream:
                stream.seek(self.offset)
                for line in stream:
                    if not line.endswith(b'\n'):
                        break
                    self.offset += len(line)
                    try:
                        events.append(json.loads(line))
                    except (ValueError, UnicodeError):
                        pass
        with self.factory.begin() as session:
            task, _, conversation, turn, job = locked(session, self.job_id)
            if not job or not valid(task, turn, job, self.token):
                return True
            for event in events:
                if isinstance(event, dict) and event.get('type') == 'thread.started':
                    from re import fullmatch
                    sid = event.get('thread_id')
                    if isinstance(sid, str) and fullmatch(r'[A-Za-z0-9_-]{1,128}', sid):
                        if conversation.session_id not in (None, sid):
                            raise ValueError('Session mismatch')
                        conversation.session_id = sid
                message = public_message(event)
                if message:
                    turn.messages = [*turn.messages, message]
                    emit(session, conversation, turn, 'message', message)
            return False


def sweep(factory):
    with factory() as session:
        ids = session.scalars(select(Job.id).where(Job.kind == 'api_cli_edit', Job.status == 'running',
            or_(Job.lease_until.is_(None), Job.lease_until <= utcnow()))).all()
    for job_id in ids:
        with factory.begin() as session:
            _, _, conversation, turn, job = locked(session, job_id)
            if job.status == 'running' and not lease_active(job):
                finish(session, conversation, turn, job, 'uncertain', '执行中断，禁止自动重试')
