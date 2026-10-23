"""Task-wide content visibility is independent of original attachment records."""
from fastapi import HTTPException
from sqlalchemy import select, or_
from app.overseas.materials.models import Material
from app.overseas.tasks.service import lock_actor
from .models import MaterialVisibility, Upload


def sources(task_id, conversation_id=None):
    return (
        ('task', select(Material).where(Material.task_id == task_id,
            Material.deleted_at.is_(None), Material.status == 'ready')),
        ('upload', select(Upload).where(Upload.task_id == task_id,
            or_(Upload.conversation_id.is_(None), Upload.conversation_id == conversation_id)
            if conversation_id else True)),
    )


def visible(session, task_id, conversation_id=None):
    states = session.scalars(select(MaterialVisibility).where(
        MaterialVisibility.task_id == task_id, MaterialVisibility.scope.in_(['', str(conversation_id)])))
    inherited, local = {}, {}
    for state in states:
        (local if state.scope else inherited)[state.checksum] = state.hidden
    hidden = {checksum for checksum, value in {**inherited, **local}.items() if value}
    seen, result = set(), []
    for source, query in sources(task_id, conversation_id):
        model = Material if source == 'task' else Upload
        for row in session.scalars(query.order_by(model.created_at, model.id)):
            if row.checksum not in hidden and row.checksum not in seen:
                result.append((row, source))
                seen.add(row.checksum)
    return result


def visibility(session, task_id, checksum, scope=''):
    return session.scalar(select(MaterialVisibility).where(
        MaterialVisibility.task_id == task_id, MaterialVisibility.checksum == checksum, MaterialVisibility.scope == scope))


def uploaded(session, task_id, checksum, conversation_id=None):
    """Called before inserting an upload, while holding the task row lock."""
    state = visibility(session, task_id, checksum, str(conversation_id) if conversation_id else '')
    inherited = visibility(session, task_id, checksum) if conversation_id and state is None else None
    if inherited and inherited.hidden:
        session.add(MaterialVisibility(task_id=task_id, checksum=checksum, scope=str(conversation_id), hidden=False))
        return 'restored'
    if state and state.hidden:
        state.hidden = False
        return 'restored'
    for source, query in sources(task_id, conversation_id):
        model = Material if source == 'task' else Upload
        if session.scalar(query.where(model.checksum == checksum).limit(1)):
            return 'existing'
    return 'added'


def remove(session, actor, task_id, identity, conversation_id=None):
    from . import queries
    actor = lock_actor(session, actor, 'task.design')
    task = queries.access(session, actor, task_id, write=True)
    if task.status != 'studio':
        raise HTTPException(409, '当前任务不能移除工作台素材')
    if conversation_id is not None:
        queries.conversation(session, task.id, conversation_id, writable=True)
    row, _ = queries.attachment(session, task, identity, conversation_id)
    scope = str(conversation_id) if conversation_id else ''
    state = visibility(session, task.id, row.checksum, scope)
    if state is None:
        session.add(MaterialVisibility(task_id=task.id, checksum=row.checksum, scope=scope, hidden=True))
    else:
        state.hidden = True
    session.flush()
    result = queries.view(session, actor, task.id, conversation_id)
    session.commit()
    return result
