"""Lease-fenced recovery of a stopped Studio invocation; never calls Codex."""
from datetime import timedelta
import logging
from pathlib import Path
from uuid import uuid4
from sqlalchemy import select

from app.core.config import get_settings
from app.db.timestamps import utcnow
from app.overseas.execution import claims
from app.overseas.execution.models import Job
from app.overseas.tasks.models import Task
from app.storage.minio_store import get_store
from . import delivery_context as context, delivery_job

log = logging.getLogger(__name__)


def recover(factory, old):
    """True means this invocation is owned by collection, including pending proof."""
    if old.kind != 'studio' or old.cancel_requested:
        return False
    try:
        owner = context.identity(old)
    except (ValueError, KeyError, TypeError):
        return False
    control = (Path(get_settings().codex_execution_root).absolute() / 'studio'
               / owner['conversationId'] / 'control' / owner['turnId'])
    if not (control / 'delivery-context.json').exists():
        return False  # Legacy jobs keep their existing reconciliation behavior.
    try:
        workspace = context.restore(old)
        summary = context.success(workspace)
    except context.UnsuccessfulCompletion:
        return False  # Reconciliation can end a proven failed, stopped process.
    except FileNotFoundError:
        # An absent exit receipt is not proof of success or a reason to regenerate.
        return True
    except ValueError:
        log.warning('Studio completion evidence unavailable job=%s', old.id)
        return True
    with factory.begin() as session:
        session.scalar(select(Task).where(Task.id == old.task_id).with_for_update())
        current = claims.locked_job(session, old.id)
        if (not current or current.status != 'uncertain' or current.claim_token != old.claim_token
                or current.cancel_requested or current.worker_node != get_settings().worker_node_name):
            return True
        current.claim_token = token = uuid4()
        current.status, current.process_exited = 'collecting', True
        current.lease_until = utcnow() + timedelta(seconds=get_settings().job_lease_seconds)
        current.error = None
        current.version += 1
        from app.overseas.execution.events import record
        record(session, current)
        session.flush()
        session.expunge(current)
    from app.overseas.execution.runner import heartbeat
    try:
        with heartbeat(factory, current.id, token, get_settings()):
            delivery_job.deliver(factory, current, token, workspace, summary, get_store(), recovering=True)
    except delivery_job.OwnershipLost:
        pass
    except Exception:
        log.warning('Studio delivery recovery pending job=%s', old.id)
        try:
            delivery_job.finish_failed(factory, old.id, token, summary)
        except delivery_job.OwnershipLost:
            pass
    return True
