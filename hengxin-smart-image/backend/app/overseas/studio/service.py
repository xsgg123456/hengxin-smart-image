from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from app.core.idempotency import fingerprint_payload, lookup_request
from app.db.timestamps import utcnow
from app.overseas.tasks.models import TaskRequest, TaskSku
from app.overseas.tasks.service import lock_actor, request_record, record_change
from app.overseas.execution.models import Job, TERMINAL
from app.overseas.execution.queue import enqueue, lock_gate
from app.overseas.management.settings import freeze_selected
from app.overseas.archives.models import Archive
from .models import Conversation, Turn
from . import queries
from .image_edits import freeze_edits, message_text


def mutate(session, actor, task_id, body, key, operation, expected_status='studio'):
    actor = lock_actor(session, actor, 'task.design')
    task = queries.access(session, actor, task_id, write=True)
    payload = body.model_dump(mode='json')
    if payload.get('imageEdits') == []:
        payload.pop('imageEdits')  # Preserve fingerprints recorded before image edits existed.
    for field in ('conversationId', 'name'):
        if payload.get(field) is None:
            payload.pop(field, None)
    digest = fingerprint_payload(payload)
    previous = lookup_request(session, TaskRequest, actor.id, operation, str(task_id), key, digest)
    if not previous:
        if task.status != expected_status or not task.requirements_approved:
            raise HTTPException(409, '任务状态已变化或尚未审核通过，请刷新后重试')
        if 'version' in payload and task.version != body.version:
            raise HTTPException(409, '任务已更新，请刷新后重试')
    return actor, task, digest, previous


def active(session, task, conversation_id=None):
    lock_gate(session)
    query = select(Job.id).where(Job.task_id == task.id, Job.status.not_in(TERMINAL))
    if conversation_id is not None:
        query = query.join(Turn, Turn.job_id == Job.id).where(Turn.conversation_id == conversation_id)
    return session.scalar(query.limit(1))


def finish(session, actor, task, key, digest, operation, conversation_id=None):
    task.updated_at = utcnow()
    request_record(session, actor, operation, str(task.id), key, digest, task).conversation_id = conversation_id
    session.flush()
    return replay(session, actor, task, conversation_id)


def replay(session, actor, task, conversation_id=None):
    result = queries.view(session, actor, task.id, conversation_id)
    session.commit()
    return result


def send(session, actor, task_id, body, key, conversation_hint=None):
    actor, task, digest, previous = mutate(session, actor, task_id, body, key, 'studio_send')
    if body.conversationId and conversation_hint and body.conversationId != conversation_hint:
        raise HTTPException(409, '请求会话与核实会话不一致，请核实原请求')
    channel_id = body.conversationId or conversation_hint
    # A routing hint must never change the historical body fingerprint. Check
    # ownership/deletion even on replay, before binding old unscoped receipts.
    if channel_id:
        queries.conversation(session, task.id, channel_id)
    if previous:
        if channel_id and previous.conversation_id and previous.conversation_id != channel_id:
            raise HTTPException(409, '原请求属于其他会话，请核实原请求')
        if previous.conversation_id is None and channel_id:
            previous.conversation_id = channel_id
        return replay(session, actor, task, previous.conversation_id or channel_id)
    channel = (queries.conversation(session, task.id, channel_id, writable=True)
               if channel_id else queries.current_conversation(session, task.id))
    if channel is None:
        from .conversations import create
        channel = create(session, task)
    else:
        queries.conversation(session, task.id, channel.id, writable=True)
    if active(session, task, channel.id):
        raise HTTPException(409, '当前会话轮次尚未结束，请等待或停止执行')
    attachments = [queries.attachment(session, task, value, channel.id)[0] for value in body.attachmentIds]
    references = [queries.picture(session, task, value, channel.id) for value in body.referencePictureIds]
    edits = freeze_edits(body, attachments, references)
    channel.updated_at = utcnow()
    channel.version += 1
    frozen = freeze_selected(session, body.skillId)
    turn_id = uuid4()
    inputs = [dict(id=str(row.id), name=row.name, bucket=row.bucket, object_key=row.object_key,
                   content_type=row.content_type, size_bytes=row.size_bytes, checksum=row.checksum)
              for row in attachments + references]
    job = enqueue(session, task.id, 'studio', f'studio:{turn_id}', {
        **frozen, 'turnId': str(turn_id), 'conversationId': str(channel.id),
        'text': body.text, 'inputs': inputs, 'imageEdits': edits})
    skill = frozen.get('skill')
    session.add(Turn(id=turn_id, task_id=task.id, conversation_id=channel.id, job_id=job.id,
        actor_id=actor.id, text=message_text(body, references), skill_name=skill.get('displayName', skill['name']) if skill else None,
        attachment_ids=body.attachmentIds, reference_ids=[str(v) for v in body.referencePictureIds]))
    return finish(session, actor, task, key, digest, 'studio_send', channel.id)


