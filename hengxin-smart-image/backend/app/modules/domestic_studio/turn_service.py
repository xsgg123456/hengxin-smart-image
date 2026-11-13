"""Freeze a trusted Skill and conversation inputs in the enqueue transaction."""
from uuid import UUID, uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.db.timestamps import utcnow
from app.models import Job, Outbox
from app.modules.management.settings import values
from app.overseas.studio.image_edits import freeze_edits, message_text
from app.worker.leases import TERMINAL
from .bindings import lock_admission
from .conversation_service import _receipt, _record, lock_actor, owned, workspace_state
from .skill_references import JOB_KIND, freeze_and_pin
from .turn_models import Picture, Turn, Upload


def upload(session, conversation_id, identity):
    try:
        prefix, value = identity.split(':', 1)
        file_id = UUID(value)
        if prefix != 'upload':
            raise ValueError()
    except (ValueError, AttributeError):
        raise HTTPException(422, '附件编号无效') from None
    row = session.scalar(select(Upload).where(Upload.id == file_id,
                                               Upload.conversation_id == conversation_id, Upload.status == 'ready'))
    if row is None:
        raise HTTPException(404, '附件不存在或不属于当前会话')
    return row


def picture(session, conversation_id, identity):
    row = session.scalar(select(Picture).join(Turn, Turn.id == Picture.turn_id).where(
        Picture.id == identity, Turn.conversation_id == conversation_id))
    if row is None:
        raise HTTPException(404, '图片不存在或不属于当前会话')
    return row


def send(session, actor_id, workspace, conversation_id, body, key, catalog):
    lock_actor(session, actor_id)
    lock_admission(session)
    channel = owned(session, actor_id, workspace, conversation_id, lock=True)
    if body.conversationId is not None and body.conversationId != channel.id:
        raise HTTPException(409, '请求会话与当前会话不一致')
    if body.skillId is not None:
        raise HTTPException(422, '当前工作台自动使用已绑定的 Skill')
    old, digest = _receipt(session, actor_id, 'send', str(channel.id), key, body.model_dump(mode='json'))
    if old:
        if old.conversation_id != channel.id:
            raise HTTPException(409, '原请求不属于当前会话')
        return channel
    if not get_settings().enable_codex_executor:
        raise HTTPException(503, 'AI 工作台暂不可用，请联系管理员')
    active = session.scalar(select(Turn.id).join(Job, Job.id == Turn.job_id).where(
        Turn.conversation_id == channel.id, Job.status.not_in(TERMINAL)).limit(1))
    if active:
        raise HTTPException(409, '当前会话轮次尚未结束，请等待或停止执行')
    attachments = [upload(session, channel.id, identity) for identity in body.attachmentIds]
    references = [picture(session, channel.id, identity) for identity in body.referencePictureIds]
    edits = freeze_edits(body, attachments, references)
    inputs = [dict(id=str(row.id), name=row.name, bucket=row.bucket, object_key=row.object_key,
                   content_type=row.content_type, size_bytes=row.size_bytes, checksum=row.checksum)
              for row in attachments + references]
    turn_id, job_id = uuid4(), uuid4()
    job = Job(id=job_id, kind=JOB_KIND, idempotency_key='domestic-studio:' + str(turn_id),
              payload_hash=digest, value=str(turn_id), status='queued')
    session.add(job)
    session.flush()
    frozen = freeze_and_pin(session, job, workspace, catalog)
    config = values(session)
    snapshot = {**frozen, 'turnId': str(turn_id), 'conversationId': str(channel.id),
                'text': body.text, 'inputs': inputs, 'imageEdits': edits,
                'attachmentIds': body.attachmentIds,
                'referencePictureIds': [str(value) for value in body.referencePictureIds],
                'timeoutSeconds': config['timeoutSeconds'], 'concurrency': config['concurrency']}
    turn = Turn(id=turn_id, conversation_id=channel.id, job_id=job.id, actor_id=actor_id,
                text=message_text(body, references), snapshot=snapshot)
    session.add_all((turn, Outbox(job_id=job.id)))
    channel.version += 1
    state = workspace_state(session, actor_id, workspace)
    if state is None:
        raise RuntimeError('Conversation workspace missing')
    state.version += 1
    _record(session, actor_id, 'send', str(channel.id), key, digest, channel.id)
    return channel


def cancel(session, actor_id, workspace, conversation_id, turn_id, version):
    from .runtime import changed, finish, locked

    lock_actor(session, actor_id)
    lock_admission(session)
    owned(session, actor_id, workspace, conversation_id, lock=True)
    identity = session.scalar(select(Turn.job_id).where(Turn.id == turn_id,
                                                          Turn.conversation_id == conversation_id))
    if identity is None:
        raise HTTPException(404, '轮次不存在')
    state, channel, turn, job = locked(session, identity)
    if job is None:
        raise HTTPException(404, '轮次不存在')
    if turn.version != version:
        raise HTTPException(409, '轮次已更新，请刷新后重试')
    if job.status == 'queued':
        turn.cancel_requested = True
        finish(session, state, channel, turn, job, 'cancelled')
    elif job.status in ('running', 'collecting', 'uncertain') and not turn.cancel_requested:
        turn.cancel_requested = True
        if job.status == 'uncertain':
            outbox = session.get(Outbox, job.id)
            if outbox is None:
                raise RuntimeError('Domestic Studio outbox missing')
            outbox.completed_at, outbox.next_dispatch_at = None, utcnow()
        changed(state, channel, turn)
    return channel


def request_recovery(session, actor_id, workspace, conversation_id, turn_id, version):
    """Ask the owning worker to verify exit evidence and re-collect files only."""
    from .runtime import changed, locked

    lock_actor(session, actor_id)
    lock_admission(session)
    owned(session, actor_id, workspace, conversation_id, lock=True)
    identity = session.scalar(select(Turn.job_id).where(Turn.id == turn_id,
                                                          Turn.conversation_id == conversation_id))
    if identity is None:
        raise HTTPException(404, '轮次不存在')
    state, channel, turn, job = locked(session, identity)
    if job is None:
        raise HTTPException(404, '轮次不存在')
    if job.status != 'uncertain' or turn.cancel_requested or not turn.dispatched or not turn.process_identity:
        raise HTTPException(409, '当前轮次没有可核实的收取请求')
    if turn.recovery_requested:
        return channel
    if turn.version != version:
        raise HTTPException(409, '轮次已更新，请刷新后重试')
    outbox = session.get(Outbox, job.id)
    if outbox is None:
        raise RuntimeError('Domestic Studio outbox missing')
    turn.recovery_requested = True
    turn.error = '等待原执行节点核实并收取文件，不会重新生成'
    outbox.completed_at, outbox.next_dispatch_at = None, utcnow()
    changed(state, channel, turn)
    return channel
