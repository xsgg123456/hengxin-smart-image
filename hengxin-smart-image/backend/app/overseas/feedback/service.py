from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.orm import undefer

from app.db.timestamps import utcnow
from app.overseas.auth.dependencies import member_roles
from app.overseas.members.service import get_member, lock_permissions
from app.overseas.permissions import authorize_member, can_manage_feedback
from .models import Feedback


def describe(item, management=False):
    data = {field: getattr(item, field) for field in (
        'id', 'submitter_id', 'submitter_name', 'question', 'source', 'task_name', 'sku',
        'status', 'public_reply', 'version', 'created_at', 'updated_at')}
    data['screenshot_url'] = (
        f'/api/overseas/v1/feedback/{item.id}/screenshot' if item.screenshot_type else None)
    if management:
        data['internal_note'] = item.internal_note
    return data


def create(session, actor_id, fields, image):
    actor = get_member(session, actor_id)
    member_roles(session, actor)
    item = Feedback(submitter_id=actor.id, submitter_name=actor.name,
                    question=fields.question, source=fields.source, task_name=fields.task_name or None,
                    sku=fields.sku or None, screenshot_type=image.content_type if image else None,
                    screenshot=image.data if image else None)
    session.add(item)
    session.flush()
    result = describe(item)
    session.commit()
    return result


def listing(session, actor, offset, limit, *, management=False, status=None):
    query = select(Feedback)
    if management:
        counts = dict.fromkeys(('pending', 'processing', 'resolved'), 0)
        counts.update(session.execute(select(Feedback.status, func.count()).group_by(Feedback.status)).all())
        total = counts[status] if status else sum(counts.values())
        query = query.options(undefer(Feedback.internal_note))
        if status:
            query = query.where(Feedback.status == status)
    else:
        query = query.where(Feedback.submitter_id == actor.id)
        total = session.scalar(select(func.count()).select_from(Feedback).where(Feedback.submitter_id == actor.id))
    rows = session.scalars(query.order_by(Feedback.created_at.desc(), Feedback.id.desc()).offset(offset).limit(limit))
    result = {'items': [describe(row, management) for row in rows], 'total': total}
    if management:
        result['counts'] = counts
    return result


def get(session, identifier):
    item = session.get(Feedback, identifier)
    if item is None:
        raise HTTPException(404, '反馈不存在')
    return item


def screenshot(session, actor, identifier):
    query = select(Feedback.screenshot, Feedback.screenshot_type).where(
        Feedback.id == identifier, Feedback.screenshot_type.is_not(None))
    if not can_manage_feedback(session, actor):
        query = query.where(Feedback.submitter_id == actor.id)
    image = session.execute(query).one_or_none()
    if image is None:
        raise HTTPException(404, '截图不存在')
    return image


def change(session, actor, identifier, body):
    lock_permissions(session)
    authorize_member(session, get_member(session, actor.id), 'feedback.manage')
    item = get(session, identifier)
    stale = HTTPException(409, '反馈已被更新，请刷新后再处理')
    if item.version != body.version:
        raise stale
    changes = body.model_dump(exclude_unset=True, exclude={'version'})
    if changes.get('status', item.status) == 'resolved' and not changes.get('public_reply', item.public_reply):
        raise HTTPException(422, '完成反馈前请填写给用户的回复')
    changed = session.execute(update(Feedback).where(Feedback.id == identifier, Feedback.version == body.version)
                              .values(**changes, version=body.version + 1, updated_at=utcnow()))
    if changed.rowcount != 1:
        raise stale
    result = describe(item, management=True)
    session.commit()
    return result
