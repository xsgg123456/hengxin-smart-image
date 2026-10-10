"""Read-only reporting over retained facts plus unbackfilled source history."""
from collections import defaultdict
from datetime import date, datetime, timezone
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.contracts import api_usage as c
from app.db.session import get_session
from app.modules.auth.dependencies import CurrentUser
from app.modules.api_image_edits.models import ApiItem, ApiTask
from app.modules.management.api_usage_summary import summarize
from app.resource_models import UserRecord

router = APIRouter(tags=['management'])
SHANGHAI = ZoneInfo('Asia/Shanghai')


def utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def parse_day(value: str | None) -> date | None:
    if value is None:
        return None
    try:
        result = date.fromisoformat(value)
        if result.isoformat() == value:
            return result
    except ValueError:
        pass
    raise HTTPException(422, '日期必须为 YYYY-MM-DD')


def inventory(session: Session, owner: UUID | None) -> c.Inventory:
    statement = select(ApiTask).where(ApiTask.deleted_at.is_(None))
    if owner is not None:
        statement = statement.where(ApiTask.owner_id == owner)
    tasks = session.scalars(statement).all()
    items = session.scalars(select(ApiItem).where(ApiItem.task_id.in_([t.id for t in tasks]))).all() if tasks else []
    succeeded = sum(i.state == 'succeeded' for i in items)
    failed = sum(i.state == 'failed' for i in items)
    pending = sum(i.state in ('queued', 'running', 'retry_wait', 'collecting') for i in items)
    known = succeeded + failed
    return c.Inventory(tasks=len(tasks), sourceImages=len(items),
        withResultImages=sum(i.result_id is not None for i in items),
        succeededImages=succeeded, failedImages=failed, pendingImages=pending,
        uncertainImages=len(items) - succeeded - failed - pending,
        deliverySuccessRate=succeeded / known if known else None)


def event(fact: dict, names: dict, deleted: set) -> c.Event:
    start, end = utc(fact['occurred_at']), fact['completed_at']
    end = utc(end) if end else None
    return c.Event(id=fact['key'], category=fact['category'], channel=fact['channel'], kind=fact['kind'],
        taskId=str(fact['task_id']), taskName=fact['task_name'], taskDeleted=fact['task_id'] in deleted,
        creatorId=str(fact['owner_id']), operatorId=str(fact['operator_id']) if fact['operator_id'] else None,
        operatorName=names.get(fact['operator_id'], '未知操作者'), occurredAt=start.isoformat(),
        completedAt=end.isoformat() if end else None, state=fact['state'], quantity=fact['quantity'],
        isRetry=fact['is_retry'], attribution=fact['attribution'],
        durationSeconds=max(0, (end - start).total_seconds()) if end else None)


def build_report(session: Session, user: UserRecord, query: c.UsageQuery) -> c.Report:
    from app.modules.management.api_stats.projection import read_facts

    start, end = parse_day(query.from_), parse_day(query.to)
    if start and end and start > end:
        raise HTTPException(422, '开始日期不能晚于结束日期')
    all_scope = user.role in ('super_admin', 'design_manager')
    if query.unassigned and (not all_scope or query.userId):
        raise HTTPException(403 if not all_scope else 422, '未知操作者筛选仅支持全员范围，不能同时选择人员')
    try:
        selected = UUID(query.userId) if query.userId else None
    except ValueError as error:
        raise HTTPException(422, '统计人员 ID 无效') from error
    if not all_scope and selected is not None and selected != user.id:
        raise HTTPException(403, '只能查看个人统计')
    owner = selected if all_scope else user.id
    users = session.scalars(select(UserRecord).order_by(UserRecord.name, UserRecord.id)).all()
    names = {u.id: u.name for u in users}
    facts = []
    groups = defaultdict(list)
    for fact in read_facts(session):
        actor = fact['operator_id']
        day = utc(fact['occurred_at']).astimezone(SHANGHAI).date()
        if (owner is not None and actor != owner) or (query.unassigned and actor is not None):
            continue
        if (start and day < start) or (end and day > end):
            continue
        if query.category and fact['category'] != query.category:
            continue
        facts.append(fact)
        groups[(day.isoformat(), str(actor) if actor else '')].append(fact)
    facts.sort(key=lambda f: (utc(f['occurred_at']), f['key']), reverse=True)
    rows = [c.DailyRow(date=day, userId=actor or None,
        userName=names.get(UUID(actor) if actor else None, '未知操作者'), summary=summarize(entries))
        for (day, actor), entries in sorted(groups.items(), reverse=True)]
    offset = (query.page - 1) * query.pageSize
    page = facts[offset:offset + query.pageSize]
    ids = {f['task_id'] for f in page}
    visible = set(session.scalars(select(ApiTask.id).where(ApiTask.id.in_(ids), ApiTask.deleted_at.is_(None)))) if ids else set()
    return c.Report(scope='all' if all_scope else 'personal',
        users=[c.UserOption(id=str(u.id), name=u.name) for u in users if all_scope or u.id == user.id],
        inventory=inventory(session, owner), summary=summarize(facts), rows=rows,
        events=[event(f, names, ids - visible) for f in page], total=len(facts), page=query.page, pageSize=query.pageSize)


@router.get('/management/api-usage', response_model=c.Report)
def usage(query: Annotated[c.UsageQuery, Query()], user: CurrentUser, session: Session = Depends(get_session)):
    return build_report(session, user, query)
