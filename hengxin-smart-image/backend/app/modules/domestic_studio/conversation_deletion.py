"""Durable requests and owner checks for deleting private conversations."""
from fastapi import HTTPException
from sqlalchemy import select

from app.models import Job
from app.worker.leases import TERMINAL
from .archive_models import Archive, ArchiveDeletion
from .bindings import lock_admission
from .conversation_models import ConversationDeletion
from .conversation_service import lock_actor, owned, workspace_state
from .turn_models import Turn


def request(session, actor_id, workspace, identity, version):
    lock_actor(session, actor_id)
    lock_admission(session)
    receipt = session.get(ConversationDeletion, identity)
    if receipt and (receipt.owner_id != actor_id or receipt.workspace != workspace):
        raise HTTPException(404, '会话不存在')
    if receipt and receipt.status == 'deleted':
        return {'conversationId': str(identity), 'status': 'deleted'}
    if receipt and receipt.status == 'deleting':
        return {'conversationId': str(identity), 'status': 'deleting'}
    channel = owned(session, actor_id, workspace, identity, lock=True, allow_deleting=True)
    if receipt:
        if receipt.status == 'delete_failed':
            receipt.status, receipt.error = 'deleting', None
        elif receipt.status != 'deleting':
            raise HTTPException(409, '会话删除状态异常，请联系管理员')
    else:
        if channel.version != version:
            raise HTTPException(409, '会话已更新，请刷新后重试')
        active = session.scalar(select(Turn.id).join(Job, Job.id == Turn.job_id).where(
            Turn.conversation_id == identity, Job.status.not_in(TERMINAL)).limit(1))
        if active:
            raise HTTPException(409, '请先停止当前会话的执行，再删除会话')
        pending = session.scalar(select(Archive.id).where(Archive.source_conversation_id == identity,
            Archive.status != 'ready').limit(1))
        if pending:
            raise HTTPException(409, '此会话有尚未完成的归档，请先重试归档')
        deleting_archive = session.scalar(select(ArchiveDeletion.archive_id).join(
            Archive, Archive.id == ArchiveDeletion.archive_id).where(
            Archive.source_conversation_id == identity, ArchiveDeletion.status != 'deleted').limit(1))
        if deleting_archive:
            raise HTTPException(409, '此会话的归档正在清理，请稍后重试')
        receipt = ConversationDeletion(conversation_id=identity, owner_id=actor_id, workspace=workspace,
                                       status='deleting', manifest={})
        session.add(receipt)
        state = workspace_state(session, actor_id, workspace)
        if state is None:
            raise RuntimeError('Conversation workspace missing')
        state.version += 1
    session.flush()
    return {'conversationId': str(identity), 'status': receipt.status}


def status(session, actor_id, workspace, identity):
    receipt = session.get(ConversationDeletion, identity)
    if receipt is None or receipt.owner_id != actor_id or receipt.workspace != workspace:
        raise HTTPException(404, '会话删除记录不存在')
    return {'conversationId': str(identity), 'status': receipt.status, 'error': receipt.error}
