"""Real execution usage reporting for the management center."""
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Iterable
from uuid import UUID
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.contracts import management as m
from app.modules.tasks.attempts import ExecutionAttempt, ExecutionUsage
from app.modules.tasks.models import ImageVersion, ResultSlotRecord, RoundRecord, TaskRecord
from app.resource_models import UserRecord

SHANGHAI = ZoneInfo('Asia/Shanghai')
ACTIVE_ROUNDS = frozenset({'queued', 'running', 'collecting', 'cancelling'})


def _day(value: datetime) -> date:
    """Convert a stored timestamp to the product's reporting timezone."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(SHANGHAI).date()


def _timestamp(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _parse_date(value: str | None, label: str) -> date | None:
    if value is None:
        return None
    try:
        parsed = date.fromisoformat(value)
    except ValueError as error:
        raise HTTPException(422, f'{label}格式无效，应为 YYYY-MM-DD') from error
    if parsed.isoformat() != value:
        raise HTTPException(422, f'{label}格式无效，应为 YYYY-MM-DD')
    return parsed


def _in_range(value: datetime, start: date | None, end: date | None) -> bool:
    current = _day(value)
    return (start is None or current >= start) and (end is None or current <= end)


def _usage(data: dict | None) -> m.TokenUsage | None:
    if not isinstance(data, dict):
        return None
    input_tokens, output_tokens = data.get('input_tokens'), data.get('output_tokens')
    if type(input_tokens) is not int or input_tokens < 0 or type(output_tokens) is not int or output_tokens < 0:
        return None
    return m.TokenUsage(inputTokens=input_tokens, outputTokens=output_tokens)


def _error_text(round: RoundRecord, attempt: ExecutionAttempt) -> str:
    return ' '.join(str(value) for value in (round.error, attempt.error) if value)


def _state(round: RoundRecord, attempt: ExecutionAttempt, output_count: int, expected: int) -> str:
    error = _error_text(round, attempt).lower()
    if 'timeout' in error or '超时' in error:
        return 'timeout'
    if round.status in ACTIVE_ROUNDS:
        return 'running'
    if round.status not in ('succeeded', 'partial', 'failed', 'cancelled', 'uncertain') and attempt.status in ('starting', 'running'):
        return 'running'
    if round.status == 'succeeded' and output_count >= expected:
        return 'success'
    if round.status in ('succeeded', 'partial') and output_count > 0:
        return 'partial'
    if round.status == 'cancelled' and '取消' in error:
        return 'failed'
    return 'failed'


def _kind(rounds_by_task: dict[UUID, list[RoundRecord]], current: RoundRecord) -> str:
    rounds = sorted(rounds_by_task.get(current.task_id, [current]), key=lambda row: row.created_at)
    if rounds and rounds[0].id == current.id:
        return 'initial'
    return 'single' if current.target is not None else 'whole'


def _summary(attempts: Iterable[m.UsageAttempt], task_count: int) -> m.UsageSummary:
    rows = list(attempts)
    ended = [row for row in rows if row.finishedAt is not None]
    complete_usage = bool(rows) and all(row.usage is not None for row in rows)
    count = lambda state: sum(row.state == state for row in rows)
    input_tokens = sum(row.usage.inputTokens for row in rows) if complete_usage else None
    output_tokens = sum(row.usage.outputTokens for row in rows) if complete_usage else None
    return m.UsageSummary(
        tasks=task_count,
        attempts=len(rows),
        initial=sum(row.kind == 'initial' for row in rows),
        single=sum(row.kind == 'single' for row in rows),
        whole=sum(row.kind == 'whole' for row in rows),
        running=count('running'),
        success=count('success'),
        partial=count('partial'),
        failed=count('failed'),
        timeout=count('timeout'),
        outputImages=sum(row.outputImages for row in rows),
        successRate=(count('success') / len(ended)) if ended else None,
        inputTokens=input_tokens,
        outputTokens=output_tokens,
        averageQueueSeconds=(sum(row.queueSeconds for row in rows) / len(rows)) if rows else None,
        averageDurationSeconds=(sum(row.durationSeconds or 0 for row in ended) / len(ended)) if ended else None,
    )


def _attempt(
    attempt: ExecutionAttempt,
    round: RoundRecord,
    task: TaskRecord,
    operator: UserRecord,
    kind: str,
    usage: m.TokenUsage | None,
    output_count: int,
    expected: int,
) -> m.UsageAttempt:
    state = _state(round, attempt, output_count, expected)
    finished_at = attempt.finished_at or round.finished_at
    if state != 'running' and finished_at is None:
        # An uncertain process has no authoritative completion instant. Use the
        # durable observation update so the API remains a stable terminal record.
        finished_at = round.updated_at or attempt.started_at
    if state == 'running':
        finished_at = None
    duration = None
    if finished_at is not None:
        started = attempt.started_at
        duration = max(0.0, (finished_at - started).total_seconds())
    queue = max(0.0, (attempt.started_at - round.created_at).total_seconds())
    return m.UsageAttempt(
        id=str(attempt.id), taskId=str(task.id), taskName=task.name,
        creatorId=str(task.owner_id), operatorId=str(attempt.operator_id), operatorName=operator.name,
        mode=task.mode, kind=kind, startedAt=_timestamp(attempt.started_at), finishedAt=_timestamp(finished_at),
        state=state, outputImages=output_count, queueSeconds=queue, durationSeconds=duration, usage=usage,
    )


def build_usage(session: Session, user: UserRecord, query: m.UsageQuery) -> m.UsageReport:
    """Build a report from durable execution facts without trusting CLI prose."""
    start, end = _parse_date(query.from_, '开始日期'), _parse_date(query.to, '结束日期')
    if start and end and start > end:
        raise HTTPException(422, '开始日期不能晚于结束日期')
    all_scope = user.role in ('super_admin', 'design_manager')
    if query.userId and not all_scope and query.userId != str(user.id):
        raise HTTPException(403, '只能查看个人统计')
    selected_user = None
    if query.userId:
        try:
            selected_user = UUID(query.userId)
        except ValueError as error:
            raise HTTPException(422, '统计人员 ID 无效') from error
    owner_filter = selected_user or (None if all_scope else user.id)

    users = session.scalars(select(UserRecord).order_by(UserRecord.name, UserRecord.id)).all()
    user_options = [m.UserOption(id=str(row.id), name=row.name) for row in users if all_scope or row.id == user.id]
    tasks = session.scalars(select(TaskRecord).where(TaskRecord.deleted_at.is_(None))).all()
    tasks = [row for row in tasks if (owner_filter is None or row.owner_id == owner_filter)
             and (query.mode is None or row.mode == query.mode) and _in_range(row.created_at, start, end)]

    execution_rows = session.execute(
        select(ExecutionAttempt, RoundRecord, TaskRecord, UserRecord)
        .join(RoundRecord, RoundRecord.id == ExecutionAttempt.round_id)
        .join(TaskRecord, TaskRecord.id == ExecutionAttempt.task_id)
        .join(UserRecord, UserRecord.id == ExecutionAttempt.operator_id)
        .where(TaskRecord.deleted_at.is_(None))
    ).all()
    execution_rows = [row for row in execution_rows if _in_range(row[0].started_at, start, end)
                      and (owner_filter is None or row[0].operator_id == owner_filter)
                      and (query.mode is None or row[2].mode == query.mode)]
    task_ids = {row[2].id for row in execution_rows}
    round_ids = [row[1].id for row in execution_rows]
    round_rows = session.scalars(select(RoundRecord).where(RoundRecord.task_id.in_(task_ids))).all() if task_ids else []
    rounds_by_task: dict[UUID, list[RoundRecord]] = defaultdict(list)
    for row in round_rows:
        rounds_by_task[row.task_id].append(row)
    output_counts = dict(session.execute(
        select(ImageVersion.round_id, func.count(ImageVersion.id))
        .where(ImageVersion.round_id.in_(round_ids)).group_by(ImageVersion.round_id)
    ).all()) if round_ids else {}
    expected_counts = dict(session.execute(
        select(ResultSlotRecord.task_id, func.count(ResultSlotRecord.id))
        .where(ResultSlotRecord.task_id.in_(task_ids)).group_by(ResultSlotRecord.task_id)
    ).all()) if task_ids else {}
    usage_rows = {row.attempt_id: _usage(row.data) for row in session.scalars(
        select(ExecutionUsage).where(ExecutionUsage.attempt_id.in_([row[0].id for row in execution_rows]))
    ).all()} if execution_rows else {}

    attempts: list[m.UsageAttempt] = []
    for attempt, round, task, operator in execution_rows:
        expected = 1 if round.target is not None else expected_counts.get(task.id, 0)
        attempts.append(_attempt(attempt, round, task, operator, _kind(rounds_by_task, round),
                                 usage_rows.get(attempt.id), output_counts.get(round.id, 0), expected))
    attempts.sort(key=lambda row: (row.startedAt, row.id), reverse=True)

    task_dates = [( _day(row.created_at), row.owner_id) for row in tasks]
    attempt_dates = [(_day(row[0].started_at), row[0].operator_id) for row in execution_rows]
    keys = sorted(set(task_dates + attempt_dates), reverse=True)
    task_counts: dict[tuple[date, UUID], int] = defaultdict(int)
    for key in task_dates:
        task_counts[key] += 1
    attempt_days = {str(row[0].id): _day(row[0].started_at) for row in execution_rows}
    detail_by_key: dict[tuple[date, UUID], list[m.UsageAttempt]] = defaultdict(list)
    for item in attempts:
        detail_by_key[(attempt_days[item.id], UUID(item.operatorId))].append(item)
    rows = []
    names = {str(row.id): row.name for row in users}
    for day, operator_id in keys:
        details = detail_by_key[(day, operator_id)]
        rows.append(m.UsageRow(date=day.isoformat(), userId=str(operator_id),
            userName=names.get(str(operator_id), str(operator_id)),
            summary=_summary(details, task_counts[(day, operator_id)]), details=details))
    return m.UsageReport(scope='all' if all_scope else 'personal', timezone='Asia/Shanghai',
                         summary=_summary(attempts, len(tasks)), rows=rows, users=user_options)
