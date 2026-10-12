from fastapi import HTTPException
from sqlalchemy import select
from app.overseas.permissions import principal_for, require_task_access
from app.overseas.tasks.queries import get_task
from app.overseas.execution.models import Job
from .models import Picture, PictureVersion


def slots(session, task_id):
    return session.scalars(select(Picture).where(Picture.task_id == task_id)
                           .order_by(Picture.sku, Picture.position)).all()


def find(session, picture_id, actor):
    picture = session.get(Picture, picture_id)
    if not picture:
        raise HTTPException(404, '图片不存在')
    task = get_task(session, picture.task_id)
    require_task_access(principal_for(session, actor), task.created_by, task.designer_id)
    return picture


def version(session, picture, number=None):
    return session.scalar(select(PictureVersion).where(PictureVersion.picture_id == picture.id,
        PictureVersion.version == (picture.version if number is None else number)))


def status(session, picture):
    job = session.get(Job, picture.job_id)
    if job.status in ('failed', 'cancelled'):
        return 'failed'
    if job.status != 'succeeded':
        return 'reworking' if picture.version else 'pending'
    return 'ready' if picture.version else 'pending'


def url(picture, number):
    return f'/api/overseas/v1/pictures/{picture.id}/versions/{number}/content'


def listing(session, actor, task_id):
    task = get_task(session, task_id)
    require_task_access(principal_for(session, actor), task.created_by, task.designer_id)
    items = []
    for picture in slots(session, task.id):
        current = version(session, picture)
        history = session.scalars(select(PictureVersion).where(PictureVersion.picture_id == picture.id)
                                  .order_by(PictureVersion.version.desc())).all()
        items.append({'id': str(picture.id), 'taskId': str(task.id), 'sku': picture.sku,
            'position': picture.position, 'title': picture.title, 'version': picture.version,
            'approved': bool(picture.version and picture.approved_version == picture.version),
            'status': status(session, picture), 'url': url(picture, picture.version) if current else None,
            'width': current.width if current else None, 'height': current.height if current else None,
            'history': [{'version': v.version, 'url': url(picture, v.version), 'width': v.width,
                         'height': v.height, 'note': v.note, 'createdAt': v.created_at} for v in history]})
    return {'items': items, 'taskVersion': task.version}
