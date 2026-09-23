"""Immutable successful versions and frozen inputs for the current edit cycle."""
from fastapi import HTTPException
from sqlalchemy import func, select

from app.models import utcnow
from .files import find_file
from .models import ApiDispatch, ApiItem, ApiOperation, ApiVersion
from .service import enabled, find_task, operation
from .state import channel, event, refresh_task


def ensure_legacy(session, item, task):
    if item.result_id and item.current_version is None:
        version = session.scalar(select(ApiVersion).where(ApiVersion.item_id == item.id,
                                                          ApiVersion.number == 1))
        if version is None:
            session.add(ApiVersion(item_id=item.id, number=1, file_id=item.result_id,
                                   operator_id=task.owner_id, text=task.prompt,
                                   created_at=item.updated_at, updated_at=item.updated_at))
        item.current_version = 1
        session.flush()


def execution_inputs(session, item, task):
    if item.revision_base_version is None:
        return None
    return (find_file(session, item.revision_source_id),
            find_file(session, item.revision_annotation_id) if item.revision_annotation_id else None,
            item.revision_text or '')


def publish_result(session, item, task, file_id):
    ensure_legacy(session, item, task)
    number = (session.scalar(select(func.max(ApiVersion.number)).where(
        ApiVersion.item_id == item.id)) or 0) + 1
    session.add(ApiVersion(item_id=item.id, number=number, file_id=file_id,
                           operator_id=item.revision_operator_id or task.owner_id,
                           text=item.revision_text if item.revision_base_version else task.prompt,
                           annotation_id=item.revision_annotation_id,
                           base_version=item.revision_base_version))
    item.result_id, item.current_version = file_id, number


def target(session, task_id, item_id):
    task = find_task(session, task_id, lock=True)
    item = session.scalar(select(ApiItem).where(ApiItem.id == item_id,
                          ApiItem.task_id == task.id).with_for_update())
    if item is None:
        raise HTTPException(404, '图片任务不存在')
    ensure_legacy(session, item, task)
    return task, item


def enqueue(session, task, item):
    if task.state not in {'queued', 'running', 'uncertain'}:
        task.state = 'queued'
    item.state = 'collecting' if item.result_url or item.result_bytes else 'queued'
    item.cycle_retries = item.collection_retries = 0
    item.next_attempt_at = item.error = None
    task.completed_at = None
    refresh_task(session, task)
    dispatch = session.get(ApiDispatch, task.id)
    if dispatch is None:
        session.add(ApiDispatch(id=task.id))
    else:
        dispatch.completed_at, dispatch.next_dispatch_at = None, utcnow()


def finish(session, user, key, digest, task, message):
    event(task, f'{user.name}：{message}')
    session.add(ApiOperation(operator_id=user.id, key=key, payload_hash=digest, task_id=task.id))
    session.commit()
    return task.id


def revise(session, user, task_id, item_id, data, key):
    enabled()
    gate = channel(session)
    old, digest = operation(session, user, key, {'revise': str(task_id), 'item': str(item_id),
                                               'data': data.model_dump(mode='json')})
    if old:
        return old.task_id
    task, item = target(session, task_id, item_id)
    if gate.paused or item.state != 'succeeded' or item.current_version != data.baseVersion:
        raise HTTPException(409, '图片版本或状态已变化，请刷新后重试')
    for file_id in sorted({item.result_id, data.annotationFileId} - {None}, key=str):
        record = find_file(session, file_id, lock=True)
        if file_id == data.annotationFileId and (record.content_type not in {'image/jpeg', 'image/png'}
                                                  or record.size_bytes > 10 * 1024 * 1024):
            raise HTTPException(422, '标注图仅支持不超过 10 MiB 的 JPG/PNG')
    item.revision_base_version, item.revision_source_id = data.baseVersion, item.result_id
    item.revision_annotation_id, item.revision_text = data.annotationFileId, data.text
    item.revision_operator_id = user.id
    item.result_url = item.result_bytes = None
    enqueue(session, task, item)
    return finish(session, user, key, digest, task, f'第 {item.position} 张已提交修改')


def retry_item(session, user, task_id, item_id, key):
    enabled()
    gate = channel(session)
    old, digest = operation(session, user, key, {'retry_item': str(task_id), 'item': str(item_id)})
    if old:
        return old.task_id
    task, item = target(session, task_id, item_id)
    if gate.paused or item.state != 'failed':
        raise HTTPException(409, '当前图片或通道状态不能重试')
    enqueue(session, task, item)
    return finish(session, user, key, digest, task, f'第 {item.position} 张已提交重试')


def restore(session, user, task_id, item_id, data, key):
    channel(session)
    old, digest = operation(session, user, key, {'restore': str(task_id), 'item': str(item_id),
                                               'version': data.version})
    if old:
        return old.task_id
    task, item = target(session, task_id, item_id)
    if item.state != 'succeeded':
        raise HTTPException(409, '图片处理中，暂不能切换版本')
    version = session.scalar(select(ApiVersion).where(ApiVersion.item_id == item.id,
                                                       ApiVersion.number == data.version))
    if version is None:
        raise HTTPException(404, '历史版本不存在')
    find_file(session, version.file_id, lock=True)
    item.result_id, item.current_version, item.state = version.file_id, version.number, 'succeeded'
    item.revision_base_version = item.revision_source_id = item.revision_annotation_id = None
    item.revision_text = item.revision_operator_id = None
    item.error = item.next_attempt_at = item.result_url = item.result_bytes = None
    refresh_task(session, task)
    return finish(session, user, key, digest, task, f'第 {item.position} 张已恢复 V{version.number}')
