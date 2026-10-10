"""Old CLI task retention under the same parent lock used by admission."""
from datetime import timedelta
from uuid import UUID

from sqlalchemy import select

from app.models import Job, utcnow
from app.modules.tasks.attempts import ExecutionAttempt, ExecutionSession, ExecutionUsage
from app.modules.tasks.models import RoundRecord, TaskRecord
from app.worker.leases import TERMINAL
from . import paths
from .state import HISTORY_AGE, aware, due, entry, touch


def _locked(session, resource_id):
    task = session.scalar(select(TaskRecord).where(TaskRecord.id == resource_id)
                          .with_for_update().execution_options(populate_existing=True))
    return task, entry(session, 'legacy_cli', resource_id)


def _idle(session, task):
    rounds = session.scalars(select(RoundRecord).where(RoundRecord.task_id == task.id)).all()
    for round in rounds:
        job = session.get(Job, round.job_id)
        if (round.status not in TERMINAL or not round.finished_at or not job
                or job.status not in TERMINAL or job.lease_until is not None):
            return False
    attempts = session.scalars(select(ExecutionAttempt).where(ExecutionAttempt.task_id == task.id)).all()
    if any(a.status != 'finished' or a.finished_at is None for a in attempts):
        return False
    from app.core.config import get_settings
    from app.execution.process import same_process
    for attempt in attempts:
        if attempt.process_id is None:
            continue
        if attempt.node != get_settings().worker_node_name or not all((attempt.boot_id, attempt.process_start)):
            return False
        try:
            if same_process(attempt.process_id, attempt.boot_id, attempt.process_start):
                return False
        except OSError:
            return False
    identity = session.get(ExecutionSession, task.id)
    return not identity or identity.status in ('ready', 'expired', 'cleaned')


def _expire(session, task, row, now):
    from .objects import queue_unused
    rounds = session.scalars(select(RoundRecord).where(RoundRecord.task_id == task.id)).all()
    annotations = {r.annotation_file_id for r in rounds if r.annotation_file_id}
    newly_cleaned = sum(not r.execution_config.get('historyExpired') for r in rounds)
    for round in rounds:
        round.note, round.error, round.annotation_file_id = '', None, None
        round.execution_config = {'historyExpired': True}
        job = session.get(Job, round.job_id)
        job.error, job.result = None, None
    attempts = session.scalars(select(ExecutionAttempt).where(ExecutionAttempt.task_id == task.id)).all()
    for attempt in attempts:
        attempt.workspace, attempt.node, attempt.cli_version = '', '', ''
        attempt.process_id = attempt.process_start = attempt.boot_id = None
        attempt.observation = attempt.error = None
        usage = session.get(ExecutionUsage, attempt.id)
        if usage:
            usage.data = {key: value for key, value in (usage.data or {}).items()
                          if key in ('input_tokens', 'output_tokens')
                          and type(value) is int and value >= 0} or None
    identity = session.get(ExecutionSession, task.id)
    if identity:
        identity.session_id, identity.status = None, 'expired'
    row.counters = {**(row.counters or {}), 'roundsCleared':
                    (row.counters or {}).get('roundsCleared', 0) + newly_cleaned}
    session.flush()
    queue_unused(session, 'originals', annotations, now)
    row.status, row.expired_at, row.next_cleanup_at = 'expired', now, None


def process(factory, store, root, resource_id, now=None):
    resource_id, now = UUID(str(resource_id)), now or utcnow()
    with factory.begin() as session:
        task, row = _locked(session, resource_id)
        if not task or task.execution_source != 'cli':
            return 'missing'
        if not row:
            touch(session, 'legacy_cli', task.id, now)
            return 'registered'
        action = due(row, now)
        if not action:
            return 'protected'
        if not _idle(session, task):
            row.next_cleanup_at = now + timedelta(hours=1)
            return 'active_execution'
        row.status, row.error = action, None
    # Persist the fence before any irreversible filesystem operation.
    try:
        with factory.begin() as session:
            task, row = _locked(session, resource_id)
            if not task or not row or row.status not in ('cache_pending', 'expire_pending'):
                return 'protected'
            if not _idle(session, task):
                return 'active_execution'
            cache = row.status == 'cache_pending'
            paths.clean(root, resource_id, cache_only=cache)
            if cache:
                row.status, row.cache_cleared_at = 'active', now
                row.next_cleanup_at = aware(row.last_activity_at) + HISTORY_AGE
            else:
                _expire(session, task, row, now)
            row.error = None
            return 'cache_cleared' if cache else 'expired'
    except Exception:
        with factory.begin() as session:
            _, row = _locked(session, resource_id)
            if row:
                row.error = '会话清理失败，等待自动重试'
                row.next_cleanup_at = now + timedelta(hours=1)
        return 'retry'
