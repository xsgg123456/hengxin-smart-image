from uuid import UUID
from fastapi import HTTPException
from sqlalchemy import select, func

from app.contracts.execution import ExecutionView
from app.execution.diagnostics import failure_for
from app.execution.observation import LABELS, TERMINAL
from .attempts import ExecutionAttempt
from .models import RoundRecord, ResultSlotRecord
from .queries import find_task, stamp


def execution_view(session, task_id, round_id=None):
    task = find_task(session, task_id)
    round = session.get(RoundRecord, round_id or task.current_round_id)
    if not round or round.task_id != task.id:
        raise HTTPException(404, '执行轮次不存在')
    attempt = session.scalar(select(ExecutionAttempt).where(ExecutionAttempt.round_id == round.id))
    data = attempt.observation if attempt and isinstance(attempt.observation, dict) else {}
    stage = data.get('stage', 'queued' if round.status == 'queued' else 'generating')
    stage = TERMINAL.get(round.status, stage)
    failure = data.get('failure')
    if round.status in ('cancelled', 'uncertain'):
        failure = failure_for('cancelled' if round.status == 'cancelled' else 'execution_uncertain', stage)
    elif round.status in ('failed', 'partial') and not failure:
        startup = failure_for('startup_failed', 'starting')
        # Before an attempt exists, the runner can still persist this exact safe
        # reason on the round. Never return arbitrary legacy error prose.
        failure = startup if round.error == startup['message'] else failure_for(
            'legacy_failure' if not data else 'unexpected_error', stage)
    count = 1 if round.target is not None else session.scalar(select(func.count()).select_from(
        ResultSlotRecord).where(ResultSlotRecord.task_id == task.id))
    return ExecutionView(taskId=str(task.id), roundId=str(round.id), status=round.status,
        source=task.execution_source, diagnosticId=str(attempt.id) if attempt else None,
        stage=stage, label='正在取消，等待执行器停止' if round.status == 'cancelling' else LABELS[stage],
        startedAt=stamp(round.started_at or round.created_at), finishedAt=stamp(round.finished_at),
        updatedAt=data.get('updatedAt'), lastActivityAt=data.get('lastActivityAt'),
        totalImages=count, detectedImages=data.get('detectedImages'),
        legacy=not bool(data) or bool(data.get('legacy')), events=data.get('events', []), failure=failure)
