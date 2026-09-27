"""Retain stopped delivery work without reopening model execution."""
import logging

from app.models import utcnow
from app.modules.tasks.attempts import ExecutionAttempt
from app.modules.tasks.claims import end, locked_execution, mark_uncertain

PENDING_SAVE = '图片已生成，正在保存'


def retain_delivery(factory, job_id, token, attempt_id, *, ready=False, count=None):
    with factory.begin() as session:
        task, round, job = locked_execution(session, job_id)
        if (not job or job.claim_token != token or task.current_round_id != round.id
                or job.status not in ('running', 'collecting', 'cancelling', 'uncertain')):
            return  # Includes an ambiguous publication which actually committed.
        attempt = session.get(ExecutionAttempt, attempt_id)
        if not attempt or attempt.claim_token != token:
            return
        if task.deleted_at or round.cancel_requested:
            end(session, round, job, 'cancelled', '任务已取消')
            attempt.status, attempt.finished_at = 'finished', utcnow()
            return
        mark_uncertain(round, job)
        job.lease_until = None
        attempt.status, attempt.finished_at = 'uncertain', None
        data = dict(attempt.observation or {})
        data.update(stage='storing' if ready else 'uncertain', failure=None,
                    deliveryReady=ready, updatedAt=utcnow().isoformat())
        if ready:
            round.error = job.error = PENDING_SAVE
            data['detectedImages'] = count
        attempt.observation = data
    logging.getLogger(__name__).warning('delivery_recovery_pending attempt=%s ready=%s', attempt_id, ready)
