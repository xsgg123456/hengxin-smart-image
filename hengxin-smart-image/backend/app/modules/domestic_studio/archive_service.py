"""Snapshot a creator-owned conversation into independent shared archive bytes."""
import json
from hashlib import sha256
from types import SimpleNamespace
from uuid import NAMESPACE_URL, UUID, uuid5

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select

from app.core.idempotency import fingerprint_payload, lookup_request
from app.models import Job
from app.overseas.studio.files import verify
from app.worker.leases import TERMINAL
from .archive_models import Archive, ArchiveDeletion, ArchiveFile, ArchiveRequest
from . import archive_edits
from .bindings import lock_admission
from .conversation_service import lock_actor, owned
from .policy import require_archive_workspace
from .queries import timestamp
from .turn_models import OutputFile, Picture, Transcript, Turn
from .turn_service import picture, upload


class ArchiveInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    productName: str = Field(min_length=1, max_length=60)

    @field_validator('productName')
    @classmethod
    def valid_name(cls, value):
        value = value.strip()
        if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
            raise ValueError('请输入 1–60 个字的产品名称')
        return value


def archive_key(record, identity):
    return (f'domestic-studio/archives/{record.owner_id}/{record.workspace}/'
            f'{record.source_conversation_id}/{record.id}/{identity}')


def plan_asset(session, record, kind, source, position):
    identity = uuid5(record.id, kind + ':' + str(source.id))
    existing = session.get(ArchiveFile, identity)
    if existing is not None:
        return existing
    row = ArchiveFile(id=identity, archive_id=record.id, kind=kind, source_id=source.id,
        position=position, name=source.name, content_type=source.content_type,
        size_bytes=source.size_bytes, checksum=source.checksum, bucket=source.bucket,
        source_bucket=source.bucket, source_object_key=source.object_key, status='pending',
        object_key=archive_key(record, identity),
        width=getattr(source, 'width', None), height=getattr(source, 'height', None))
    session.add(row)
    session.flush()
    return row


def file_dto(row):
    return dict(id=str(row.id), kind=row.kind, name=row.name, contentType=row.content_type,
        sizeBytes=row.size_bytes, width=row.width, height=row.height,
        url=f'/api/v1/domestic-studio/archives/{row.archive_id}/files/{row.id}/content')


def manifest_entry(row):
    return dict(file=file_dto(row), sourceId=str(row.source_id), checksum=row.checksum,
                bucket=row.bucket, objectKey=row.object_key, sourceBucket=row.source_bucket,
                sourceObjectKey=row.source_object_key, position=row.position)


def seal(snapshot):
    raw = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8')
    return sha256(raw).hexdigest()


def verify_snapshot(record, rows):
    """Check the frozen list and every reference before trusting archived copies."""
    snapshot = record.snapshot
    if not isinstance(snapshot, dict) or set(snapshot) != {'turns', 'files', 'checksum'}:
        raise ValueError('Invalid archive snapshot')
    body = {'turns': snapshot['turns'], 'files': snapshot['files']}
    if seal(body) != snapshot['checksum'] or not isinstance(body['turns'], list) or not isinstance(body['files'], list):
        raise ValueError('Archive snapshot checksum mismatch')
    ordered = sorted(rows, key=lambda row: (row.position, str(row.id)))
    if (body['files'] != [manifest_entry(row) for row in ordered]
            or any(row.status != 'ready' or row.archive_id != record.id
                   or row.object_key != archive_key(record, row.id) for row in ordered)):
        raise ValueError('Archive file manifest mismatch')
    available = {str(row.id): row for row in ordered}
    referenced = set()
    for turn in body['turns']:
        if not isinstance(turn, dict):
            raise ValueError('Invalid archive turn')
        if turn.get('status') is not None and turn['status'] not in TERMINAL:
            raise ValueError('Invalid archived turn status')
        if turn.get('error') is not None and not isinstance(turn['error'], str):
            raise ValueError('Invalid archived turn error')
        transcript = turn.get('transcript', [])
        if not isinstance(transcript, list):
            raise ValueError('Invalid archived transcript')
        for entry in transcript:
            if (not isinstance(entry, dict) or entry.get('kind') not in ('message', 'reasoning', 'tool', 'notice')
                    or entry.get('state') not in ('running', 'completed', 'failed')
                    or not isinstance(entry.get('text'), str)
                    or (entry.get('itemId') is not None and not isinstance(entry['itemId'], str))
                    or (entry.get('createdAt') is not None and not isinstance(entry['createdAt'], str))):
                raise ValueError('Invalid archived transcript entry')
        for field, kind in (('attachments', 'upload'), ('pictures', 'picture'),
                            ('referencePictures', 'picture'), ('outputs', 'output')):
            values = turn.get(field)
            if not isinstance(values, list):
                raise ValueError('Invalid archive references')
            for value in values:
                row = available.get(value.get('id')) if isinstance(value, dict) else None
                if row is None or row.kind != kind or value != file_dto(row):
                    raise ValueError('Archive reference mismatch')
                referenced.add(str(row.id))
        archive_edits.validate(turn.get('imageEdits', []), turn['attachments'],
                               turn['referencePictures'], turn.get('text', ''))
    if referenced != set(available):
        raise ValueError('Archive file reference set mismatch')


