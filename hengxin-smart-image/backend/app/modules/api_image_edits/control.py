from fastapi import HTTPException
from sqlalchemy import select

from app.models import utcnow
from .models import ApiAttempt, ApiItem
from .service import enabled, find_task
from .state import aware, channel, event, refresh_task, release_item
from .claims import adopt_legacy


def resume(session, user):
    enabled()
    gate = channel(session)
    adopt_legacy(session, gate)
    if session.scalar(select(ApiItem.id).where(ApiItem.state == 'uncertain').limit(1)):
        raise HTTPException(409, '请先核实状态不确定的调用')
    gate.paused, gate.reason = False, None
    session.commit()


def resolve(session, user, task_id, confirmed):
    if confirmed is not True:
        raise HTTPException(422, '必须确认旧调用已经停止')
    gate = channel(session)
    adopt_legacy(session, gate)
    task = find_task(session, task_id, lock=True)
    items = session.scalars(select(ApiItem).where(ApiItem.task_id == task.id)).all()
    unresolved = [item for item in items if item.state == 'uncertain' or
                  (item.state == 'running' and (not item.lease_until or aware(item.lease_until) <= utcnow()))]
    if not unresolved:
        raise HTTPException(409, '没有可核实的调用；仍在运行的图片不能强行释放')
    for item in unresolved:
        item.state, item.error = 'failed', '管理员已确认旧调用停止，可手动重试'
        attempts = session.scalars(select(ApiAttempt).where(ApiAttempt.item_id == item.id,
                                   ApiAttempt.state.in_(['running', 'uncertain'])))
        for attempt in attempts:
            attempt.state, attempt.error = 'failed', item.error
            attempt.completed_at, attempt.resolved_by = utcnow(), user.id
        release_item(item)
    event(task, f'管理员 {user.name} 已确认 {len(unresolved)} 张图片的旧调用停止')
    refresh_task(session, task)
    session.commit()
