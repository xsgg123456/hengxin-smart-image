from fastapi import HTTPException
from sqlalchemy import select

from app.models import utcnow
from .models import ApiAttempt, ApiItem
from .service import enabled, find_task
from .state import aware, channel, event, refresh_task, release


def resume(session, user):
    enabled()
    gate = channel(session)
    if gate.item_id:
        item = session.get(ApiItem, gate.item_id)
        if item.state == 'uncertain':
            raise HTTPException(409, '请先核实状态不确定的调用')
    gate.paused, gate.reason = False, None
    session.commit()


def resolve(session, user, task_id, confirmed):
    if confirmed is not True:
        raise HTTPException(422, '必须确认旧调用已经停止')
    gate = channel(session)
    task = find_task(session, task_id, lock=True)
    item = session.get(ApiItem, gate.item_id) if gate.item_id else None
    if not item or item.task_id != task.id:
        raise HTTPException(409, '没有可核实的调用')
    if item.state == 'running' and aware(gate.lease_until) <= utcnow():
        item.state = 'uncertain'
    if item.state != 'uncertain':
        raise HTTPException(409, '仍在运行，不能强行释放通道')
    item.state, item.error = 'failed', '管理员已确认旧调用停止，可手动重试'
    attempts = session.scalars(select(ApiAttempt).where(ApiAttempt.item_id == item.id,
                               ApiAttempt.state.in_(['running', 'uncertain'])))
    for attempt in attempts:
        attempt.state, attempt.error = 'failed', item.error
        attempt.completed_at, attempt.resolved_by = utcnow(), user.id
    event(task, f'管理员 {user.id} 已确认旧调用停止')
    release(gate)
    refresh_task(session, task)
    session.commit()
