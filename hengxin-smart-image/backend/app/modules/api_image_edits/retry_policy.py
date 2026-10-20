"""Durable per-image generation budget; collection never starts a new cycle."""
import random
from datetime import timedelta
from uuid import uuid4

from sqlalchemy import func, select

from app.models import utcnow
from .state import aware, release_item

REASONS = {
    'user_stopped': '已停止后续重试',
    'attempts_exhausted': '本轮尝试次数已用完',
    'deadline_exceeded': '本轮已超过45分钟发送期限',
    'uncertain': '正在恢复处理',
    'retry_wait': '上游暂时不可用，等待自动重试',
    'rate_wait': '等待通道发送名额',
    'capacity_wait': '等待通道在途名额',
    'cooldown': '上游冷却中，等待恢复探测',
    'probe_wait': '正在探测上游恢复情况',
    'permanent': '本次请求不可重试，请检查输入或配置',
    'channel': '通道已暂停，请管理员检查配置',
}


def database_now(session):
    # Read after acquiring the row lock: transaction_timestamp predates lock waits.
    if session.bind.dialect.name == 'postgresql':
        return session.scalar(select(func.clock_timestamp()))
    return utcnow()  # SQLite is only used by isolated single-process tests.


def new_cycle(item):
    item.retry_cycle_id, item.retry_policy_version = uuid4(), 'bounded-v2'
    item.attempts, item.max_attempts = 0, 20
    item.retry_started_at = item.retry_deadline_at = None
    item.stop_requested, item.retry_reason = False, None


def inherit_legacy(session, item):
    if item.retry_cycle_id:
        return
    from .models import ApiAttempt
    item.retry_cycle_id, item.retry_policy_version = uuid4(), 'legacy-v1'
    item.max_attempts = 4
    # Old schema has no cycle key. Never guess which historical attempt was reset.
    count = session.scalar(select(func.count()).select_from(ApiAttempt).where(ApiAttempt.item_id == item.id))
    item.attempts = min(4, max(item.attempts or 0, item.cycle_retries or 0, count or 0))
    if item.state in {'running', 'uncertain'}:
        latest = session.scalar(select(ApiAttempt).where(ApiAttempt.item_id == item.id,
            ApiAttempt.state.in_(('running', 'uncertain'))).order_by(ApiAttempt.created_at.desc()).limit(1))
        if latest:
            latest.retry_cycle_id = item.retry_cycle_id


def exhausted(item, now):
    if item.stop_requested:
        return 'user_stopped'
    if item.attempts >= item.max_attempts:
        return 'attempts_exhausted'
    if item.retry_deadline_at and aware(item.retry_deadline_at) <= now:
        return 'deadline_exceeded'
    return None


def end_wait(item, reason):
    item.state, item.retry_reason, item.error = 'failed', reason, REASONS[reason]
    item.next_attempt_at = None
    release_item(item)


def retry_delay(item, retry_after=None):
    if item.retry_policy_version == 'legacy-v1':
        delay = 2 ** min(item.cycle_retries, 2)
    else:
        ceiling = (10, 20, 40)[item.attempts - 1] if 1 <= item.attempts <= 3 else 60
        delay = random.uniform(ceiling / 2, ceiling)
    return max(delay, retry_after or 0)


def consume(item, now):
    item.attempts += 1
    if item.retry_started_at is None:
        item.retry_started_at = now
        if item.retry_policy_version == 'bounded-v2':
            item.retry_deadline_at = now + timedelta(minutes=45)
    item.retry_reason = None


def view(item):
    def iso(value):
        return aware(value).isoformat() if value else None
    return dict(cycleId=str(item.retry_cycle_id) if item.retry_cycle_id else None,
        attempts=item.attempts, maxAttempts=item.max_attempts,
        startedAt=iso(item.retry_started_at), deadlineAt=iso(item.retry_deadline_at),
        nextAttemptAt=iso(item.next_attempt_at), stopRequested=item.stop_requested,
        canStop=not item.stop_requested and item.state in {'queued', 'running', 'retry_wait', 'uncertain'},
        reason=REASONS.get(item.retry_reason))
