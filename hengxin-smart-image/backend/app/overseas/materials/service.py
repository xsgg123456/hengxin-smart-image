from fastapi import HTTPException
from sqlalchemy import select
from app.core.idempotency import fingerprint_payload, lookup_request
from app.db.timestamps import utcnow
from app.overseas.permissions import principal_for, require_task_access
from app.overseas.tasks.models import TaskRequest
from app.overseas.tasks.queries import detail, get_task
from app.overseas.tasks.service import lock_actor, record_change, request_record
from .models import Material, ParseVersion
from . import parsers


def find(session, material_id, *, lock=False, deleted=False):
    query = select(Material).where(Material.id == material_id).execution_options(populate_existing=True)
    record = session.scalar(query.with_for_update() if lock else query)
    if record is None or record.status != 'ready' or (record.deleted_at and not deleted):
        raise HTTPException(404, '海外资料不存在')
    return record


def owned(session, record, actor):
    if record.owner_id != actor.id:
        raise HTTPException(403, '只能操作自己的未提交资料')
    if record.task_id:
        raise HTTPException(409, '已提交资料不可修改或删除')


def readable(session, material_id, actor):
    record = find(session, material_id)
    if record.task_id:
        task = get_task(session, record.task_id)
        require_task_access(principal_for(session, actor), task.created_by, task.designer_id)
    else:
        from app.overseas.permissions import authorize_member
        authorize_member(session, actor, 'task.create')
        owned(session, record, actor)
    return record


def describe(session, record):
    versions = list(session.scalars(select(ParseVersion).where(ParseVersion.material_id == record.id)
                                   .order_by(ParseVersion.version)))
    items = [{'version': v.version, 'status': v.status, 'parserVersion': v.parser_version,
              'text': v.text, 'error': v.error, 'createdAt': v.created_at} for v in versions]
    current = next(v for v in items if v['version'] == record.version)
    return {'id': str(record.id), 'kind': record.kind, 'name': record.name,
            'sizeBytes': record.size_bytes, 'contentType': record.content_type,
            'taskId': str(record.task_id) if record.task_id else None,
            **current, 'createdAt': record.created_at, 'versions': items}


def parse_revision(session, record, data):
    try:
        text = parsers.parse_document(data, record.name)
        error, status = None, 'ready'
    except parsers.ParseError as exc:
        text, error, status = '', str(exc)[:500], 'failed'
    record.version += 1
    record.updated_at = utcnow()
    session.add(ParseVersion(material_id=record.id, version=record.version, status=status,
                            parser_version=parsers.PARSER_VERSION, text=text, error=error))
    session.flush()


def bind(session, actor, task, material_ids, *, resubmit=False):
    records = [find(session, key, lock=True) for key in sorted(material_ids, key=str)]
    if len({r.kind for r in records}) != len(records):
        raise HTTPException(422, '每种资料最多提交一份')
    for record in records:
        if not (resubmit and record.task_id == task.id):
            owned(session, record, actor)
        version = session.scalar(select(ParseVersion).where(
            ParseVersion.material_id == record.id, ParseVersion.version == record.version))
        if version is None or version.status != 'ready':
            raise HTTPException(422, '资料解析成功后才能提交')
    for record in records:
        record.task_id = task.id
    task.material_ids = [str(record.id) for record in records]
    task.requirements_approved = False
    task.status = 'pending_review'
    session.flush()


def submit(session, actor, task_id, body, key):
    actor = lock_actor(session, actor, 'task.create')
    body_hash = fingerprint_payload(body.model_dump(mode='json'))
    previous = lookup_request(session, TaskRequest, actor.id, 'materials', str(task_id), key, body_hash)
    task = get_task(session, task_id, lock=True)
    principal = principal_for(session, actor)
    if task.created_by != actor.id and 'operator_manager' not in principal.roles:
        raise HTTPException(403, '只能为本人创建的任务提交资料')
    if previous:
        result = detail(session, task.id, actor)
        session.commit()
        return result
    if task.version != body.version or task.status != 'created':
        raise HTTPException(409, '任务已修改或已提交，请刷新后重试')
    bind(session, actor, task, body.materialIds)
    task.version += 1
    task.updated_at = utcnow()
    record_change(session, task, actor, 'task.materials_submitted')
    request_record(session, actor, 'materials', str(task_id), key, body_hash, task)
    session.flush()
    result = detail(session, task.id, actor)
    session.commit()
    return result


def for_task(session, actor, task_id):
    task = get_task(session, task_id)
    require_task_access(principal_for(session, actor), task.created_by, task.designer_id)
    return [describe(session, record) for record in current_materials(session, task)]


def current_materials(session, task):
    query = select(Material).where(Material.task_id == task.id, Material.deleted_at.is_(None))
    if task.material_ids is not None:
        from uuid import UUID
        query = query.where(Material.id.in_([UUID(key) for key in task.material_ids]))
    return session.scalars(query.order_by(Material.kind)).all()
