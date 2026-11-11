"""Execution rows from retained evidence and the current queue; never infer outputs."""
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select

from app.contracts.activity import Record
from app.modules.api_image_edits.models import ApiAttempt, ApiItem, ApiTask
from app.modules.api_image_edits.conversation_models import Conversation, ConversationTurn
from app.modules.management.api_usage import utc
from app.modules.management.api_usage_summary import API_FAILURES, CLI_SUCCESSES, generation_type

PHASES = {'queued', 'running', 'retry_wait', 'collecting', 'cancelling',
          'uncertain', 'failed', 'succeeded', 'cancelled'}


@dataclass
class Entry:
    row: Record
    api: int = 0
    cli: int = 0
    statistics_time: datetime | None = None


def group_status(status):
    return 'running' if status in ('retry_wait', 'collecting', 'cancelling') else status


def status_of(state):
    if state in CLI_SUCCESSES:
        return 'succeeded'
    if state in API_FAILURES or state == 'timeout':
        return 'failed'
    return state if state in PHASES else 'unknown'


def safe_error(status):
    # Stored diagnostics can contain credentials, upstream URLs and prompt fragments.
    return {'failed': '本次执行失败，请查看任务状态后决定是否重试。',
            'uncertain': '最终执行结果尚未确认。',
            'retry_wait': '等待重试。'}.get(status, '')


def make_row(fact, names, visible, *, identifier=None, state=None, started=None, images=None):
    status = status_of(state or fact['state'])
    end = utc(fact['completed_at']) if fact['completed_at'] else None
    start = utc(started) if started else None
    actor = fact['operator_id']
    return Record(id=identifier or fact['key'], taskId=str(fact['task_id']),
        task=fact['task_name'], personId=str(actor) if actor else None,
        person=names.get(actor, '未知操作者'), kind=generation_type(fact), status=status,
        createdAt=utc(fact['occurred_at']).isoformat(),
        startedAt=start.isoformat() if start else None, finishedAt=end.isoformat() if end else None,
        images=images, seconds=max(0, (end - start).total_seconds()) if start and end else None,
        retry=fact['is_retry'], error=safe_error(status), taskDeleted=fact['task_id'] not in visible)


def execution_records(session, facts, names, now):
    tasks = {task.id: task for task in session.scalars(select(ApiTask))}
    visible = {key for key, task in tasks.items() if task.deleted_at is None}
    indexed = {fact['key']: fact for fact in facts}
    entries = {}
    for fact in facts:
        if fact['category'] == 'api_request':
            entries[fact['key']] = Entry(make_row(fact, names, visible,
                started=fact['occurred_at']), api=fact['quantity'])
        elif fact['category'] in ('cli_submission', 'cli_round'):
            identifier = fact['key'].split(':', 1)[1]
            key = 'cli_round:' + identifier
            round_fact = indexed.get(key)
            evidence = round_fact or fact
            started = evidence['occurred_at'] if round_fact and round_fact['quantity'] else None
            candidate = indexed.get('cli_candidate:' + identifier)
            row = make_row(evidence, names, visible, identifier=key,
                started=started, images=candidate['quantity'] if candidate else None)
            submission = indexed.get('cli_submission:' + identifier)
            if submission:
                row.createdAt = utc(submission['occurred_at']).isoformat()
            entries[key] = Entry(row,
                cli=round_fact['quantity'] if round_fact and round_fact['state'] != 'unverified' else 0,
                statistics_time=utc(evidence['occurred_at']))

    items = {item.id: item for item in session.scalars(select(ApiItem))}
    latest_attempts = {}
    for attempt in session.scalars(select(ApiAttempt).order_by(ApiAttempt.created_at, ApiAttempt.id)):
        latest_attempts[attempt.item_id] = attempt
    for item in items.values():
        if item.task_id not in visible:
            continue
        phase = ('retry_wait' if item.state == 'queued' and item.next_attempt_at
                 and utc(item.next_attempt_at) > now else item.state)
        if phase not in PHASES:
            continue
        attempt = latest_attempts.get(item.id)
        key = f'api_request:{attempt.id}' if attempt else ''
        same_cycle = attempt and attempt.retry_cycle_id == item.retry_cycle_id
        if same_cycle and key in entries and phase not in ('queued', 'retry_wait'):
            row = entries[key].row
            row.current, row.status, row.error = True, phase, safe_error(phase)
            # An upstream return can precede collection; this is not execution completion.
            if phase in ('running', 'collecting', 'cancelling'):
                row.finishedAt = row.seconds = None
        elif phase not in ('succeeded', 'cancelled'):
            task = tasks[item.task_id]
            kind = ((item.revision_snapshot or {}).get('kind', 'generation')
                    if item.request_operator_id else 'legacy_unknown')
            data = dict(key=f'api_queue:{item.id}', task_id=task.id, task_name=task.name,
                operator_id=item.request_operator_id, kind=kind, channel='api', category='api_request',
                state=phase, occurred_at=item.retry_started_at or item.created_at,
                completed_at=None, is_retry=item.request_is_retry)
            row = make_row(data, names, visible)
            row.current = True
            entries[row.id] = Entry(row)

    conversations = {c.id: c for c in session.scalars(select(Conversation))}
    turns = list(session.scalars(select(ConversationTurn).order_by(
        ConversationTurn.created_at, ConversationTurn.id)))
    latest_turns = {turn.conversation_id: turn.id for turn in turns}
    for turn in turns:
        conversation = conversations.get(turn.conversation_id)
        item = items.get(conversation.item_id) if conversation else None
        key = f'cli_round:{turn.id}'
        if item is None or key not in entries:
            continue
        row = entries[key].row
        row.status = status_of(turn.status)
        row.error = safe_error(row.status)
        row.current = item.task_id in visible and latest_turns[turn.conversation_id] == turn.id
        if turn.finished_at:
            row.finishedAt = utc(turn.finished_at).isoformat()
            row.seconds = (max(0, (utc(turn.finished_at) - utc(
                indexed[key]['occurred_at'])).total_seconds()) if row.startedAt else None)
    return list(entries.values())
