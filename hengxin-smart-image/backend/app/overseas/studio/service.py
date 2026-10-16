from uuid import uuid4
from fastapi import HTTPException
from sqlalchemy import select
from app.core.idempotency import fingerprint_payload, lookup_request
from app.db.timestamps import utcnow
from app.overseas.tasks.models import TaskRequest, TaskSku
from app.overseas.tasks.service import lock_actor, request_record
from app.overseas.execution.models import Job, TERMINAL
from app.overseas.execution.queue import enqueue, lock_gate
from app.overseas.management.settings import freeze_selected
from app.overseas.archives.models import Archive
from .models import Conversation, Turn
from . import queries
from .image_edits import freeze_edits, message_text


def mutate(session, actor, task_id, body, key, operation):
    actor = lock_actor(session, actor, 'task.design')
    task = queries.access(session, actor, task_id, write=True)
    payload = body.model_dump(mode='json')
    if payload.get('imageEdits') == []:
        payload.pop('imageEdits')  # Preserve fingerprints recorded before image edits existed.
    digest = fingerprint_payload(payload)
    previous = lookup_request(session, TaskRequest, actor.id, operation, str(task_id), key, digest)
    if not previous and (task.status != 'studio' or not task.requirements_approved):
        raise HTTPException(409, '任务尚未进入工作台或已经完成')
    return actor, task, digest, previous


def active(session, task):
    lock_gate(session)
    return session.scalar(select(Job.id).where(Job.task_id == task.id,
        Job.status.not_in(TERMINAL)).limit(1))


def finish(session, actor, task, key, digest, operation):
    task.updated_at = utcnow()
    request_record(session, actor, operation, str(task.id), key, digest, task)
    session.flush()
    return replay(session, actor, task)


def replay(session, actor, task):
    result = queries.view(session, actor, task.id)
    session.commit()
    return result


def send(session, actor, task_id, body, key):
    actor, task, digest, previous = mutate(session, actor, task_id, body, key, 'studio_send')
    if previous:
        return replay(session, actor, task)
    if active(session, task):
        raise HTTPException(409, '当前轮次尚未结束，请等待或停止执行')
    attachments = [queries.attachment(session, task, value)[0] for value in body.attachmentIds]
    references = [queries.picture(session, task, value) for value in body.referencePictureIds]
    edits = freeze_edits(body, attachments, references)
    channel = queries.current_conversation(session, task.id)
    if channel is None:
        channel = Conversation(task_id=task.id)
        session.add(channel)
        session.flush()
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
    return finish(session, actor, task, key, digest, 'studio_send')


def new_conversation(session, actor, task_id, body, key):
    actor, task, digest, previous = mutate(session, actor, task_id, body, key, 'studio_conversation')
    if previous:
        return replay(session, actor, task)
    if active(session, task):
        raise HTTPException(409, '当前轮次尚未结束，请等待或停止执行')
    session.add(Conversation(task_id=task.id))
    return finish(session, actor, task, key, digest, 'studio_conversation')


def cancel(session, actor, task_id, turn_id, version):
    task = queries.access(session, actor, task_id)
    turn = session.get(Turn, turn_id)
    if not turn or turn.task_id != task.id:
        raise HTTPException(404, '轮次不存在')
    from app.overseas.execution.cancel import cancel as cancel_job
    cancel_job(session, actor, turn.job_id, version)
    return queries.view(session, actor, task.id)


def archive(session, actor, task_id, body, key, store):
    actor, task, digest, previous = mutate(session, actor, task_id, body, key, 'studio_archive')
    if previous:
        return replay(session, actor, task)
    sku = session.scalar(select(TaskSku).where(TaskSku.task_id == task.id, TaskSku.code == body.sku))
    if not sku:
        raise HTTPException(422, '请选择本任务的SKU')
    pictures = [queries.picture(session, task, value) for value in set(body.pictureIds)]
    if any(p.sku is not None and p.sku != sku.code for p in pictures):
        raise HTTPException(409, '图片已经归档到其他SKU')
    record = session.scalar(select(Archive).where(Archive.task_id == task.id))
    if record is None:
        record = Archive(task_id=task.id, versions=[])
        session.add(record)
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
    return finish(session, actor, task, key, digest, 'studio_archive')


def complete(session, actor, task_id, body, key):
    actor, task, digest, previous = mutate(session, actor, task_id, body, key, 'studio_complete')
    if previous:
        return replay(session, actor, task)
    if active(session, task):
        raise HTTPException(409, '请等待所有执行结束后再完成任务')
    record = session.scalar(select(Archive).where(Archive.task_id == task.id))
    if record is None or not record.versions:
        raise HTTPException(409, '请先归档至少一张图片')
    task.status = 'completed'
    task.version += 1
    return finish(session, actor, task, key, digest, 'studio_complete')
