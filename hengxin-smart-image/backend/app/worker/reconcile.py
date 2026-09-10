"""Resume collection only after proving the exact local invocation has stopped."""
import json
from datetime import timedelta
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, update
from app.core.config import get_settings
from app.models import Job, utcnow
from app.modules.tasks.attempts import ExecutionAttempt, ExecutionSession, ExecutionUsage
from app.modules.tasks.claims import end, locked_execution, mark_uncertain, valid
from app.modules.tasks.models import RoundRecord, ResultSlotRecord, TaskRecord
from app.modules.tasks.results import publish_results
from app.modules.files.service import save_upload
from app.resource_models import UserRecord
from app.storage.minio_store import get_store
from app.worker.leases import heartbeat
from app.execution.process import same_process
from app.execution.events import parse_events
from app.execution.output_collector import collect_outputs
from app.execution.provenance import verify_provenance


def _acquire(factory, attempt):
    """Rotate ownership without claiming another invocation or incrementing usage."""
    with factory.begin() as session:
        info = session.get(RoundRecord, attempt.round_id)
        if not info:
            return None
        task, round, job = locked_execution(session, info.job_id)
        current = session.get(ExecutionAttempt, attempt.id)
        if (not job or task.execution_source != 'cli' or
                task.current_round_id != round.id or round.status != 'uncertain' or
                job.status != 'uncertain' or job.claim_token != attempt.claim_token or
                current.claim_token != attempt.claim_token):
            return None
        if task.deleted_at or round.cancel_requested:
            end(session, round, job, 'cancelled', '原执行进程已退出，取消已确认')
            current.status, current.finished_at = 'finished', utcnow()
            return None
        token = uuid4()
        # CAS also fences competing sweepers on databases without row locks.
        changed = session.execute(update(Job).where(Job.id == job.id,
            Job.status == 'uncertain', Job.claim_token == attempt.claim_token).values(
            claim_token=token, status='running', error=None,
            lease_until=utcnow() + timedelta(seconds=get_settings().job_lease_seconds)))
        if changed.rowcount != 1:
            return None
        current.claim_token, current.status = token, 'uncertain'
        round.status, round.error = 'running', None
        identity = session.get(ExecutionSession, task.id)
        count = 1 if round.target is not None else len(session.scalars(
            select(ResultSlotRecord).where(ResultSlotRecord.task_id == task.id)).all())
        return job.id, token, round.operator_id, count, identity.session_id if identity else None


def _settle(factory, attempt_id, job_id, token, summary=None, failed=False):
    with factory.begin() as session:
        task, round, job = locked_execution(session, job_id)
        if not job or job.claim_token != token or job.status not in ('running', 'collecting', 'cancelling', 'uncertain', 'succeeded', 'partial', 'failed'):
            return
        attempt = session.get(ExecutionAttempt, attempt_id)
        if summary:
            identity = session.get(ExecutionSession, task.id)
            if identity and summary.session_id and identity.session_id in (None, summary.session_id):
                identity.session_id, identity.status = summary.session_id, 'ready'
            session.merge(ExecutionUsage(attempt_id=attempt.id, data=summary.usage))
        if job.status in ('succeeded', 'partial', 'failed'):
            attempt.status, attempt.finished_at = 'finished', utcnow()
        elif task.deleted_at or round.cancel_requested:
            end(session, round, job, 'cancelled', '原执行进程已退出，取消已确认')
            attempt.status, attempt.finished_at = 'finished', utcnow()
        elif failed:
            end(session, round, job, 'failed', '原执行进程已退出并明确报告失败')
            attempt.status, attempt.finished_at = 'finished', utcnow()
        else:
            mark_uncertain(round, job)
            job.lease_until = None
            attempt.status = 'uncertain'


def _active(factory, job_id, token):
    with factory() as session:
        task, round, job = locked_execution(session, job_id)
        return bool(job and valid(task, round, job, token))


def reconcile_once(factory, store=None):
    settings = get_settings()
    with factory() as session:
        rows = session.scalars(select(ExecutionAttempt).join(
            RoundRecord, RoundRecord.id == ExecutionAttempt.round_id).join(
            TaskRecord, TaskRecord.id == ExecutionAttempt.task_id).where(
            ExecutionAttempt.node == settings.worker_node_name,
            TaskRecord.execution_source == 'cli', RoundRecord.status == 'uncertain')).all()
        session.expunge_all()
    for attempt in rows:
        if not all((attempt.process_id, attempt.boot_id, attempt.process_start)):
            continue
        try:
            if same_process(attempt.process_id, attempt.boot_id, attempt.process_start):
                continue
            control = Path(attempt.workspace)
            root = Path(settings.codex_execution_root).resolve()
            if (not control.resolve().is_relative_to(root) or
                    any(p.is_symlink() or (hasattr(p, 'is_junction') and p.is_junction())
                        for p in (control, *control.parents))):
                continue
        except (OSError, ValueError):
            continue  # Failure to inspect the identity is not proof of exit.
        ownership = _acquire(factory, attempt)
        if not ownership:
            continue
        job_id, token, operator_id, expected, previous = ownership
        summary, failed = None, False
        try:
            with heartbeat(factory, job_id, token):
                summary = parse_events(control / 'events.jsonl', previous)
                receipt = json.loads((control / 'exit.json').read_text()) if (control / 'exit.json').is_file() else {}
                failed = (isinstance(receipt, dict) and
                    ((type(receipt.get('exit_code')) is int and receipt['exit_code'] != 0) or
                     receipt.get('reason') in ('cancelled', 'timeout', 'output_limit')))
                failed = failed or summary.error in ('turn_failed', 'cli_error')
                if failed or summary.error or not summary.turn_completed:
                    continue
                home = control.parent.parent / 'home' / '.codex'
                baseline = json.loads((control / 'baseline.json').read_text())
                proof = json.loads((control / 'provenance.json').read_text())
                manifest = control.parent.parent / 'rounds' / str(attempt.round_id) / 'manifest.json'
                images = collect_outputs(home, summary.session_id, baseline, expected,
                    manifest if manifest.exists() else None, allow_partial=True)
                successful = [image for image in images if image is not None]
                if successful:
                    verify_provenance(home, summary.session_id, proof, successful)
                outputs = []
                for image in images:
                    if not _active(factory, job_id, token):
                        break
                    if image is None:
                        outputs.append(None)
                        continue
                    with factory() as session:
                        user = session.get(UserRecord, operator_id)
                        outputs.append(save_upload(session, store or get_store(), user, image).id)
                if len(outputs) == expected:
                    publish_results(factory, job_id, token, outputs)
        except Exception:
            pass  # Keep evidence and exclusive uncertain state; never replay CLI.
        finally:
            _settle(factory, attempt.id, job_id, token, summary, failed)
