from datetime import timedelta

from sqlalchemy import select

from app.models import utcnow
from .claims import owned
from .models import ApiAttempt, ApiTask
from .state import event, refresh_task, release_item


def finish_attempt(session, item, state, error=None):
    attempt = session.scalar(select(ApiAttempt).where(ApiAttempt.item_id == item.id,
                         ApiAttempt.state == 'running').order_by(ApiAttempt.created_at.desc()).limit(1))
    if attempt:
        attempt.state, attempt.error, attempt.completed_at = state, error, utcnow()


def failure(factory, item_id, token, kind, code, retry_after=None):
    with factory.begin() as session:
        gate, item = owned(session, item_id, token)
        if not item:
            return
        task = session.get(ApiTask, item.task_id)
        # Codes originate exclusively from our adapter, never upstream exception text.
        item.error = code
        finish_attempt(session, item, kind, code)
        if kind in {'retryable', 'uncertain'} and item.cycle_retries < 3:
            delay = 2 ** item.cycle_retries
            item.cycle_retries += 1
            item.state = 'retry_wait'
            item.next_attempt_at = utcnow() + timedelta(seconds=delay)
            release_item(item)
        else:
            item.state = 'failed'
            release_item(item)
            if kind == 'channel':
                gate.paused, gate.reason = True, code
        event(task, f'第 {item.position} 张：{code}')
        refresh_task(session, task)


def save_response(factory, item_id, token, result):
    with factory.begin() as session:
        gate, item = owned(session, item_id, token)
        if not item:
            return False
        item.result_url, item.result_bytes = result.result_url, result.image_bytes
        item.state, item.error = 'collecting', None
        finish_attempt(session, item, 'succeeded')
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
            item.next_attempt_at = utcnow() + timedelta(seconds=2 ** item.collection_retries)
            item.collection_retries += 1
            release_item(item)
        event(task, f'第 {item.position} 张：{item.error}')
        refresh_task(session, task)
