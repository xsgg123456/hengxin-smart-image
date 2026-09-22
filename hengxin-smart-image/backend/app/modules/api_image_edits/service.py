import hashlib
import json
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.models import utcnow
from .config import PARAMETERS, get_api_settings
from .files import find_file
from .models import ApiDispatch, ApiItem, ApiOperation, ApiTask
from .state import channel, event

def enabled():
    if not get_api_settings().enabled:
        raise HTTPException(503, 'API 换套图尚未启用')


def find_task(session, task_id, lock=False):
    query = select(ApiTask).where(ApiTask.id == task_id, ApiTask.deleted_at.is_(None))
    task = session.scalar(query.with_for_update() if lock else query)
    if task is None:
        raise HTTPException(404, '任务不存在')
    return task


def operation(session, user, key, payload):
    if not key or not 1 <= len(key) <= 128:
        raise HTTPException(422, '需要有效的 Idempotency-Key')
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    old = session.scalar(select(ApiOperation).where(ApiOperation.operator_id == user.id,
                                                   ApiOperation.key == key))
    if old and old.payload_hash != digest:
        raise HTTPException(409, '幂等键已用于其他请求')
    return old, digest


def submit(session, user, data, key):
    enabled()
    gate = channel(session)  # Serializes idempotency and admission independently of CLI.
    old, digest = operation(session, user, key, {'create': data.model_dump(mode='json')})
    if old:
        return old.task_id
    if gate.paused:
        raise HTTPException(409, 'API 通道已暂停，请管理员检查配置')
    for file_id in sorted(set([*data.originalFileIds, data.materialFileId]), key=str):
        find_file(session, file_id, lock=True)
    task = ApiTask(id=uuid4(), owner_id=user.id, operator_id=user.id, name=data.name,
                   prompt=data.prompt, material_id=data.materialFileId,
                   parameters=PARAMETERS.copy(), events=['任务已提交'], state='queued')
    session.add(task)
    session.flush()
    for position, source_id in enumerate(data.originalFileIds, 1):
        session.add(ApiItem(task_id=task.id, source_id=source_id, position=position))
    session.add(ApiDispatch(id=task.id))
    session.add(ApiOperation(operator_id=user.id, key=key, payload_hash=digest, task_id=task.id))
    session.commit()
    return task.id


def retry(session, user, task_id, key):
    enabled()
    gate = channel(session)
    old, digest = operation(session, user, key, {'retry': str(task_id)})
    if old:
        return old.task_id
    task = find_task(session, task_id, lock=True)
    if gate.paused or task.state not in {'failed', 'partial_failed'}:
        raise HTTPException(409, '当前任务或通道状态不能重试')
    items = session.scalars(select(ApiItem).where(ApiItem.task_id == task.id,
                                                ApiItem.state == 'failed')).all()
    for item in items:
        item.state = 'collecting' if item.result_url or item.result_bytes else 'queued'
        item.cycle_retries = item.collection_retries = 0
        item.next_attempt_at = item.error = None
    task.state, task.error, task.completed_at, task.operator_id = 'queued', None, None, user.id
    dispatch = session.get(ApiDispatch, task.id)
    dispatch.completed_at, dispatch.next_dispatch_at = None, utcnow()
    event(task, '已提交失败图片重试')
    session.add(ApiOperation(operator_id=user.id, key=key, payload_hash=digest, task_id=task.id))
    session.commit()
    return task.id


def delete_task(session, user, task_id):
    channel(session)
    task = find_task(session, task_id, lock=True)
    if task.state in {'running', 'uncertain'}:
        raise HTTPException(409, '正在运行或待核实的任务不能删除')
    task.deleted_at, task.deleted_by = utcnow(), user.id
    session.get(ApiDispatch, task.id).completed_at = utcnow()
    session.commit()
