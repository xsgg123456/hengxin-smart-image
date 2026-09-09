import hashlib
import time
from uuid import UUID

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import session_factory
from app.models import Job, Outbox, utcnow
from app.worker.celery_app import celery_app


def run_job(job_id: str, factory=None):
    settings = get_settings()
    if settings.app_env not in ("development", "test") or not settings.enable_test_jobs:
        raise RuntimeError("Test jobs are disabled")
    factory = factory or session_factory()
    with factory.begin() as session:
        job = session.scalar(select(Job).where(Job.id == UUID(job_id)).with_for_update())
        if job is None or job.status == "succeeded":
            return
        # Only a bounded, side-effect-free test computation runs under this lock.
        # Process death rolls back; duplicate messages wait then observe completion.
        # External AI/CLI effects cannot use this as an exactly-once guarantee.
        time.sleep(job.delay_seconds)
        job.result = hashlib.sha256(job.value.encode()).hexdigest()
        job.execution_count += 1
        job.status = "succeeded"
        job.completed_at = utcnow()
        session.get(Outbox, job.id).completed_at = job.completed_at


@celery_app.task(name="hengxin.test_job")
def execute_test_job(job_id: str):
    run_job(job_id)
