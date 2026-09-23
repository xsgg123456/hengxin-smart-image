from datetime import timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.models import utcnow
from .models import ApiChannel, ApiDispatch, ApiItem

ACTIVE = {'queued', 'running', 'retry_wait', 'collecting', 'uncertain'}


def aware(value):
    return value.replace(tzinfo=timezone.utc) if value and value.tzinfo is None else value


def channel(session):
    row = session.scalar(select(ApiChannel).where(ApiChannel.id == 1).with_for_update())
    if row is None:
        try:
            with session.begin_nested():
                session.add(ApiChannel(id=1, paused=False))
                session.flush()
        except IntegrityError:
            pass
        row = session.scalar(select(ApiChannel).where(ApiChannel.id == 1).with_for_update())
    return row


def event(task, message):
    task.events = [*task.events, message][-100:]


def refresh_task(session, task):
    session.flush()
    states = list(session.scalars(select(ApiItem.state).where(ApiItem.task_id == task.id)))
    if 'uncertain' in states:
        task.state = 'uncertain'
    elif any(state in ACTIVE for state in states):
        task.state = 'running' if task.state in {'running', 'uncertain'} else 'queued'
    else:
        task.state = ('succeeded' if all(s == 'succeeded' for s in states)
                      else 'partial_failed' if 'succeeded' in states else 'failed')
        task.completed_at = utcnow()
        dispatch = session.get(ApiDispatch, task.id)
        if dispatch:
            dispatch.completed_at = utcnow()
    task.error = ('有请求状态不确定，请联系超级管理员核实' if task.state == 'uncertain'
                  else '部分图片处理失败' if 'failed' in states else None)


def release(gate):
    gate.item_id = gate.token = gate.lease_until = None


def release_item(item):
    item.lease_token = item.lease_until = None
