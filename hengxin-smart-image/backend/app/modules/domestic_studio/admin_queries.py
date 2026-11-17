"""Domestic admin projections: SQL-only reads, without Skill or admission locks."""
from sqlalchemy import case, func, select
from fastapi import HTTPException

from app.models import Job
from app.resource_models import UserRecord
from app.worker.leases import TERMINAL
from .conversation_models import Conversation, ConversationDeletion
from .policy import WORKSPACES
from .task_models import Task
from .queries import timestamp
from .turn_models import Turn

STATUSES = ('empty', 'queued', 'running', 'succeeded', 'failed', 'cancelled', 'unknown')


def readable():
    return (Conversation.workspace.in_(WORKSPACES), ~select(ConversationDeletion.conversation_id)
            .where(ConversationDeletion.conversation_id == Conversation.id).exists())


def conversation(session, identity):
    row = session.scalar(select(Conversation).where(Conversation.id == identity, *readable()))
    if row is None:
        raise HTTPException(404, '会话不存在或已删除')
    return row


def projection():
    active = Job.status.not_in(TERMINAL)
    ranked = select(Turn.conversation_id, Turn.id.label('turn_id'), Job.status,
        func.count().over(partition_by=Turn.conversation_id).label('turn_count'),
        func.max(Turn.updated_at).over(partition_by=Turn.conversation_id).label('turn_updated'),
        func.max(Job.updated_at).over(partition_by=Turn.conversation_id).label('job_updated'),
        func.row_number().over(partition_by=Turn.conversation_id,
            order_by=(case((active, 0), else_=1), Turn.created_at.desc(), Turn.id.desc())).label('rank')
        ).outerjoin(Job, Job.id == Turn.job_id).subquery()
    status = case((ranked.c.turn_id.is_(None), 'empty'),
        (ranked.c.status.in_(('uncertain', 'collecting', 'cancelling', 'retry_wait')), 'running'),
        (ranked.c.status == 'partial', 'succeeded'),
        (ranked.c.status.in_(STATUSES), ranked.c.status), else_='unknown')
    return select(Conversation.id, Conversation.task_id, Task.name.label('task_name'), Conversation.owner_id, UserRecord.name.label('owner_name'),
        Conversation.name, Conversation.workspace, Conversation.version, Conversation.created_at,
        func.greatest(Conversation.updated_at, ranked.c.turn_updated, ranked.c.job_updated).label('updated_at'),
        status.label('status'), func.coalesce(ranked.c.turn_count, 0).label('turn_count'),
        case((ranked.c.status.not_in(TERMINAL), ranked.c.turn_id), else_=None).label('active_turn_id')
        ).join(Task, Task.id == Conversation.task_id).join(UserRecord, UserRecord.id == Conversation.owner_id).outerjoin(ranked,
            (ranked.c.conversation_id == Conversation.id) & (ranked.c.rank == 1)).where(*readable()).subquery()


def dto(row):
    return dict(id=str(row.id), name=row.name, ownerId=str(row.owner_id), ownerName=row.owner_name,
        workspace=row.workspace, taskId=str(row.task_id), taskName=row.task_name, version=row.version, status=row.status, turnCount=row.turn_count,
        activeTurnId=str(row.active_turn_id) if row.active_turn_id else None,
        createdAt=timestamp(row.created_at), updatedAt=timestamp(row.updated_at))


def listing(session, *, owner_id=None, workspace=None, status=None, search='', page=1, page_size=20):
    source = projection()
    filters = []
    if owner_id:
        filters.append(source.c.owner_id == owner_id)
    if workspace:
        filters.append(source.c.workspace == workspace)
    if status:
        filters.append(source.c.status == status)
    if search.strip():
        filters.append(source.c.name.icontains(search.strip(), autoescape=True))
    counts = dict(session.execute(select(source.c.status, func.count()).where(*filters)
                                  .group_by(source.c.status)).all())
    total = sum(counts.values())
    rows = session.execute(select(source).where(*filters)
        .order_by(source.c.updated_at.desc(), source.c.id.desc()).offset((page - 1) * page_size).limit(page_size))
    members = session.execute(select(UserRecord.id, UserRecord.name).join(Conversation,
        Conversation.owner_id == UserRecord.id).where(*readable()).distinct().order_by(UserRecord.name, UserRecord.id))
    return dict(items=[dto(row) for row in rows], total=total, page=page, pageSize=page_size,
        counters={'total': total, **{key: counts.get(key, 0) for key in STATUSES}},
        members=[dict(id=str(row.id), name=row.name) for row in members])


def siblings(session, owner_id, *, task_id):
    source = projection()
    return [dto(row) for row in session.execute(select(source).where(source.c.owner_id == owner_id, source.c.task_id == task_id)
            .order_by(source.c.updated_at.desc(), source.c.id.desc()))]
