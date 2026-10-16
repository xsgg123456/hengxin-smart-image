"""Task-wide content visibility is independent of original attachment records."""
from fastapi import HTTPException
from sqlalchemy import select
from app.overseas.materials.models import Material
from app.overseas.tasks.service import lock_actor
from .models import MaterialVisibility, Upload


def sources(task_id):
    return (
        ('task', select(Material).where(Material.task_id == task_id,
            Material.deleted_at.is_(None), Material.status == 'ready')),
        ('upload', select(Upload).where(Upload.task_id == task_id)),
    )


def visible(session, task_id):
    hidden = set(session.scalars(select(MaterialVisibility.checksum).where(
        MaterialVisibility.task_id == task_id, MaterialVisibility.hidden.is_(True))))
    seen, result = set(), []
    for source, query in sources(task_id):
        model = Material if source == 'task' else Upload
        for row in session.scalars(query.order_by(model.created_at, model.id)):
            if row.checksum not in hidden and row.checksum not in seen:
                result.append((row, source))
                seen.add(row.checksum)
    return result


def visibility(session, task_id, checksum):
    return session.scalar(select(MaterialVisibility).where(
        MaterialVisibility.task_id == task_id, MaterialVisibility.checksum == checksum))


def uploaded(session, task_id, checksum):
    """Called before inserting an upload, while holding the task row lock."""
    state = visibility(session, task_id, checksum)
    if state and state.hidden:
        state.hidden = False
        return 'restored'
    for source, query in sources(task_id):
        model = Material if source == 'task' else Upload
        if session.scalar(query.where(model.checksum == checksum).limit(1)):
            return 'existing'
    return 'added'


def remove(session, actor, task_id, identity):
    from . import queries
    actor = lock_actor(session, actor, 'task.design')
    task = queries.access(session, actor, task_id, write=True)
    if task.status != 'studio':
        raise HTTPException(409, '当前任务不能移除工作台素材')
    row, _ = queries.attachment(session, task, identity)
    state = visibility(session, task.id, row.checksum)
    if state is None:
        session.add(MaterialVisibility(task_id=task.id, checksum=row.checksum, hidden=True))
    else:
        state.hidden = True
    session.flush()
    result = queries.view(session, actor, task.id)
    session.commit()
    return result
