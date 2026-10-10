"""Serialized submission and explicit version adoption for a single API image."""
from uuid import UUID, uuid4
from fastapi import HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from app.core.config import get_settings
from app.models import Job, Outbox, utcnow
from .conversation_models import Conversation, ConversationEvent, ConversationTurn
from .files import find_file, picture
from .image_prompts import build_image_prompt
from .models import ApiOperation, ApiVersion
from .service import operation
from .state import channel
from .versions import target
from app.modules.management.settings import values
from app.retention.state import describe, entry, guard, touch

ACTIVE = ('queued', 'running', 'uncertain')


class SubmitTurn(BaseModel):
    restartExpired: bool = False
    text: str = Field(min_length=1, max_length=20000)
    prompt: str | None = Field(default=None, max_length=40000)
    baseVersion: int | None = Field(default=None, ge=1)
    baseTurnId: UUID | None = None
    annotationFileId: UUID | None = None

    @model_validator(mode='after')
    def validate_base(self):
        if not self.text.strip() or (self.baseVersion is not None and self.baseTurnId is not None):
            raise ValueError('请选择一个底图并填写意见')
        return self


class AdoptTurn(BaseModel):
    expectedVersion: int = Field(ge=1)


def identity(session, item_id):
    return session.scalar(select(Conversation).where(Conversation.item_id == item_id))


def assert_idle(session, item_id):
    row = session.scalar(select(ConversationTurn.id).join(Conversation).where(
        Conversation.item_id == item_id, ConversationTurn.status.in_(ACTIVE)).limit(1))
    if row:
        raise HTTPException(409, '图片正在 CLI 修改或待核实，请先停止或处理当前轮次')


def emit(session, conversation, turn, kind='state', text=None):
    conversation.last_event_id += 1
    payload = {'id': conversation.last_event_id, 'turnId': str(turn.id), 'type': kind}
    payload.update({'text': text} if kind == 'message' else {'status': turn.status})
    session.add(ConversationEvent(conversation_id=conversation.id, turn_id=turn.id,
                                 number=conversation.last_event_id, payload=payload))


def view(session, task_id, item_id):
    _, item = target(session, task_id, item_id)
    conversation = identity(session, item.id)
    turns = session.scalars(select(ConversationTurn).where(
        ConversationTurn.conversation_id == conversation.id).order_by(
            ConversationTurn.created_at, ConversationTurn.id)).all() if conversation else []
    def image(file_id):
        return picture(find_file(session, file_id)) if file_id else None
    return {'id': str(conversation.id) if conversation else None, 'itemId': str(item.id),
            'retention': describe(session, 'api_cli', conversation.id) if conversation else None,
            'currentVersion': item.current_version,
            'lastEventId': conversation.last_event_id if conversation else 0,
            'turns': [{'id': str(t.id), 'status': t.status, 'text': t.text, 'prompt': t.prompt,
                       'baseVersion': t.base_version, 'baseTurnId': str(t.base_turn_id) if t.base_turn_id else None,
                       'baseFileId': str(t.base_file_id), 'basePicture': image(t.base_file_id),
                       'annotationFileId': str(t.annotation_id) if t.annotation_id else None,
                       'annotation': image(t.annotation_id), 'candidate': image(t.candidate_id),
                       'candidateFileId': str(t.candidate_id) if t.candidate_id else None,
                       'messages': t.messages, 'error': t.error,
                       'adoptedVersion': t.adopted_version, 'createdAt': t.created_at.isoformat()}
                      for t in turns]}


