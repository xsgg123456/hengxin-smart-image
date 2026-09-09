import logging
import signal
import threading
from datetime import timedelta

from sqlalchemy import and_, or_, select

from app.core.config import get_settings
from app.db.session import session_factory
from app.models import Job, Outbox, utcnow
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


def publish(job_id):
    celery_app.send_task("hengxin.job", args=[str(job_id)],
                         task_id=str(job_id), retry=False)


def dispatch_once(factory=None, sender=publish):
    factory = factory or session_factory()
    from app.modules.tasks.claims import sweep_expired
    sweep_expired(factory)
    with factory.begin() as session:
        rows = session.scalars(select(Outbox).join(Job, Job.id == Outbox.job_id).where(
            Outbox.completed_at.is_(None), Outbox.next_dispatch_at <= utcnow(),
            or_(Job.status == 'queued', and_(Job.kind != 'generation', Job.status == 'running')),
            or_(Job.lease_until.is_(None), Job.lease_until <= utcnow()),
        ).order_by(Outbox.next_dispatch_at).limit(100).with_for_update(of=Outbox, skip_locked=True)).all()
        for row in rows:
            sender(row.job_id)
            row.dispatch_count += 1
            # Never retire an outbox row merely because Redis acknowledged publish.
            row.next_dispatch_at = utcnow() + timedelta(
                seconds=get_settings().outbox_redispatch_seconds,
            )
        return len(rows)


def main():
    logging.basicConfig(level=logging.INFO)
    stopped = threading.Event()
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: stopped.set())
    while not stopped.is_set():
        try:
            dispatch_once()
        except Exception:
            # Avoid connection strings and credentials in container logs.
            logger.warning("Outbox dispatch unavailable; durable rows will be retried")
        stopped.wait(get_settings().outbox_poll_seconds)


if __name__ == "__main__":
    main()
