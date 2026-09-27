"""Both Celery applications enforce the opt-in deployment process budget."""
from celery.signals import worker_init, worker_process_init

from app.core.config import get_settings
from app.db.session import reset_after_fork


@worker_init.connect
def validate_worker_budget(sender=None, **kwargs):
    limit = get_settings().db_worker_process_limit
    if limit is None:
        return
    count = getattr(sender, 'concurrency', None)
    # worker_init fires BEFORE Pool bootstep sets sender.autoscale.
    autoscale = (getattr(sender, 'options', {}) or {}).get('autoscale') or getattr(sender, 'autoscale', None)
    if isinstance(autoscale, str):
        try:
            autoscale = [int(value) for value in autoscale.split(',')]
        except ValueError:
            raise SystemExit('Invalid autoscale database budget') from None
    if (type(count) is not int or count < 1 or count > limit
            or (autoscale and (not isinstance(autoscale, (tuple, list))
                               or len(autoscale) != 2
                               or any(type(value) is not int or value < 0 or value > limit for value in autoscale)))):
        # Celery signals catch Exception; SystemExit must stop unsafe startup.
        raise SystemExit('Worker process count exceeds the configured database budget')


worker_process_init.connect(reset_after_fork, weak=False)
