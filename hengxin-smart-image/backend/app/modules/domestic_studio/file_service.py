"""Conversation-owned uploads; private URLs never expose another member's files."""
from hashlib import sha256
from io import BytesIO
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select

from app.core.config import get_settings
from app.overseas.studio.files import MAX_BYTES, read, validate_stream
from . import maintenance_lock
from .conversation_models import Conversation, ConversationDeletion
from .conversation_service import lock_actor, owned
from .turn_models import OutputFile, Picture, Turn, Upload


def asset(row, workspace):
    return dict(id='upload:' + str(row.id), name=row.name, contentType=row.content_type,
                sizeBytes=row.size_bytes, source='upload',
                url=f'/api/v1/domestic-studio/workspaces/{workspace}/files/{row.id}/content')


def authorize_upload(factory, actor_id, workspace, conversation_id):
    with factory.begin() as session:
        lock_actor(session, actor_id)
        owned(session, actor_id, workspace, conversation_id)


def upload(factory, store, actor_id, workspace, conversation_id, data, filename):
    authorize_upload(factory, actor_id, workspace, conversation_id)
    stream = BytesIO(data) if isinstance(data, bytes) else data
    stream.seek(0)
    digest, size = sha256(), 0
    while chunk := stream.read(1024 * 1024):
        size += len(chunk)
        if size > MAX_BYTES:
            raise HTTPException(413, '单个附件不能超过 500 MB')
        digest.update(chunk)
    stream.seek(0)
    name, content_type = validate_stream(stream, size, filename)
    stream.seek(0)
    settings = get_settings()
    # The shared OS lock persists through database disconnects and is also held
    # by native deletion. No global permission or admission lock spans storage I/O.
    with maintenance_lock.hold(settings, conversation_id):
        # Commit the write intent before sending bytes. If this process dies,
        # deletion must not assume an absent object means the remote PUT ended.
        with factory.begin() as session:
            lock_actor(session, actor_id)
            channel = owned(session, actor_id, workspace, conversation_id, lock=True)
            identity = uuid4()
            row = Upload(id=identity, conversation_id=channel.id, name=name, content_type=content_type,
                size_bytes=size, checksum=digest.hexdigest(), bucket=settings.minio_bucket,
                object_key=f'domestic-studio/uploads/{actor_id}/{workspace}/{channel.id}/{identity}',
                status='uploading')
            session.add(row)
            session.flush()
        with factory.begin() as session:
            channel = owned(session, actor_id, workspace, conversation_id, lock=True)
            row = session.get(Upload, identity)
            if row is None or row.status != 'uploading':
                raise HTTPException(409, '附件状态异常，请重试')
            try:
                store.put_stream(row, stream, size)
            except Exception:
                raise HTTPException(503, '附件存储失败，请重试') from None
            lock_actor(session, actor_id)
            if session.get(ConversationDeletion, channel.id):
                raise HTTPException(409, '会话正在删除，不能上传附件')
            row.status = 'ready'
            session.flush()
            return asset(row, workspace)


def find(session, actor_id, workspace, identity):
    row = session.scalar(select(Upload).join(Conversation, Conversation.id == Upload.conversation_id).where(
        Upload.id == identity, Upload.status == 'ready', Conversation.owner_id == actor_id, Conversation.workspace == workspace,
        ~select(ConversationDeletion.conversation_id).where(
            ConversationDeletion.conversation_id == Conversation.id).exists()))
    if row is None:
        raise HTTPException(404, '附件不存在或不可访问')
    return row


def bytes_for_owner(session, store, actor_id, workspace, identity):
    return read(store, find(session, actor_id, workspace, identity))


def find_output(session, actor_id, workspace, identity, *, picture=False):
    model = Picture if picture else OutputFile
    row = session.scalar(select(model).join(Turn, Turn.id == model.turn_id)
        .join(Conversation, Conversation.id == Turn.conversation_id).where(
            model.id == identity, Conversation.owner_id == actor_id, Conversation.workspace == workspace,
            ~select(ConversationDeletion.conversation_id).where(
                ConversationDeletion.conversation_id == Conversation.id).exists()))
    if row is None:
        raise HTTPException(404, '文件不存在或不可访问')
    return row
