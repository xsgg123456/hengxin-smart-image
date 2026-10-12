"""Unknown processes retain capacity; recovery never starts a replacement CLI."""
from sqlalchemy import select
from app.core.config import get_settings
from app.execution.process import same_process
from app.overseas.db import require_overseas_context
from . import claims
from .models import Job


def reconcile_once(factory):
    require_overseas_context()
    claims.sweep_expired(factory)
    node = get_settings().worker_node_name
    with factory() as session:
        rows = session.scalars(select(Job).where(Job.status == 'uncertain',
                                                 Job.worker_node == node)).all()
        session.expunge_all()
    count = 0
    for old in rows:
        if not old.process_exited:
            if not all((old.process_id, old.process_boot, old.process_started)):
                continue
            try:
                if same_process(old.process_id, old.process_boot, old.process_started):
                    continue
            except (OSError, ValueError):
                continue
        with factory.begin() as session:
            job = claims.locked_job(session, old.id)
            if (not job or job.status != 'uncertain' or job.claim_token != old.claim_token
                    or job.worker_node != node):
                continue
            job.process_exited = True
            # No recovery publication under an expired lease. Business retry must
            # explicitly create a new job after this original invocation is stopped.
            claims.end(session, job, 'cancelled' if job.cancel_requested else 'failed', error=True)
            count += 1
    return count
