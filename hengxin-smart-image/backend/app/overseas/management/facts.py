from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from fastapi import HTTPException, Query
from sqlalchemy import String, cast, func, or_, select
from app.overseas.execution.models import Job
from app.overseas.auth.models import Member
from app.overseas.studio.models import Turn
from app.overseas.permissions import principal_for, task_filter
from app.overseas.pictures.models import PictureVersion
from app.overseas.tasks.models import Task


def filters(from_: datetime | None = Query(None, alias='from'),
            to: datetime | None = None, before: datetime | None = None, taskId: UUID | None = None, memberId: UUID | None = None,
            kind: Literal['analysis', 'reanalysis', 'generation', 'revision', 'studio'] | None = None,
            status: Literal['queued', 'running', 'collecting', 'cancelling', 'uncertain',
                            'succeeded', 'failed', 'cancelled'] | None = None,
            statusGroup: Literal['queued', 'running', 'uncertain', 'succeeded', 'failed', 'cancelled'] | None = None,
            search: str = Query('', max_length=100)):
    def utc(value):
        return (value.replace(tzinfo=timezone.utc) if not value.tzinfo else value.astimezone(timezone.utc)) if value else None
    start, end, limit = utc(from_), utc(to), utc(before)
    if start and end and start > end:
        raise HTTPException(422, '开始时间不能晚于结束时间')
    if start and limit and start >= limit:
        raise HTTPException(422, '开始时间不能晚于结束时间')
    clauses = []
    for column, value in ((Job.task_id, taskId), (Job.kind, kind), (Job.status, status),
                          (Turn.actor_id, memberId)):
        if value is not None:
            clauses.append(column == value)
    if start:
        clauses.append(Job.created_at >= start)
    if end:
        clauses.append(Job.created_at <= end)
    if limit:
        clauses.append(Job.created_at < limit)
    if statusGroup:
        clauses.append(Job.status.in_(('running', 'collecting', 'cancelling')) if statusGroup == 'running'
                       else Job.status == statusGroup)
    if search.strip():
        term = search.strip()
        normalized = term.replace('-', '')
        clauses.append(or_(Task.name.icontains(term, autoescape=True),
            func.replace(cast(Task.id, String), '-', '').icontains(normalized, autoescape=True))
            if normalized else Task.name.icontains(term, autoescape=True))
    return clauses


def scoped(session, actor, clauses):
    return select(Job).join(Task, Task.id == Job.task_id).outerjoin(Turn, Turn.job_id == Job.id).where(
        task_filter(principal_for(session, actor), Task.created_by, Task.designer_id, 'stats.read'), *clauses)


def operators(session, actor):
    rows = session.execute(scoped(session, actor, []).join(Member, Member.id == Turn.actor_id)
        .with_only_columns(Member.id, Member.name).distinct().order_by(Member.name, Member.id))
    return {'items': [{'id': str(identity), 'name': name} for identity, name in rows]}


def image_counts(session, ids):
    counts = dict(session.execute(select(PictureVersion.job_id, func.count()).where(
        PictureVersion.job_id.in_(ids)).group_by(PictureVersion.job_id)).all())
    from app.overseas.studio.models import Picture, Turn
    for job_id, count in session.execute(select(Turn.job_id, func.count()).join(
            Picture, Picture.turn_id == Turn.id).where(Turn.job_id.in_(ids)).group_by(Turn.job_id)):
        counts[job_id] = counts.get(job_id, 0) + count
    return counts