def prepare(session, actor_id, workspace, conversation_id, body, key):
    require_archive_workspace(workspace)
    actor = lock_actor(session, actor_id)
    lock_admission(session)
    digest = fingerprint_payload(body.model_dump(mode='json'))
    previous = lookup_request(session, ArchiveRequest, actor_id, 'archive', str(conversation_id), key, digest)
    if previous:
        record = session.get(Archive, previous.archive_id)
        if (record is None or record.owner_id != actor_id or record.workspace != workspace
                or record.source_conversation_id != conversation_id or session.get(ArchiveDeletion, record.id)):
            raise HTTPException(409, '原归档已删除或不可用，请重新发起归档')
        return record
    channel = owned(session, actor_id, workspace, conversation_id, lock=True)
    pending = list(session.scalars(select(Archive).where(
        Archive.owner_id == actor_id, Archive.workspace == workspace,
        Archive.source_conversation_id == channel.id, Archive.status.in_(('preparing', 'copy_failed')))))
    if len(pending) > 1:
        raise HTTPException(409, '会话存在多条未完成归档，请联系管理员处理')
    if pending:
        record = pending[0]
        if record.product_name != body.productName:
            raise HTTPException(409, f'请先使用原产品名称「{record.product_name}」重试未完成的归档')
        session.add(ArchiveRequest(user_id=actor_id, operation='archive', target=str(channel.id), key=key,
                                   body_hash=digest, archive_id=record.id))
        session.flush()
        return record
    active = session.scalar(select(Turn.id).join(Job, Job.id == Turn.job_id).where(
        Turn.conversation_id == channel.id, Job.status.not_in(TERMINAL)).limit(1))
    turns = list(session.scalars(select(Turn).where(Turn.conversation_id == channel.id)
                                 .order_by(Turn.created_at, Turn.id)))
    if active or not any((turn.reply or '').strip() for turn in turns):
        raise HTTPException(409, '请等待本轮回复完成后归档')
    token = json.dumps([str(actor_id), workspace, str(channel.id), key], ensure_ascii=False, separators=(',', ':'))
    record = Archive(id=uuid5(NAMESPACE_URL, 'hengxin:domestic:archive:' + token), owner_id=actor_id,
        workspace=workspace, source_conversation_id=channel.id, source_conversation_name=channel.name,
        product_name=body.productName, snapshot={}, status='preparing')
    if session.get(Archive, record.id) is not None:
        raise HTTPException(409, '归档标识冲突，请使用新请求重试')
    session.add(record)
    session.flush()
    entries, copied = [], {}

    def save(kind, source):
        key = kind, source.id
        if key not in copied:
            copied[key] = plan_asset(session, record, kind, source, len(copied))
        return file_dto(copied[key])

    for turn in turns:
        if turn.actor_id != actor_id:
            raise HTTPException(503, '会话资料校验失败，原会话已保留')
        job = session.get(Job, turn.job_id)
        if job is None or job.status not in TERMINAL:
            raise HTTPException(503, '会话执行状态校验失败，原会话已保留')
        attachments = [save('upload', upload(session, channel.id, identity))
                       for identity in turn.snapshot.get('attachmentIds', [])]
        references = [save('picture', picture(session, channel.id, UUID(identity)))
                      for identity in turn.snapshot.get('referencePictureIds', [])]
        try:
            edits = archive_edits.copy(turn.snapshot, attachments, references, turn.text)
        except (KeyError, TypeError, ValueError):
            raise HTTPException(503, '会话修改资料校验失败，原会话已保留') from None
        pictures = [save('picture', row) for row in session.scalars(select(Picture).where(Picture.turn_id == turn.id)
                                                                      .order_by(Picture.created_at, Picture.id))]
        outputs = [save('output', row) for row in session.scalars(select(OutputFile).where(OutputFile.turn_id == turn.id)
                                                                    .order_by(OutputFile.created_at, OutputFile.id))]
        messages = list(session.scalars(select(Transcript).where(Transcript.turn_id == turn.id)
                                       .order_by(Transcript.id)))
        last_reply = next((row for row in reversed(messages) if row.kind == 'message' and row.text == turn.reply), None)
        reply_time = last_reply.created_at if last_reply else turn.finished_at if turn.reply else None
        event_ids = {}
        for row in messages:
            if row.item_id not in event_ids:
                event_ids[row.item_id] = 'event-' + str(len(event_ids) + 1)
        entries.append(dict(id=str(uuid5(record.id, 'turn:' + str(turn.id))), text=turn.text,
            actorName=actor.name, createdAt=timestamp(turn.created_at), reply=turn.reply, status=job.status,
            error=turn.error or job.error,
            replyAt=timestamp(reply_time), attachments=attachments, referencePictures=references,
            imageEdits=edits, pictures=pictures, outputs=outputs,
            transcript=[dict(itemId=event_ids[row.item_id], kind=row.kind, text=row.text, state=row.state, createdAt=timestamp(row.created_at))
                        for row in messages]))
    snapshot = {'turns': entries, 'files': [manifest_entry(row) for row in
                                           sorted(copied.values(), key=lambda row: (row.position, str(row.id)))]}
    record.snapshot = {**snapshot, 'checksum': seal(snapshot)}
    session.add(ArchiveRequest(user_id=actor_id, operation='archive', target=str(channel.id), key=key,
                               body_hash=digest, archive_id=record.id))
    session.flush()
    return record


