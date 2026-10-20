from datetime import timedelta
import math

from sqlalchemy import select

from app.models import utcnow
from .claims import owned
from .models import ApiAttempt, ApiTask
from .state import event, refresh_task, release_item
from .retry_policy import database_now, exhausted, end_wait, retry_delay
from . import limiter


def finish_attempt(session, item, state, error=None):
    attempt = session.scalar(select(ApiAttempt).where(ApiAttempt.item_id == item.id,
                         ApiAttempt.retry_cycle_id == item.retry_cycle_id,
                         ApiAttempt.state.in_(('running', 'uncertain') if item.state == 'uncertain'
                                              else ('running',)))
                         .order_by(ApiAttempt.created_at.desc()).limit(1))
    if attempt:
        attempt.state, attempt.error, attempt.completed_at = state, error, utcnow()
        from app.modules.management.api_stats.facts import record_attempt
        record_attempt(session, item, session.get(ApiTask, item.task_id), attempt)
    return attempt


def failure(factory, item_id, token, kind, code, retry_after=None, request_id=None, retry_after_at=None):
    with factory.begin() as session:
        gate, item = owned(session, item_id, token)
        if not item:
            return
        task = session.get(ApiTask, item.task_id)
        # Codes originate exclusively from our adapter, never upstream exception text.
        item.error = code
        now = database_now(session)
        if retry_after_at:
            retry_after = max(retry_after or 0, math.ceil((retry_after_at - now).total_seconds()))
        attempt = finish_attempt(session, item, kind, code)
        if attempt:
            attempt.request_id = request_id
        # The local call has ended; retain uncertain audit, use the normal retry gate.
        limiter.outcome(gate, attempt, 'retryable' if kind == 'uncertain' else kind, now, retry_after)
        reason = exhausted(item, now)
        if reason:
            end_wait(item, reason)
        elif kind in {'retryable', 'uncertain'}:
            delay = retry_delay(item, retry_after)
            item.cycle_retries += 1
            item.state, item.retry_reason = 'retry_wait', 'retry_wait'
            item.next_attempt_at = now + timedelta(seconds=delay)
            release_item(item)
        else:
            item.state = 'failed'
            item.retry_reason = 'channel' if kind == 'channel' else 'permanent'
            release_item(item)
        if kind == 'channel':
            gate.paused, gate.reason = True, code
            if code == 'RETRY_AFTER_TOO_LONG':
                limiter.block_unrepresentable_wait(gate)
        event(task, f'第 {item.position} 张：{code}')
        refresh_task(session, task)


def save_response(factory, item_id, token, result):
    with factory.begin() as session:
        gate, item = owned(session, item_id, token)
        if not item:
            return False
        attempt = finish_attempt(session, item, 'succeeded')
        item.result_url, item.result_bytes = result.result_url, result.image_bytes
        item.state, item.error = 'collecting', None
        item.retry_reason, item.next_attempt_at = None, None
        now = database_now(session)
        # An expired/unknown request may return while still owning the token.
        from .config import get_api_settings
        item.lease_until = now + timedelta(seconds=get_api_settings().lease_seconds)
        if attempt:
            attempt.request_id = result.request_id
        limiter.outcome(gate, attempt, 'succeeded', now)
        refresh_task(session, session.get(ApiTask, item.task_id))
        return True


def collection_failure(factory, item_id, token, permanent=False):
    with factory.begin() as session:
        gate, item = owned(session, item_id, token)
        if not item:
            return
        item.error = '结果校验失败' if permanent else '结果收集失败，仅重试收图'
        task = session.get(ApiTask, item.task_id)
        if permanent or item.collection_retries >= 3:
            item.state = 'failed'
            release_item(item)
        else:
            item.next_attempt_at = database_now(session) + timedelta(seconds=2 ** item.collection_retries)
            item.collection_retries += 1
            release_item(item)
        event(task, f'第 {item.position} 张：{item.error}')
        refresh_task(session, task)


def record_return_dimensions(factory, item_id, token, width, height):
    """Record observed upstream dimensions, never invent evidence for old requests."""
    with factory.begin() as session:
        _, item = owned(session, item_id, token)
        if not item:
            return False
        attempt = session.scalar(select(ApiAttempt).where(ApiAttempt.item_id == item.id)
                                 .order_by(ApiAttempt.created_at.desc(), ApiAttempt.id).limit(1))
        if attempt and attempt.return_width is None:
            attempt.return_width, attempt.return_height = width, height
        return True
