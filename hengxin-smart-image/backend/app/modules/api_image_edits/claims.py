from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select

from app.models import utcnow
from .config import get_api_settings
from .models import ApiAttempt, ApiItem, ApiTask
from .scheduling import IMAGES_PER_TASK, TASK_CONCURRENCY, candidates
from .state import ACTIVE, aware, channel, event, refresh_task, release, release_item


def mark_uncertain(session, item):
    item.state, item.error = 'uncertain', '请求状态不确定，需管理员确认旧调用停止'
    release_item(item)
    task = session.get(ApiTask, item.task_id)
    for attempt in session.scalars(select(ApiAttempt).where(ApiAttempt.item_id == item.id,
                                                          ApiAttempt.state == 'running')):
        attempt.state, attempt.error = 'uncertain', item.error
        attempt.completed_at = utcnow()
    event(task, item.error)
    refresh_task(session, task)


def adopt_legacy(session, gate):
    """Preserve a pre-upgrade reservation rather than replay an in-flight request."""
    if gate.item_id:
        item = session.get(ApiItem, gate.item_id)
        if item and not item.lease_token:
            item.lease_token, item.lease_until = gate.token, gate.lease_until
        release(gate)


def claim(factory):
    settings = get_api_settings()
    if not settings.enabled:
        return None
    with factory.begin() as session:
        gate = channel(session)
        adopt_legacy(session, gate)
        now = utcnow()
        # Only admission holds the DB lock; each image owns its network-call lease.
        pending = session.scalars(select(ApiItem).join(ApiTask).where(
            ApiTask.deleted_at.is_(None), ApiItem.state.in_(ACTIVE))
            .order_by(ApiTask.created_at, ApiTask.id, ApiItem.position)).all()
        if not pending:
            return None
        for item in pending:
            if item.state == 'running' and (not item.lease_until or aware(item.lease_until) <= now):
                mark_uncertain(session, item)
        if gate.paused:
            return None
        leased = [item for item in pending if item.lease_token and item.lease_until
                  and aware(item.lease_until) > now]
        if len(leased) >= TASK_CONCURRENCY * IMAGES_PER_TASK:
            return None
        blocked = any(item.state == 'uncertain' for item in pending)
        for item in candidates(session, pending, leased, blocked):
            if item.lease_token and item.lease_until and aware(item.lease_until) > now:
                continue
            if item.next_attempt_at and aware(item.next_attempt_at) > now:
                continue
            item.lease_token = uuid4()
            item.lease_until = now + timedelta(seconds=settings.lease_seconds)
            item.state = 'collecting' if item.result_url or item.result_bytes else 'running'
            item.next_attempt_at = None
            task = session.get(ApiTask, item.task_id)
            task.state = 'running'
            task.started_at = task.started_at or now
            refresh_task(session, task)
            event(task, f'第 {item.position} 张开始处理')
            return item.id, item.lease_token, item.state
        return None


def owned(session, item_id, token):
    gate = channel(session)
    item = session.get(ApiItem, item_id)
    if not item or item.lease_token != token or not item.lease_until:
        return None, None
    if aware(item.lease_until) <= utcnow():
        if item.state == 'running':
            mark_uncertain(session, item)
        return None, None
    return gate, item


def start_attempt(factory, item_id, token):
    with factory.begin() as session:
        _, item = owned(session, item_id, token)
        if not item or item.state != 'running':
            return False
        task = session.get(ApiTask, item.task_id)
        if item.cycle_retries > 0:
            item.retries += 1
        session.add(ApiAttempt(item_id=item.id, operator_id=item.revision_operator_id or task.owner_id))
        return True
