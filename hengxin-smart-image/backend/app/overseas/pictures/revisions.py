from uuid import uuid4
from fastapi import HTTPException
from app.overseas.execution.models import Job
from app.overseas.execution.queue import enqueue
from app.overseas.plans.service import complete
from .review import mutation, replay
from .queries import version


def validate_marks(body, original):
    if not body.note.strip() and not any(m.note.strip() for m in body.marks):
        raise HTTPException(422, '请填写修改意见')
    if len({m.id for m in body.marks}) != len(body.marks) or sum(len(m.points) for m in body.marks) > 10000:
        raise HTTPException(422, '标注数量或标识无效')
    for mark in body.marks:
        if (mark.x + mark.width > original.width or mark.y + mark.height > original.height
                or any(p.x > original.width or p.y > original.height for p in mark.points)
                or (mark.kind == 'pen' and len(mark.points) < 2)
                or (mark.kind == 'rect' and (mark.points or not mark.width or not mark.height))):
            raise HTTPException(422, '标注必须在原图范围内')


def revise(session, actor, picture_id, body, key):
    operation = 'picture_revision'
    actor, task, picture, digest, previous = mutation(session, actor, picture_id, body, key, operation)
    if previous:
        return replay(session, actor, task)
    original = version(session, picture)
    if not original:
        raise HTTPException(409, '图片尚未生成')
    validate_marks(body, original)
    old = session.get(Job, picture.job_id)
    frozen = {k: getattr(original, k) for k in ('bucket', 'object_key', 'name', 'content_type',
              'size_bytes', 'checksum', 'width', 'height')}
    job = enqueue(session, task.id, 'revision', f'revision:{uuid4()}', {**old.payload,
        'pictureId': str(picture.id), 'baseVersion': picture.version, 'position': picture.position,
        'original': frozen, 'note': body.note, 'marks': [m.model_dump() for m in body.marks]})
    picture.job_id, picture.approved_version = job.id, None
    task.status = 'reworking'
    return complete(session, actor, task, operation, str(picture.id), key, digest)
