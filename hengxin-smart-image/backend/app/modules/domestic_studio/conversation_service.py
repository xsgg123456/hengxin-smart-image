"""Creator-scoped conversation management; no mock messages or Skill defaults."""
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.exc import OperationalError

from app.core.idempotency import fingerprint_payload, lookup_request
from app.db.timestamps import utcnow
from app.modules.auth.member_policy import lock_permissions
from app.modules.auth.permissions import BUSINESS_ROLES
from app.resource_models import UserRecord
from .bindings import lock_admission
from .conversation_models import Conversation, ConversationDeletion, ConversationRequest, Workspace
from .policy import require_workspace


def lock_actor(session, actor_id):
    """Serialize with membership revocation before taking the execution gate."""
    lock_permissions(session)
    actor = session.scalar(select(UserRecord).where(UserRecord.id == actor_id)
                           .execution_options(populate_existing=True))
    if (actor is None or actor.directory_state != 'enrolled'
            or actor.status != 'active' or actor.role not in BUSINESS_ROLES):
        raise HTTPException(403, '没有操作权限')
    return actor


def owned(session, actor_id, workspace, conversation_id, *, lock=False, allow_deleting=False):
    require_workspace(workspace)
    query = select(Conversation).where(
        Conversation.id == conversation_id, Conversation.owner_id == actor_id,
        Conversation.workspace == workspace).execution_options(populate_existing=True)
    try:
        row = session.scalar(query.with_for_update(nowait=True) if lock else query)
    except OperationalError as exc:
        if getattr(exc.orig, 'sqlstate', None) == '55P03':
            raise HTTPException(409, '当前会话正在处理文件，请稍后重试') from None
        raise
    if row is None:
        raise HTTPException(404, '会话已删除或不存在')
    if not allow_deleting and session.get(ConversationDeletion, row.id) is not None:
        raise HTTPException(409, '会话正在删除或删除未完成，请重试删除')
    return row


def workspace_state(session, actor_id, workspace, *, create=False):
    require_workspace(workspace)
    row = session.get(Workspace, (actor_id, workspace), populate_existing=True)
    if row is None and create:
        # Caller holds the shared admission gate; concurrent first inserts serialize.
        row = Workspace(owner_id=actor_id, workspace=workspace, version=1)
        session.add(row)
        session.flush()
    return row


def _receipt(session, actor_id, operation, target, key, payload):
    digest = fingerprint_payload(payload)
    old = lookup_request(session, ConversationRequest, actor_id, operation, target, key, digest)
    return old, digest


def _record(session, actor_id, operation, target, key, digest, conversation_id):
    session.add(ConversationRequest(user_id=actor_id, operation=operation, target=target,
                                    key=key, body_hash=digest, conversation_id=conversation_id))
    session.flush()


def create(session, actor_id, workspace, body, key):
    """Create at most ten conversations per person and entry, transactionally."""
    require_workspace(workspace)
    lock_actor(session, actor_id)
    lock_admission(session)
    old, digest = _receipt(session, actor_id, 'create', workspace, key, body.model_dump(mode='json'))
    if old:
        return owned(session, actor_id, workspace, old.conversation_id)
    state = workspace_state(session, actor_id, workspace, create=True)
    count = session.scalar(select(func.count()).select_from(Conversation).where(
        Conversation.owner_id == actor_id, Conversation.workspace == workspace))
    if count >= 10:
        raise HTTPException(409, '每个工作台最多保留10个会话，请先删除会话后重试')
    row = Conversation(owner_id=actor_id, workspace=workspace, name=body.name or f'会话 {count + 1}')
    session.add(row)
    session.flush()
    state.version += 1
    _record(session, actor_id, 'create', workspace, key, digest, row.id)
    return row


def rename(session, actor_id, workspace, conversation_id: UUID, body, key):
    require_workspace(workspace)
    lock_actor(session, actor_id)
    lock_admission(session)
    row = owned(session, actor_id, workspace, conversation_id, lock=True)
    target = str(conversation_id)
    old, digest = _receipt(session, actor_id, 'rename', target, key, body.model_dump(mode='json'))
    if old:
        if old.conversation_id != row.id:
            raise HTTPException(409, '原请求不属于当前会话')
        return row
    if row.version != body.version:
        raise HTTPException(409, '会话已更新，请刷新后重试')
    row.name, row.version, row.updated_at = body.name, row.version + 1, utcnow()
    state = workspace_state(session, actor_id, workspace)
    if state is None:
        raise RuntimeError('Conversation workspace missing')
    state.version += 1
    _record(session, actor_id, 'rename', target, key, digest, row.id)
    return row
