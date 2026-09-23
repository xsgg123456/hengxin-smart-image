"""Explicitly re-admit a false failed final delivery for fenced collection only."""
import json
from pathlib import Path

from sqlalchemy import select

from app.core.config import get_settings
from app.execution.final_delivery import collect_final_outputs
from app.execution.intervention import invocation_summary
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
                or job.claim_token != attempt.claim_token or attempt.error != 'cli_error'
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
        if (not isinstance(receipt, dict) or type(receipt.get('exit_code')) is not int
                or receipt['exit_code'] != 0 or receipt.get('reason')):
            raise ValueError('Successful exit not proved')
        if json.loads((control / 'delivery.json').read_text()) != {'version': 'final-reply-v1'}:
            raise ValueError('Unsupported delivery protocol')
        identity = session.get(ExecutionSession, task.id)
        if not identity or not identity.session_id:
            raise ValueError('Session missing')
        summary = invocation_summary(control, identity.session_id)
        if summary.error or not summary.turn_completed:
            raise ValueError('No successful final turn')
        if session.scalar(select(ImageVersion.id).where(ImageVersion.round_id == round.id).limit(1)):
            raise ValueError('Round already has published versions')
        slots = session.scalars(select(ResultSlotRecord).where(ResultSlotRecord.task_id == task.id)).all()
        expected = len([slot for slot in slots if round.target is None or slot.slot == round.target])
        images = collect_final_outputs(control.parents[1] / 'rounds' / str(round.id),
            control.parents[1] / 'home' / '.codex', control / 'events.jsonl', identity.session_id,
            json.loads((control / 'baseline.json').read_text()), expected)
        observation = dict(attempt.observation or {})
        observation['recollection'] = {'at': utcnow().isoformat(), 'reason': 'verified_reconnect_false_failure',
            'previousFailure': observation.get('failure'), 'previousError': attempt.error,
            'previousFinishedAt': str(round.finished_at)}
        observation['stage'] = 'uncertain'
        attempt.observation = observation
        attempt.status = 'uncertain'
        mark_uncertain(round, job)
        return {'attemptId': str(attempt.id), 'roundId': str(round.id), 'images': len(images)}
