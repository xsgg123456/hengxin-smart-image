"""Shared list filters and SQL-only aggregates for domestic task records."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import String, case, cast, func, or_, select

from app.resource_models import UserRecord
from .models import ApiItem, ApiTask

BEIJING = ZoneInfo('Asia/Shanghai')


def filtered_tasks(search, status, *, owner_id=None, date_from=None, date_to=None):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(422, '开始日期不能晚于结束日期')
    query = select(ApiTask).where(ApiTask.deleted_at.is_(None))
    if owner_id is not None:
        query = query.where(ApiTask.owner_id == owner_id)
    if search:
        query = query.where(or_(ApiTask.name.icontains(search, autoescape=True),
                               func.replace(cast(ApiTask.id, String), '-', '').icontains(
                                   search.replace('-', '') or search, autoescape=True),
                               cast(ApiTask.id, String).icontains(search, autoescape=True)))
    if status:
        query = query.where(ApiTask.state == status)
    try:
        if date_from:
            start = datetime.combine(date_from, time.min, BEIJING).astimezone(timezone.utc)
            query = query.where(ApiTask.created_at >= start)
        if date_to:
            end = (datetime.combine(date_to, time.min, BEIJING)
                   + timedelta(days=1)).astimezone(timezone.utc)
            query = query.where(ApiTask.created_at < end)
    except OverflowError:
        raise HTTPException(422, '日期超出支持范围') from None
    return query


def task_stats(session, query):
    matched = query.with_only_columns(ApiTask.id, ApiTask.state).subquery()
    tasks, pending = session.execute(select(func.count(), func.coalesce(func.sum(case(
        (matched.c.state.in_(['queued', 'running', 'uncertain']), 1), else_=0)), 0))
        .select_from(matched)).one()
    success, failed = session.execute(select(
        func.coalesce(func.sum(case((ApiItem.state == 'succeeded', 1), else_=0)), 0),
        func.coalesce(func.sum(case((ApiItem.state == 'failed', 1), else_=0)), 0),
    ).select_from(ApiItem).join(matched, ApiItem.task_id == matched.c.id)).one()
    return dict(tasks=tasks, pendingTasks=pending, successImages=success, failedImages=failed)


def list_creators(session, current_user_id):
    has_tasks = select(ApiTask.id).where(ApiTask.owner_id == UserRecord.id,
                                        ApiTask.deleted_at.is_(None)).exists()
    rows = session.execute(select(UserRecord.id, UserRecord.name).where(
        or_(UserRecord.id == current_user_id, has_tasks)).order_by(UserRecord.name, UserRecord.id))
    return {'items': [{'id': str(user_id), 'name': name} for user_id, name in rows]}
