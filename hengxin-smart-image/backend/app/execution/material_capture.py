"""Freeze business evidence in the shared DB, independent of native worker paths."""
import logging
import time
from sqlalchemy import select
from app.core.config import get_settings
from app.modules.tasks.models import RoundRecord, TaskRecord
from app.modules.tasks.attempts import ExecutionAttempt
from .material_history import public_text, read_history
from .material_bindings import historical_inputs

logger = logging.getLogger(__name__)


class CaptureTicker:
    def __init__(self, factory, attempt_id):
        self.factory, self.attempt_id = factory, attempt_id
        self.last = time.monotonic()

    def tick(self):
        if time.monotonic() - self.last >= 30:
            freeze_calls(self.factory, self.attempt_id)
            self.last = time.monotonic()


def freeze_prompt(factory, round_id, manifest, prompt):
    try:
        _freeze_prompt(factory, round_id, manifest, prompt)
        return True
    except Exception:
        logger.warning('Business prompt capture deferred for round %s', round_id)
        return False


def _freeze_prompt(factory, round_id, manifest, prompt):
    with factory.begin() as session:
        row = session.scalar(select(RoundRecord).where(RoundRecord.id == round_id).with_for_update())
        evidence = dict(row.execution_config.get('materials', {}))
        prompts = list(evidence.get('systemPrompts', []))
        prompts.append({'label': f'系统任务提示词 {len(prompts) + 1}', 'text': public_text(prompt)})
        evidence.update(manifest=manifest, systemPrompts=prompts)
        row.execution_config = {**row.execution_config, 'materials': evidence}


def freeze_calls(factory, attempt_id):
    # Observability must never turn a completed generation into a retryable failure.
    try:
        with factory() as session:
            attempt = session.get(ExecutionAttempt, attempt_id)
            if not attempt:
                return False
            data = read_history(get_settings().codex_execution_root, attempt.task_id,
                                attempt.round_id, attempt.started_at, attempt.finished_at)
            round_id = attempt.round_id
        with factory.begin() as session:
            row = session.scalar(select(RoundRecord).where(RoundRecord.id == round_id).with_for_update())
            evidence = dict(row.execution_config.get('materials', {}))
            if not evidence.get('systemPrompts'):
                evidence['systemPrompts'] = data['systemPrompts']
            if not evidence.get('manifest'):
                task = session.get(TaskRecord, row.task_id)
                bindings = historical_inputs(session, task, row,
                    get_settings().codex_execution_root, evidence['systemPrompts'])
                prior = {(item['role'], item['fileId']): item for item in evidence.get('historicalInputs', [])
                         if item.get('verified')}
                evidence['historicalInputs'] = [prior.get((item['role'], item['fileId']), item) for item in bindings]
            if data['toolCalls'] or not evidence.get('toolCalls'):
                evidence['toolCalls'] = data['toolCalls']
            evidence.update(notices=data['notices'], captured=True)
            row.execution_config = {**row.execution_config, 'materials': evidence}
        return True
    except Exception:
        logger.warning('Business execution evidence capture deferred for attempt %s', attempt_id)
        return False
