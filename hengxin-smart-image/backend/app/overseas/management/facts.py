from datetime import datetime, timezone
from typing import Literal
from uuid import UUID
from fastapi import HTTPException, Query
from sqlalchemy import func, select
from app.overseas.execution.models import Job
from app.overseas.permissions import principal_for, task_filter
from app.overseas.pictures.models import PictureVersion
from app.overseas.tasks.models import Task


def filters(from_: datetime | None = Query(None, alias='from'),
            to: datetime | None = None, taskId: UUID | None = None,
            kind: Literal['analysis', 'reanalysis', 'generation', 'revision', 'studio'] | None = None,
            status: Literal['queued', 'running', 'collecting', 'cancelling', 'uncertain',
                            'succeeded', 'failed', 'cancelled'] | None = None):
    start = from_.replace(tzinfo=timezone.utc) if from_ and not from_.tzinfo else from_
    end = to.replace(tzinfo=timezone.utc) if to and not to.tzinfo else to
    if start and end and start > end:
        raise HTTPException(422, '开始时间不能晚于结束时间')
    clauses = []
    for column, value in ((Job.task_id, taskId), (Job.kind, kind), (Job.status, status)):
        if value is not None:
            clauses.append(column == value)
    if start:
        clauses.append(Job.created_at >= start)
    if end:
        clauses.append(Job.created_at <= end)
    return clauses


def scoped(session, actor, clauses):
    return select(Job).join(Task, Task.id == Job.task_id).where(
        task_filter(principal_for(session, actor), Task.created_by, Task.designer_id, 'stats.read'), *clauses)


def token(job, field):
    value = (job.usage or {}).get(field)
    return value if type(value) is int and value >= 0 else None


def image_counts(session, ids):
    counts = dict(session.execute(select(PictureVersion.job_id, func.count()).where(
        PictureVersion.job_id.in_(ids)).group_by(PictureVersion.job_id)).all())
    from app.overseas.studio.models import Picture, Turn
    for job_id, count in session.execute(select(Turn.job_id, func.count()).join(
            Picture, Picture.turn_id == Turn.id).where(Turn.job_id.in_(ids)).group_by(Turn.job_id)):
        counts[job_id] = counts.get(job_id, 0) + count
    return counts