def complete(factory, store, archive_id, actor_id):
    """A committed manifest proves ownership even if copying is interrupted."""
    try:
        with factory.begin() as session:
            lock_actor(session, actor_id)
        # Keep the archive's own row locked during copying, but release the
        # shared permission/admission locks before potentially large storage I/O.
        with factory.begin() as session:
            record = session.scalar(select(Archive).where(Archive.id == archive_id).with_for_update())
            if (record is None or record.owner_id != actor_id
                    or session.get(ArchiveDeletion, archive_id) is not None):
                raise HTTPException(404, '归档不存在或正在删除')
            if record.status not in ('preparing', 'copy_failed', 'ready'):
                raise ValueError('Invalid archive copy status')
            if record.status == 'ready':
                return
            rows = list(session.scalars(select(ArchiveFile).where(ArchiveFile.archive_id == record.id)
                                        .order_by(ArchiveFile.position, ArchiveFile.id)))
            for row in rows:
                if row.status not in ('pending', 'uploading', 'ready'):
                    raise ValueError('Invalid archive file status')
                if row.status == 'ready':
                    verify(store, row)
                    continue
                if row.status == 'pending':
                    source = SimpleNamespace(bucket=row.source_bucket, object_key=row.source_object_key,
                                             size_bytes=row.size_bytes, checksum=row.checksum)
                    verify(store, source)
                    stream = store.open(source)
                    try:
                        # Commit before issuing the only PUT for this key. A timed-out
                        # PUT can still arrive after its caller and lock disappear.
                        with factory.begin() as intent_session:
                            intent = intent_session.get(ArchiveFile, row.id, with_for_update=True)
                            if intent is None or intent.archive_id != archive_id or intent.status != 'pending':
                                raise ValueError('Archive copy intent changed')
                            intent.status = 'uploading'
                        store.put_stream(row, stream, row.size_bytes)
                    finally:
                        try:
                            stream.close()
                        finally:
                            stream.release_conn()
                # An existing intent may only be completed by observing the
                # original PUT, never by issuing another write for the same key.
                verify(store, row)
                row.status = 'ready'
        # Authorization and publication are checked together after all copies
        # have committed. NOWAIT keeps a concurrent copy from blocking the gate.
        with factory.begin() as session:
            lock_actor(session, actor_id)
            lock_admission(session)
            record = session.scalar(select(Archive).where(Archive.id == archive_id).with_for_update(nowait=True))
            if (record is None or record.owner_id != actor_id
                    or session.get(ArchiveDeletion, archive_id) is not None):
                raise HTTPException(404, '归档不存在或正在删除')
            if record.status not in ('preparing', 'copy_failed', 'ready'):
                raise ValueError('Invalid archive copy status')
            if session.scalar(select(ArchiveFile.id).where(ArchiveFile.archive_id == archive_id,
                                                            ArchiveFile.status != 'ready').limit(1)):
                raise ValueError('Archive copy incomplete')
            verify_snapshot(record, list(session.scalars(select(ArchiveFile).where(
                ArchiveFile.archive_id == archive_id))))
            record.status, record.error = 'ready', None
    except HTTPException as error:
        if error.status_code in (403, 404):
            raise
        _copy_failed(factory, archive_id)
        raise HTTPException(503, '归档文件复制或校验失败，原会话已保留，请重试') from None
    except Exception:
        _copy_failed(factory, archive_id)
        raise HTTPException(503, '归档文件复制或校验失败，原会话已保留，请重试') from None


def _copy_failed(factory, archive_id):
    with factory.begin() as session:
        record = session.scalar(select(Archive).where(Archive.id == archive_id).with_for_update())
        if record is not None and record.status != 'ready':
            record.status, record.error = 'copy_failed', '归档文件复制或校验失败，原会话已保留'
