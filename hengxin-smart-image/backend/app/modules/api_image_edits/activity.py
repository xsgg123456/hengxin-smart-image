"""Small, batched CLI activity projection; never load conversation contents."""
from sqlalchemy import case, func, select

from app.models import Job
from .conversation_models import Conversation, ConversationTurn
from .deletion_state import JOB_TERMINAL, TURN_TERMINAL
from .models import ApiItem


def activities(session, task_ids):
    if not task_ids:
        return {}, {}
    # Unknown/inconsistent execution evidence must remain visible until reconciled.
    rank = case(
        ((ConversationTurn.status == 'queued') & (Job.status == 'queued'), 1),
        ((ConversationTurn.status == 'running') & (Job.status.in_(('running', 'collecting', 'cancelling'))), 2),
        ((ConversationTurn.status.in_(TURN_TERMINAL)) & (Job.status.in_(JOB_TERMINAL))
         & ConversationTurn.finished_at.is_not(None) & Job.completed_at.is_not(None)
         & Job.lease_until.is_(None), 0),
        else_=3,
    )
    rows = session.execute(select(ApiItem.task_id, ApiItem.id, func.max(rank))
        .join(Conversation, Conversation.item_id == ApiItem.id)
        .join(ConversationTurn, ConversationTurn.conversation_id == Conversation.id)
        .outerjoin(Job, Job.id == ConversationTurn.job_id)
        .where(ApiItem.task_id.in_(task_ids)).group_by(ApiItem.task_id, ApiItem.id))
    task_ranks, items = {}, {}
    labels = ('idle', 'queued', 'running', 'uncertain')
    for task_id, item_id, value in rows:
        items[item_id] = labels[value]
        task_ranks[task_id] = max(task_ranks.get(task_id, 0), value)
    return {task_id: labels[value] for task_id, value in task_ranks.items()}, items
