"""Explicitly re-admit a false failed final delivery for fenced collection only."""
import json
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.capacity.admission import reserve
from app.execution.delivery_acceptance import accept_delivery
from app.execution.process import same_process
from app.models import utcnow
from app.modules.tasks.attempts import ExecutionAttempt, ExecutionSession
from app.modules.tasks.claims import locked_execution, mark_uncertain
from app.modules.tasks.models import ImageVersion, ResultSlotRecord, RoundRecord


def prepare_recollection(factory, attempt_id):
    """No model call. Fail closed on stale/current, process, exit or file evidence."""
    settings = get_settings()
    with factory.begin() as session:
        attempt = session.get(ExecutionAttempt, attempt_id)
        if not attempt:
            raise ValueError('Attempt missing')
        info = session.get(RoundRecord, attempt.round_id)
        task, round, job = locked_execution(session, info.job_id)
        session.refresh(attempt)
        if (not job or task.execution_source != 'cli' or task.deleted_at or round.cancel_requested
                or task.current_round_id != round.id or round.status != 'failed'
                or job.status != 'failed' or attempt.status != 'finished'
                or job.claim_token != attempt.claim_token
                or attempt.node != settings.worker_node_name):
            raise ValueError('Not an eligible current false failure')
        if not all((attempt.process_id, attempt.boot_id, attempt.process_start)) or same_process(
                attempt.process_id, attempt.boot_id, attempt.process_start):
            raise ValueError('Original process not proved stopped')
        control = Path(attempt.workspace)
        if (not control.resolve().is_relative_to(Path(settings.codex_execution_root).resolve())
                or any(p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction())
                       for p in (control, *control.parents))):
            raise ValueError('Unsafe control directory')
        receipt = json.loads((control / 'exit.json').read_text())
        if json.loads((control / 'delivery.json').read_text()) != {'version': 'final-reply-v1'}:
            raise ValueError('Unsupported delivery protocol')
        identity = session.get(ExecutionSession, task.id)
        if not identity or not identity.session_id:
            raise ValueError('Session missing')
        if session.scalar(select(ImageVersion.id).where(ImageVersion.round_id == round.id).limit(1)):
            raise ValueError('Round already has published versions')
        slots = session.scalars(select(ResultSlotRecord).where(ResultSlotRecord.task_id == task.id)).all()
        expected = len([slot for slot in slots if round.target is None or slot.slot == round.target])
        if not reserve(session, round.id, 'cli', round.id, max(1, expected) * 20 * 1024 * 1024):
            raise ValueError('No capacity for recollection; original evidence retained')
        images = accept_delivery(control, task.id, round.id, identity.session_id, expected, receipt)
        observation = dict(attempt.observation or {})
        observation['recollection'] = {'at': utcnow().isoformat(), 'reason': 'verified_final_delivery',
            'previousFailure': observation.get('failure'), 'previousError': attempt.error,
            'previousFinishedAt': str(round.finished_at)}
        observation.update(stage='storing', deliveryReady=True, detectedImages=expected, failure=None)
        attempt.observation = observation
        attempt.status = 'uncertain'
        mark_uncertain(round, job)
        round.error = job.error = '图片已生成，正在保存'
        return {'attemptId': str(attempt.id), 'roundId': str(round.id), 'images': len(images)}