def submit(session, user, task_id, item_id, data, key):
    # Same ordering as legacy revisions; gate also serializes operation keys.
    channel(session)
    task, item = target(session, task_id, item_id)
    payload = data.model_dump(mode='json')
    if not data.restartExpired:
        payload.pop('restartExpired')  # Existing clients retain their original idempotency digest.
    old, digest = operation(session, user, key, {'cliTurn': str(item_id), 'data': payload})
    if old:
        return
    if not get_settings().enable_codex_executor:
        raise HTTPException(503, 'CLI 图片修改尚未启用')
    assert_idle(session, item.id)
    if item.state != 'succeeded' or not item.result_id:
        raise HTTPException(409, '图片当前不能修改')
    conversation = identity(session, item.id)
    if not conversation:
        conversation = Conversation(id=uuid4(), item_id=item.id, last_event_id=0)
        session.add(conversation)
        session.flush()
    retained = entry(session, 'api_cli', conversation.id)
    if retained and retained.status == 'expired' and data.baseTurnId:
        raise HTTPException(409, '历史候选已清理，请选择正式图片开启新会话')
    guard(session, 'api_cli', conversation.id, restart=data.restartExpired)
    if data.baseTurnId:
        base = session.get(ConversationTurn, data.baseTurnId)
        if not base or base.conversation_id != conversation.id or not base.candidate_id:
            raise HTTPException(422, '候选底图不存在')
        base_id, base_version = base.candidate_id, None
    else:
        base_version = data.baseVersion or item.current_version
        base = session.scalar(select(ApiVersion).where(ApiVersion.item_id == item.id,
                                                       ApiVersion.number == base_version))
        if not base:
            raise HTTPException(409, '底图版本不存在')
        base_id = base.file_id
    ids = [base_id, item.source_id, task.material_id]
    if data.annotationFileId:
        ids.append(data.annotationFileId)
    for file_id in sorted(set(ids), key=str):
        record = find_file(session, file_id, lock=True)
        if file_id == data.annotationFileId and (record.content_type not in ('image/jpeg', 'image/png')
                                                or record.size_bytes > 10 * 1024 * 1024):
            raise HTTPException(422, '标注图仅支持不超过 10 MiB 的 JPG/PNG')
    prompt, policy = build_image_prompt(data.text)
    config = values(session)
    turn_id, job_id = uuid4(), uuid4()
    session.add(Job(id=job_id, idempotency_key='api-cli:' + str(turn_id), payload_hash=digest,
                    value=str(turn_id), kind='api_cli_edit'))
    session.flush()
    turn = ConversationTurn(id=turn_id, conversation_id=conversation.id, job_id=job_id,
        operator_id=user.id, text=data.text, prompt=prompt, base_version=base_version,
        base_turn_id=data.baseTurnId, base_file_id=base_id, annotation_id=data.annotationFileId,
        status='queued', snapshot={'fileIds': [str(i) for i in ids], 'policyVersion': policy,
                                   'timeoutSeconds': config['timeoutSeconds'], 'concurrency': config['concurrency']})
    session.add(turn)
    session.flush()
    from app.modules.management.api_stats.facts import record_action
    record_action(session, task, 'cli_submission', turn.id, user.id, channel='cli')
    emit(session, conversation, turn)
    session.add(Outbox(job_id=job_id))
    touch(session, 'api_cli', conversation.id)
    session.add(ApiOperation(operator_id=user.id, key=key, payload_hash=digest, task_id=task.id))
    session.commit()


def selected(session, task_id, item_id, turn_id):
    task, item = target(session, task_id, item_id)
    conversation = identity(session, item.id)
    turn = session.get(ConversationTurn, turn_id)
    if not conversation or not turn or turn.conversation_id != conversation.id:
        raise HTTPException(404, '修改轮次不存在')
    return task, item, conversation, turn


def stop(session, task_id, item_id, turn_id):
    _, _, conversation, turn = selected(session, task_id, item_id, turn_id)
    guard(session, 'api_cli', conversation.id)
    if turn.status in ('queued', 'running', 'uncertain'):
        turn.cancel_requested = True
        if turn.status == 'uncertain':
            dispatch = session.get(Outbox, turn.job_id)
            dispatch.completed_at, dispatch.next_dispatch_at = None, utcnow()
            turn.error = '等待执行节点核实并停止原进程；缺少进程凭据时需管理员核实'
        if turn.status == 'queued':
            turn.status, turn.finished_at = 'cancelled', utcnow()
            job = session.get(Job, turn.job_id)
            job.status, job.completed_at = 'cancelled', utcnow()
            session.get(Outbox, job.id).completed_at = utcnow()
        emit(session, conversation, turn)
        touch(session, 'api_cli', conversation.id)
    session.commit()


def adopt(session, user, task_id, item_id, turn_id, data, key):
    channel(session)
    task, item, conversation, turn = selected(session, task_id, item_id, turn_id)
    old, digest = operation(session, user, key, {'adopt': str(turn_id), 'version': data.expectedVersion})
    if old:
        return
    guard(session, 'api_cli', conversation.id)
    assert_idle(session, item.id)
    if (item.state != 'succeeded' or item.current_version != data.expectedVersion
            or turn.status != 'candidate' or not turn.candidate_id):
        raise HTTPException(409, '图片版本或候选状态已变化，请刷新后重试')
    find_file(session, turn.candidate_id, lock=True)
    number = (session.scalar(select(func.max(ApiVersion.number)).where(ApiVersion.item_id == item.id)) or 0) + 1
    version = ApiVersion(item_id=item.id, number=number, file_id=turn.candidate_id,
        operator_id=user.id, kind='image_edit', text=turn.text, annotation_id=turn.annotation_id,
        base_version=turn.base_version)
    session.add(version)
    session.flush()
    from app.modules.management.api_stats.facts import record_action
    record_action(session, task, 'adopt', version.id, user.id, channel='cli')
    item.result_id, item.current_version = turn.candidate_id, number
    item.revision_base_version = item.revision_source_id = item.revision_annotation_id = None
    item.revision_text = item.revision_operator_id = item.revision_snapshot = None
    item.error = item.next_attempt_at = item.result_url = item.result_bytes = None
    turn.status, turn.adopted_version = 'adopted', number
    from app.modules.management.api_stats.facts import record_turn
    record_turn(session, task, turn)
    emit(session, conversation, turn)
    touch(session, 'api_cli', conversation.id)
    session.add(ApiOperation(operator_id=user.id, key=key, payload_hash=digest, task_id=task.id))
    session.commit()
