"""One fail-closed idle predicate for deletion admission and batched UI summaries."""
from fastapi import HTTPException
from sqlalchemy import select
from app.models import Job
from app.retention.models import RetentionEntry
from .conversation_models import Conversation, ConversationTurn
from .deletion_models import ApiTaskDeletion
from .models import ApiAttempt, ApiChannel, ApiItem, ApiTask

TASK_TERMINAL = ('succeeded', 'failed', 'partial_failed', 'cancelled')
ITEM_TERMINAL = ('succeeded', 'failed', 'cancelled')
TURN_TERMINAL = ('candidate', 'waiting_user', 'adopted', 'failed', 'cancelled')
JOB_TERMINAL = ('succeeded', 'failed', 'cancelled')
ATTEMPT_TERMINAL = (*ITEM_TERMINAL, 'permanent', 'retryable', 'channel', 'uncertain')


def fenced(session, task_id):
    return session.get(ApiTaskDeletion, task_id) is not None


def guard(session, task_id):
    if fenced(session, task_id):
        raise HTTPException(409, '任务正在永久删除或删除尚未完成，请等待或重试删除')


def reasons(session, task_ids):
    """Select only execution evidence; no prompts, messages, result bytes or histories."""
    if not task_ids:
        return {}
    result = {}
    def block(identifier, message):
        result.setdefault(identifier, message)
    for identifier, state in session.execute(select(ApiTask.id, ApiTask.state).where(ApiTask.id.in_(task_ids))):
        if state not in TASK_TERMINAL:
            block(identifier, 'API 任务仍在排队、执行或待核实，暂不能删除')
    query = select(ApiItem.task_id, ApiItem.state, ApiItem.lease_token, ApiItem.lease_until)
    for identifier, state, token, lease in session.execute(query.where(ApiItem.task_id.in_(task_ids))):
        # Terminal failures retain URL/bytes/backoff solely for a later manual retry.
        # Claims only consume ACTIVE states; these recovery inputs do not own execution.
        if state not in ITEM_TERMINAL or token or lease:
            block(identifier, '图片仍在处理或执行租约尚未确认结束，暂不能删除')
    attempts = select(ApiItem.task_id, ApiAttempt.state, ApiAttempt.completed_at).join(
        ApiAttempt, ApiAttempt.item_id == ApiItem.id)
    for identifier, state, completed in session.execute(attempts.where(ApiItem.task_id.in_(task_ids))):
        if state not in ATTEMPT_TERMINAL or not completed:
            block(identifier, '存在尚未确认结束的 API 调用，暂不能删除')
    gate = session.execute(select(ApiItem.task_id).join(ApiChannel, ApiChannel.item_id == ApiItem.id)
        .where(ApiItem.task_id.in_(task_ids))).scalars().all()
    for identifier in gate:
        block(identifier, 'API 通道仍持有图片执行权，暂不能删除')
    turns = select(ApiItem.task_id, ConversationTurn.status, ConversationTurn.finished_at,
        ConversationTurn.process_identity, ConversationTurn.snapshot['executionDispatched'].as_boolean(),
        Job.status, Job.lease_until, Job.completed_at).join(Conversation, Conversation.item_id == ApiItem.id)
    turns = turns.join(ConversationTurn, ConversationTurn.conversation_id == Conversation.id).outerjoin(
        Job, Job.id == ConversationTurn.job_id).where(ApiItem.task_id.in_(task_ids))
    for identifier, state, finished, identity, dispatched, job_state, lease, completed in session.execute(turns):
        valid_identity = (isinstance(identity, dict) and all(identity.get(k) for k in ('pid', 'boot', 'birth', 'node')))
        if (state not in TURN_TERMINAL or not finished or job_state not in JOB_TERMINAL
                or lease is not None or not completed or (dispatched and not valid_identity)):
            block(identifier, 'CLI 修改尚未确认结束，包含等待、执行、停止或待核实状态')
    retained = select(ApiItem.task_id).join(Conversation, Conversation.item_id == ApiItem.id).join(
        RetentionEntry, RetentionEntry.resource_id == Conversation.id).where(ApiItem.task_id.in_(task_ids),
        RetentionEntry.domain == 'api_cli', RetentionEntry.status.in_(('cache_pending', 'expire_pending')))
    for identifier in session.scalars(retained):
        block(identifier, '会话正在自动清理，请稍后重试删除')
    return result


def describe(session, task_ids):
    blocked = reasons(session, task_ids)
    receipts = {r.task_id: r for r in session.scalars(select(ApiTaskDeletion).where(
        ApiTaskDeletion.task_id.in_(task_ids)))} if task_ids else {}
    result = {}
    for identifier in task_ids:
        receipt = receipts.get(identifier)
        state = ('failed' if receipt.status == 'delete_failed' else 'deleting') if receipt else 'idle'
        reason = ('任务正在永久删除' if state == 'deleting' else blocked.get(identifier))
        result[identifier] = dict(canDelete=state != 'deleting' and not blocked.get(identifier),
            deleteBlockedReason=reason, deletionState=state, deletionError=receipt.error if receipt else None)
    return result
