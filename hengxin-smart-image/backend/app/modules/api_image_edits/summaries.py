"""List-only projection: never hydrate prompts, receipts or version history."""
from sqlalchemy import case, func, select

from app.resource_models import UserRecord
from .models import ApiFile, ApiItem
from .files import picture
from .state import aware


def summaries(session, tasks):
    if not tasks:
        return []
    ids = [task.id for task in tasks]
    counts = {row.task_id: row for row in session.execute(select(
        ApiItem.task_id, func.count().label('total'),
        func.sum(case((ApiItem.state == 'succeeded', 1), else_=0)).label('success'),
        func.sum(case((ApiItem.state == 'failed', 1), else_=0)).label('failed'),
        func.sum(case((ApiItem.state == 'uncertain', 1), else_=0)).label('uncertain'),
        func.sum(case((ApiItem.state.in_(['running', 'collecting']), 1), else_=0)).label('running'),
        func.min(case((ApiItem.state.not_in(['succeeded', 'failed']), ApiItem.position))).label('first_pending'),
    ).where(ApiItem.task_id.in_(ids)).group_by(ApiItem.task_id))}
    first = select(ApiItem.task_id, func.min(ApiItem.position).label('position')).where(
        ApiItem.task_id.in_(ids)).group_by(ApiItem.task_id).subquery()
    covers = {task_id: picture(file) for task_id, file in session.execute(
        select(ApiItem.task_id, ApiFile).join(first, (ApiItem.task_id == first.c.task_id)
            & (ApiItem.position == first.c.position)).join(ApiFile, ApiFile.id == ApiItem.source_id))}
    owners = dict(session.execute(select(UserRecord.id, UserRecord.name).where(
        UserRecord.id.in_({task.owner_id for task in tasks}))).all())
    result = []
    for task in tasks:
        row = counts.get(task.id)
        total = row.total if row else 0
        batches = (total + 9) // 10
        result.append(dict(id=str(task.id), name=task.name, status=task.state,
            created=aware(task.created_at).isoformat(), operator=owners.get(task.owner_id, '未知用户'),
            cover=covers.get(task.id), counts=dict(total=total, success=row.success if row else 0,
                failed=row.failed if row else 0, uncertain=row.uncertain if row else 0),
            batch=dict(total=batches, current=(row.first_pending - 1) // 10 + 1
                if row and row.first_pending else batches, running=row.running if row else 0)))
    return result
