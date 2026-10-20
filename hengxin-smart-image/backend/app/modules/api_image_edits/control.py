from fastapi import HTTPException
from sqlalchemy import select

from app.models import utcnow
from .models import ApiAttempt, ApiItem
from .service import enabled, find_task
from .state import aware, channel, event, refresh_task, release_item
from .claims import adopt_legacy
from .retry_policy import database_now, inherit_legacy


def resume(session, user):
    enabled()
    gate = channel(session)
    adopt_legacy(session, gate)
    gate.paused, gate.reason = False, None
    session.commit()


def resolve(session, user, task_id, confirmed):
    if confirmed is not True:
        raise HTTPException(422, '必须确认旧调用已经停止')
    gate = channel(session)
    adopt_legacy(session, gate)
    task = find_task(session, task_id, lock=True)
    items = session.scalars(select(ApiItem).where(ApiItem.task_id == task.id)).all()
    now = database_now(session)
    unresolved = [item for item in items if item.state == 'uncertain' or
                  (item.state == 'running' and (not item.lease_until or aware(item.lease_until) <= now))]
    if not unresolved:
        raise HTTPException(409, '没有可核实的调用；仍在运行的图片不能强行释放')
    for item in unresolved:
        inherit_legacy(session, item)
        item.state, item.error = 'failed', '管理员已确认旧调用停止，可手动重试'
        attempts = session.scalars(select(ApiAttempt).where(ApiAttempt.item_id == item.id,
                                   ApiAttempt.retry_cycle_id == item.retry_cycle_id,
                                   ApiAttempt.state.in_(['running', 'uncertain'])))
        for attempt in attempts:
            if gate.probe_attempt_id == attempt.id:
                from .limiter import cool
                cool(gate, database_now(session))
            attempt.state, attempt.error = 'failed', item.error
            attempt.completed_at, attempt.resolved_by = utcnow(), user.id
            from app.modules.management.api_stats.facts import record_attempt
            record_attempt(session, item, task, attempt)
        release_item(item)
        item.retry_reason = None
    event(task, f'管理员 {user.name} 已确认 {len(unresolved)} 张图片的旧调用停止')
    refresh_task(session, task)
    session.commit()
