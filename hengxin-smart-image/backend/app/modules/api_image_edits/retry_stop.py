"""Idempotent stop under the same lock as the final network-send permission."""
from fastapi import HTTPException
from sqlalchemy import select

from .models import ApiAttempt, ApiOperation
from .retry_policy import end_wait
from .service import enabled, operation
from .state import channel, event, refresh_task
from .versions import target


def stop(session, user, task_id, item_id, key):
    enabled()
    channel(session)
    old, digest = operation(session, user, key, {'stop': str(task_id), 'item': str(item_id)})
    if old:
        return old.task_id
    task, item = target(session, task_id, item_id)
    if item.state not in {'queued', 'running', 'retry_wait', 'uncertain', 'collecting'} and not item.stop_requested:
        raise HTTPException(409, '本轮已经结束，无需停止')
    item.stop_requested = True
    item.retry_reason = 'user_stopped'
    inflight = session.scalar(select(ApiAttempt.id).where(ApiAttempt.item_id == item.id,
        ApiAttempt.state == 'running').limit(1))
    if not inflight and item.state != 'uncertain' and not (item.result_url or item.result_bytes):
        end_wait(item, 'user_stopped')
    # Keep leases/receipts intact. In-flight and returned results finish normally.
    event(task, f'第 {item.position} 张已停止后续重试')
    refresh_task(session, task)
    session.add(ApiOperation(operator_id=user.id, key=key, payload_hash=digest, task_id=task.id))
    session.commit()
    return task.id
