import threading
from contextlib import contextmanager
from datetime import timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select

from app.core.config import get_settings
from app.models import Job, Outbox, utcnow

TERMINAL = ('succeeded', 'failed', 'cancelled')


def lease_active(job):
    return bool(job.lease_until and job.lease_until.replace(tzinfo=timezone.utc) > utcnow())


def claim(factory, job_id):
    with factory.begin() as session:
        job = session.scalar(select(Job).where(Job.id == UUID(str(job_id))).with_for_update())
        now = utcnow()
        if job is None or job.status in TERMINAL or lease_active(job):
            return None
        job.claim_token = uuid4()
        job.lease_until = now + timedelta(seconds=get_settings().job_lease_seconds)
        job.status = 'running'
        return job.claim_token


def renew(factory, job_id, token):
    with factory.begin() as session:
        job = session.scalar(select(Job).where(Job.id == UUID(str(job_id))).with_for_update())
        if not job or job.claim_token != token or job.status != 'running' or not lease_active(job):
            return False
        job.lease_until = utcnow() + timedelta(seconds=get_settings().job_lease_seconds)
        return True


@contextmanager
def heartbeat(factory, job_id, token):
    stopped = threading.Event()
    def beat():
        while not stopped.wait(get_settings().job_heartbeat_seconds):
            try:
                if not renew(factory, job_id, token):
                    return
            except Exception:
                return  # Expired ownership cannot publish a result.
    thread = threading.Thread(target=beat, daemon=True)
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=1)


def finish_job(session, job, status, error=None):
    job.status, job.error = status, error
    job.completed_at, job.lease_until = utcnow(), None
    job.execution_count += 1
    row = session.get(Outbox, job.id)
    if row:
        row.completed_at = job.completed_at
