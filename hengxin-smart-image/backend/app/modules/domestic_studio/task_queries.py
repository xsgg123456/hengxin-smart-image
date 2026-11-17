"""Task list and detail projections use actual conversation/execution records."""
from sqlalchemy import func, select

from app.models import Job
from app.resource_models import UserRecord
from app.worker.leases import TERMINAL
from .conversation_models import Conversation
from .queries import timestamp
from .task_models import Task
from .turn_models import Turn


def projection():
    counts = select(Conversation.task_id, func.count().label('conversation_count')).group_by(
        Conversation.task_id).subquery()
    active = select(Conversation.task_id, func.count(func.distinct(Conversation.id)).label('active_count'))\
        .join(Turn, Turn.conversation_id == Conversation.id).join(Job, Job.id == Turn.job_id)\
        .where(Job.status.not_in(TERMINAL)).group_by(Conversation.task_id).subquery()
    activity = select(Conversation.task_id, func.max(Conversation.updated_at).label('updated_at'))\
        .group_by(Conversation.task_id).subquery()
    return select(Task.id, Task.name, Task.owner_id, UserRecord.name.label('owner_name'), Task.workspace,
        Task.version, Task.completed, Task.created_at,
        func.greatest(Task.updated_at, activity.c.updated_at).label('updated_at'),
        Task.deletion_status, Task.deletion_error,
        func.coalesce(counts.c.conversation_count, 0).label('conversation_count'),
        func.coalesce(active.c.active_count, 0).label('active_count'))\
        .join(UserRecord, UserRecord.id == Task.owner_id)\
        .outerjoin(counts, counts.c.task_id == Task.id).outerjoin(active, active.c.task_id == Task.id)\
        .outerjoin(activity, activity.c.task_id == Task.id).subquery()


def dto(row):
    return dict(id=str(row.id), name=row.name, workspace=row.workspace, ownerId=str(row.owner_id),
        ownerName=row.owner_name, version=row.version, completed=row.completed,
        conversationCount=row.conversation_count, activeConversationCount=row.active_count,
        createdAt=timestamp(row.created_at), updatedAt=timestamp(row.updated_at),
        deletionStatus=row.deletion_status, deletionError=row.deletion_error)


def detail(session, identity):
    source = projection()
    return dto(session.execute(select(source).where(source.c.id == identity)).one())


def listing(session, *, owner_id=None, workspace=None, status=None, search='', page=1, page_size=20, members=False):
    source = projection()
    filters = [source.c.deletion_status.is_(None) | (source.c.deletion_status != 'deleted')]
    if owner_id:
        filters.append(source.c.owner_id == owner_id)
    if workspace:
        filters.append(source.c.workspace == workspace)
    if search.strip():
        filters.append(source.c.name.icontains(search.strip(), autoescape=True))
    counts = dict(session.execute(select(source.c.completed, func.count()).where(*filters)
                                  .group_by(source.c.completed)).all())
    if status:
        filters.append(source.c.completed.is_(status == 'completed'))
    total = counts.get(status == 'completed', 0) if status else sum(counts.values())
    rows = session.execute(select(source).where(*filters).order_by(source.c.updated_at.desc(), source.c.id.desc())
                           .offset((page - 1) * page_size).limit(page_size))
    result = dict(items=[dto(row) for row in rows], total=total, page=page, pageSize=page_size,
                  counters=dict(total=sum(counts.values()), active=counts.get(False, 0), completed=counts.get(True, 0)))
    if members:
        users = session.execute(select(UserRecord.id, UserRecord.name).join(Task, Task.owner_id == UserRecord.id)
            .where(Task.deletion_status.is_(None) | (Task.deletion_status != 'deleted'))
            .distinct().order_by(UserRecord.name, UserRecord.id))
        result['members'] = [dict(id=str(row.id), name=row.name) for row in users]
    return result
