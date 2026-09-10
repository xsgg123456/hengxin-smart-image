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
        if job is None or job.status in ('succeeded', 'partial', 'failed', 'cancelled'):
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


@celery_app.task(name='hengxin.job')
def execute_job(job_id: str):
    factory = session_factory()
    with factory() as session:
        job = session.get(Job, UUID(job_id))
        kind = job.kind if job else None
    if kind == 'test':
        run_job(job_id, factory)
    elif kind == 'generation':
        from app.modules.tasks.models import RoundRecord, TaskRecord
        with factory() as session:
            round = session.scalar(select(RoundRecord).where(RoundRecord.job_id == UUID(job_id)))
            task = session.get(TaskRecord, round.task_id) if round else None
            source = task.execution_source if task else None
        if source == 'cli':
            from app.execution.codex_runner import run_generation
        elif source == 'fixture':
            from app.execution.fixture_runner import run_generation
        else:
            return
        run_generation(job_id, factory)
    elif kind == 'skill_install':
        from app.worker.skill_install import run_install
        run_install(job_id, factory)
    elif kind is not None:
        from app.worker.leases import finish_job
        with factory.begin() as session:
            job = session.scalar(select(Job).where(Job.id == UUID(job_id)).with_for_update())
            if job.status not in ('succeeded', 'partial', 'failed', 'cancelled'):
                finish_job(session, job, 'failed', '未知作业类型')
