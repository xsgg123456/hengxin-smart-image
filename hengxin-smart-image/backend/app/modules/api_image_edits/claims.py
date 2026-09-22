from datetime import timedelta
from uuid import uuid4

from sqlalchemy import select

from app.models import utcnow
from .config import get_api_settings
from .models import ApiAttempt, ApiItem, ApiTask
from .state import ACTIVE, aware, channel, event, refresh_task, release


def mark_uncertain(session, gate, item):
    item.state, item.error = 'uncertain', '请求状态不确定，需管理员确认旧调用停止'
    gate.token = None  # Fence a worker that returns after its durable lease expired.
    task = session.get(ApiTask, item.task_id)
    for attempt in session.scalars(select(ApiAttempt).where(ApiAttempt.item_id == item.id,
                                                          ApiAttempt.state == 'running')):
        attempt.state, attempt.error = 'uncertain', item.error
        attempt.completed_at = utcnow()
    event(task, item.error)
    refresh_task(session, task)


def claim(factory):
    settings = get_api_settings()
    if not settings.enabled:
        return None
    with factory.begin() as session:
        gate = channel(session)
        now = utcnow()
        item = session.get(ApiItem, gate.item_id) if gate.item_id else None
        if item:
            if item.state == 'uncertain':
                return None
            if item.state == 'running':
                if aware(gate.lease_until) <= now:
                    mark_uncertain(session, gate, item)
                return None
            if gate.token and aware(gate.lease_until) > now:
                return None
            if item.state not in ACTIVE:
                release(gate)
                item = None
        if gate.paused:
            return None
        if item is None:
            item = session.scalar(select(ApiItem).join(ApiTask).where(
                ApiTask.deleted_at.is_(None), ApiItem.state.in_(ACTIVE))
                .order_by(ApiTask.created_at, ApiTask.id, ApiItem.position).limit(1))
        if item is None or item.state == 'uncertain':
            return None
        if item.next_attempt_at and aware(item.next_attempt_at) > now:
            return None
        gate.item_id, gate.token = item.id, uuid4()
        gate.lease_until = now + timedelta(seconds=settings.lease_seconds)
        item.state = 'collecting' if item.result_url or item.result_bytes else 'running'
        item.next_attempt_at = None
        task = session.get(ApiTask, item.task_id)
        task.state, task.started_at = 'running', task.started_at or now
        event(task, f'第 {item.position} 张开始处理')
        return item.id, gate.token, item.state


def owned(session, item_id, token):
    gate = channel(session)
    if gate.item_id != item_id or gate.token != token:
        return None, None
    return gate, session.get(ApiItem, item_id)


def start_attempt(factory, item_id, token):
    with factory.begin() as session:
        gate, item = owned(session, item_id, token)
        if not item or item.state != 'running':
            return False
        if aware(gate.lease_until) <= utcnow():
            mark_uncertain(session, gate, item)
            return False
        task = session.get(ApiTask, item.task_id)
        if session.scalar(select(ApiAttempt.id).where(ApiAttempt.item_id == item.id).limit(1)):
            item.retries += 1
        session.add(ApiAttempt(item_id=item.id, operator_id=task.operator_id))
        return True
