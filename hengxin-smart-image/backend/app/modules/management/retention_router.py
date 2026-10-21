from datetime import date
from typing import Literal
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select
from app.models import utcnow
from app.modules.auth.dependencies import CurrentUser
from .settings_router import Database
from app.retention.queries import filtered, serialize
from app.retention.summary import summary
from app.contracts.retention import Result, RetentionPage, RetentionRow, RetentionSummary

router = APIRouter(prefix='/management/retention', tags=['management'])


def authorize(user):
    if user.role not in ('super_admin', 'design_manager'):
        raise HTTPException(403, '仅超级管理员和设计主管可查看自动清理')


@router.get('/summary', response_model=RetentionSummary)
def get_summary(user: CurrentUser, session: Database):
    authorize(user)
    return summary(session, utcnow())


@router.get('/records', response_model=RetentionPage)
def records(user: CurrentUser, session: Database, tab: Literal['history', 'pending'] = 'history',
            keyword: str | None = Query(None, max_length=200), kind: Literal['cache', 'history'] | None = None,
            result: Result | None = None, dateFrom: date | None = None, dateTo: date | None = None,
            page: int = Query(1, ge=1), pageSize: int = Query(20, ge=1, le=100)):
    authorize(user)
    if dateFrom and dateTo and dateFrom > dateTo:
        raise HTTPException(422, '开始日期不得晚于结束日期')
    if dateTo == date.max:
        raise HTTPException(422, '结束日期超出支持范围')
    query, rows, timestamp = filtered(session, tab, utcnow(), keyword, kind, result, dateFrom, dateTo)
    total = session.scalar(select(func.count()).select_from(query.subquery()))
    results = session.execute(query.order_by(timestamp.desc().nulls_last(), rows.c.id.desc())
                              .offset((page - 1) * pageSize).limit(pageSize)).mappings()
    return dict(items=[serialize(row) for row in results], total=total, page=page, pageSize=pageSize)


@router.get('/records/{identifier}', response_model=RetentionRow)
def detail(identifier: UUID, user: CurrentUser, session: Database, tab: Literal['history', 'pending'] = 'history'):
    authorize(user)
    query, rows, _ = filtered(session, tab, utcnow())
    row = session.execute(query.where(rows.c.id == identifier)).mappings().first()
    if row is None:
        raise HTTPException(404, '清理记录不存在')
    return serialize(row)
