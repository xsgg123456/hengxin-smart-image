"""API CLI histories expire without changing API images, versions or generation."""
from datetime import timedelta
from sqlalchemy import delete, select
from app.core.config import get_settings
from app.models import Job, Outbox, utcnow
from app.execution.process import same_process
from app.modules.api_image_edits.models import ApiItem, ApiTask
from app.modules.api_image_edits.conversation_models import Conversation, ConversationTurn, ConversationEvent
from .state import entry, due, aware, HISTORY_AGE
from .objects import queue_unused
from . import paths

ITEM_TERMINAL = ('succeeded', 'failed', 'cancelled')
TURN_TERMINAL = ('candidate', 'waiting_user', 'adopted', 'failed', 'cancelled')
JOB_TERMINAL = ('succeeded', 'failed', 'cancelled')


def locked(session, identifier):
    conversation = session.get(Conversation, identifier)
    if conversation is None:
        return None
    item = session.get(ApiItem, conversation.item_id)
    task = session.scalar(select(ApiTask).where(ApiTask.id == item.task_id)
                          .with_for_update(skip_locked=True))
    if task is None:
        return None
    session.refresh(item, with_for_update=True)
    session.refresh(conversation, with_for_update=True)
    return task, item, conversation, entry(session, 'api_cli', identifier)


def busy(session, item, conversation):
    if item.state not in ITEM_TERMINAL or item.lease_token or item.result_url or item.result_bytes:
        return True
    turns = session.scalars(select(ConversationTurn).where(
        ConversationTurn.conversation_id == conversation.id)).all()
    for turn in turns:
        job = session.get(Job, turn.job_id)
        if (turn.status not in TURN_TERMINAL or not turn.finished_at or not job
                or job.status not in JOB_TERMINAL or job.lease_until is not None):
            return True
        identity = turn.process_identity
        if identity:
            if identity.get('node') != get_settings().worker_node_name:
                return True
            try:
                if same_process(identity['pid'], identity['boot'], identity['birth']):
                    return True
            except (OSError, KeyError, ValueError):
                return True
    return False


def erase_history(session, conversation, row, now):
    from app.modules.management.api_stats.backfill import preserve
    item = session.get(ApiItem, conversation.item_id)
    preserve(session, task_id=item.task_id)
    turns = session.scalars(select(ConversationTurn).where(
        ConversationTurn.conversation_id == conversation.id)).all()
    jobs = [turn.job_id for turn in turns]
    candidates = {value for t in turns for value in (t.candidate_id, t.annotation_id) if value}
    count = sum(session.get(Job, identifier).execution_count for identifier in jobs)
    row.counters = {**row.counters, 'turns': row.counters.get('turns', 0) + len(turns),
                    'calls': row.counters.get('calls', 0) + count}
    session.execute(delete(ConversationEvent).where(ConversationEvent.conversation_id == conversation.id))
    # Clear self-FKs before deleting all turns of this conversation.
    for turn in turns:
        turn.base_turn_id = None
    session.flush()
    session.execute(delete(ConversationTurn).where(ConversationTurn.conversation_id == conversation.id))
    if jobs:
        session.execute(delete(Outbox).where(Outbox.job_id.in_(jobs)))
        session.execute(delete(Job).where(Job.id.in_(jobs)))
    session.flush()
    queue_unused(session, 'api-image-edits', candidates, now)
    conversation.session_id = None
    conversation.last_event_id += 1  # Old GET/SSE snapshots cannot resurrect deleted turns.
    row.status, row.expired_at, row.next_cleanup_at, row.error = 'expired', now, None, None


def process(factory, store, root, resource_id, now=None):
    now = aware(now or utcnow())
    with factory.begin() as session:
        data = locked(session, resource_id)
        if data is None or data[3] is None:
            return 'missing_or_locked'
        _, item, conversation, row = data
        action = due(row, now)
        if not action:
            return 'not_due'
        if busy(session, item, conversation):
            row.next_cleanup_at = now + timedelta(hours=1)
            return 'protected'
        row.status, row.next_cleanup_at = action, now + timedelta(hours=1)
    # A committed pending fence survives crashes between filesystem and DB commits.
    try:
        with factory.begin() as session:
            data = locked(session, resource_id)
            if data is None:
                return 'locked'
            _, item, conversation, row = data
            if row.status != action or busy(session, item, conversation):
                return 'protected'
            paths.clean(root / 'api-edits', resource_id, cache_only=action == 'cache_pending')
            if action == 'expire_pending':
                erase_history(session, conversation, row, now)
            else:
                row.status, row.cache_cleared_at, row.error = 'active', now, None
                row.next_cleanup_at = aware(row.last_activity_at) + HISTORY_AGE
        return 'expired' if action == 'expire_pending' else 'cache_cleared'
    except Exception:
        with factory.begin() as session:
            data = locked(session, resource_id)
            if data is not None and data[3].status == action:
                data[3].error = '清理尚未完成，将自动重试'
                data[3].next_cleanup_at = now + timedelta(hours=1)
        return 'retry'