def new_conversation(session, actor, task_id, body, key):
    actor, task, digest, previous = mutate(session, actor, task_id, body, key, 'studio_conversation')
    if previous:
        return replay(session, actor, task, previous.conversation_id)
    from .conversations import create
    channel = create(session, task, body.name)
    return finish(session, actor, task, key, digest, 'studio_conversation', channel.id)


def cancel(session, actor, task_id, turn_id, version):
    task = queries.access(session, actor, task_id)
    turn = session.get(Turn, turn_id)
    if not turn or turn.task_id != task.id:
        raise HTTPException(404, '轮次不存在')
    from app.overseas.execution.cancel import cancel as cancel_job
    cancel_job(session, actor, turn.job_id, version)
    return queries.view(session, actor, task.id, turn.conversation_id)


def archive(session, actor, task_id, body, key, store):
    actor, task, digest, previous = mutate(session, actor, task_id, body, key, 'studio_archive')
    if previous:
        return replay(session, actor, task, previous.conversation_id or body.conversationId)
    sku = session.scalar(select(TaskSku).where(TaskSku.task_id == task.id, TaskSku.code == body.sku))
    if not sku:
        raise HTTPException(422, '请选择本任务的SKU')
    pictures = [queries.picture(session, task, value, body.conversationId) for value in set(body.pictureIds)]
    if any(picture.turn_id is None for picture in pictures):
        raise HTTPException(404, '历史引用图片不属于当前会话交付，不能重新归档')
    origins = {session.get(Turn, picture.turn_id).conversation_id for picture in pictures}
    if len(origins) != 1:
        raise HTTPException(422, '每次只能归档同一会话的图片')
    channel_id = next(iter(origins))
    queries.conversation(session, task.id, channel_id, writable=True)
    if any(p.sku is not None and p.sku != sku.code for p in pictures):
        raise HTTPException(409, '图片已经归档到其他SKU')
    record = session.scalar(select(Archive).where(Archive.task_id == task.id).with_for_update())
    if record is None:
        record = Archive(task_id=task.id, versions=[])
        session.add(record)
    from app.overseas.archives.deletion import available
    available(session, record.id)
    had_versions = bool(record.versions)
    versions = list(record.versions)
    for picture in pictures:
        picture.sku = sku.code
        identity = 'studio:' + str(picture.id)
        if identity not in versions:
            versions.append(identity)
    record.versions = versions
    from app.overseas.archives.snapshot import protect
    session.flush()
    protect(session, store, record, task)
    from app.overseas.archives.audit import record_confirmation
    record_confirmation(session, record, actor, ['studio:' + str(p.id) for p in pictures], had_versions)
    return finish(session, actor, task, key, digest, 'studio_archive', channel_id)


def complete(session, actor, task_id, body, key):
    actor, task, digest, previous = mutate(session, actor, task_id, body, key, 'studio_complete')
    if previous:
        return replay(session, actor, task)
    if active(session, task):
        raise HTTPException(409, '请等待所有执行结束后再完成任务')
    from .models import ConversationDeletion
    if session.scalar(select(ConversationDeletion.conversation_id).where(
            ConversationDeletion.task_id == task.id, ConversationDeletion.status != 'deleted').limit(1)):
        raise HTTPException(409, '请完成会话删除或重试清理后再完成任务')
    if queries.available_archive(session, task.id, lock=True) is None:
        raise HTTPException(409, '请先归档至少一张有效图片；归档不存在或正在删除时不能完成任务')
    task.status = 'completed'
    task.version += 1
    record_change(session, task, actor, 'task.studio_completed')
    return finish(session, actor, task, key, digest, 'studio_complete')


def reopen(session, actor, task_id, body, key):
    actor, task, digest, previous = mutate(session, actor, task_id, body, key,
        'studio_reopen', expected_status='completed')
    if previous:
        return replay(session, actor, task)
    if active(session, task):
        raise HTTPException(409, '请等待所有执行结束后再解冻工作台')
    task.status = 'studio'
    task.version += 1
    record_change(session, task, actor, 'task.studio_reopened')
    return finish(session, actor, task, key, digest, 'studio_reopen')
