"""Read-only historical projection; never fabricate erased or unprovable evidence."""
from sqlalchemy import select
from app.modules.api_image_edits.models import ApiAttempt, ApiItem, ApiTask, ApiVersion
from app.modules.api_image_edits.conversation_models import Conversation, ConversationTurn
from .facts import as_dict, fact
from .models import ApiUsageFact


def historical_facts(session, *, task_id=None, adopted_keys=(), verified_submissions=()):
    tasks = {t.id: t for t in session.scalars(select(ApiTask).where(
        ApiTask.id == task_id) if task_id else select(ApiTask))}
    if not tasks:
        return []
    items = {i.id: i for i in session.scalars(select(ApiItem).where(ApiItem.task_id.in_(tasks)))}
    result = [fact(t, 'task_created', t.id, kind='task_created', operator_id=t.operator_id,
                   occurred_at=t.created_at) for t in tasks.values()]
    for attempt in session.scalars(select(ApiAttempt).where(ApiAttempt.item_id.in_(items))):
        item = items[attempt.item_id]
        result.append(fact(tasks[item.task_id], 'api_request', attempt.id,
                           operator_id=attempt.operator_id, occurred_at=attempt.created_at,
                           completed_at=attempt.completed_at,
                           state='uncertain' if attempt.resolved_by else attempt.state))
    conversations = {c.id: c for c in session.scalars(select(Conversation).where(
        Conversation.item_id.in_(items)))}
    adopted = {}
    for turn in session.scalars(select(ConversationTurn).where(
            ConversationTurn.conversation_id.in_(conversations))):
        item = items[conversations[turn.conversation_id].item_id]
        task = tasks[item.task_id]
        result.append(fact(task, 'cli_submission', turn.id, channel='cli', kind='image_edit',
                           operator_id=turn.operator_id, occurred_at=turn.created_at, state='submitted'))
        proven = bool(turn.process_identity)
        if (proven or (turn.snapshot or {}).get('executionDispatched')
                or turn.status in ('candidate', 'adopted', 'waiting_user')
                or (turn.started_at and turn.status in ('failed', 'cancelled', 'uncertain')
                    and f'cli_submission:{turn.id}' not in verified_submissions)):
            result.append(fact(task, 'cli_round', turn.id, channel='cli', kind='image_edit',
                               operator_id=turn.operator_id, occurred_at=turn.started_at or turn.created_at,
                               completed_at=turn.finished_at, state=turn.status if proven else 'unverified',
                               quantity=int(proven)))
        if turn.candidate_id:
            result.append(fact(task, 'cli_candidate', turn.id, channel='cli', kind='image_edit',
                               operator_id=turn.operator_id, occurred_at=turn.finished_at or turn.created_at))
        if turn.adopted_version is not None:
            adopted[item.id, turn.adopted_version] = turn
    for version in session.scalars(select(ApiVersion).where(ApiVersion.item_id.in_(items))):
        item = items[version.item_id]
        task = tasks[item.task_id]
        if (item.id, version.number) in adopted or f'adopt:{version.id}' in adopted_keys:
            result.append(fact(task, 'adopt', version.id, channel='cli', kind='adopt',
                               operator_id=version.operator_id, occurred_at=version.created_at))
        else:
            result.append(fact(task, 'version_published', version.id,
                               channel='api' if version.kind in ('generation', 'text_edit', 'text_repair') else 'unknown',
                               kind=version.kind if version.kind in ('generation', 'text_edit', 'text_repair') else 'legacy_unknown',
                               operator_id=version.operator_id,
                               occurred_at=version.created_at))
    return result


def read_facts(session):
    """No flush/commit/write; stored immutable attribution wins over mutable source rows."""
    with session.no_autoflush:
        durable = {row.key: as_dict(row) for row in session.scalars(select(ApiUsageFact))}
        historical = historical_facts(session, adopted_keys=durable,
            verified_submissions={key for key, row in durable.items() if row['attribution'] == 'verified'})
    return list({**{row['key']: row for row in historical}, **durable}.values())
