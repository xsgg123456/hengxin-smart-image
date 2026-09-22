"""Run with python -m app.modules.api_image_edits.outbox; no CLI queue dependencies."""
from datetime import timedelta
import time

from sqlalchemy import select

from app.models import utcnow
from .config import get_api_settings
from .models import ApiDispatch, ApiTask


def dispatch_once(factory, publish):
    if not get_api_settings().enabled:
        return False
    with factory.begin() as session:
        row = session.scalar(select(ApiDispatch).join(ApiTask, ApiTask.id == ApiDispatch.id)
            .where(ApiDispatch.completed_at.is_(None), ApiTask.deleted_at.is_(None),
                   ApiDispatch.next_dispatch_at <= utcnow())
            .order_by(ApiTask.created_at, ApiTask.id).with_for_update(skip_locked=True).limit(1))
        if row is None:
            return False
        # Reserve briefly before publish. If publish or its acknowledgement is lost,
        # this row is automatically eligible again; database claims deduplicate delivery.
        row.next_dispatch_at = utcnow() + timedelta(seconds=2)
        row.dispatch_count += 1
    publish()
    return True


def main():
    from app.db.session import session_factory
    from .celery_app import execute
    while True:
        try:
            dispatch_once(session_factory(), lambda: execute.delay())
        except Exception:
            # No raw broker/DB exceptions: URLs can contain passwords.
            pass
        time.sleep(1)


if __name__ == '__main__':
    main()
