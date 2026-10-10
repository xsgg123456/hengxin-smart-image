"""Only the API Celery consumer publishes these heartbeats; no paid API probes."""
import threading
from celery.signals import worker_ready, worker_shutdown
from app.db.session import session_factory
from app.models import utcnow
from .config import get_api_settings
from .heartbeat_models import ApiWorkerHeartbeat

_stop = threading.Event()


def pulse(factory, node, capacity):
    config = get_api_settings()
    ready = config.enabled and bool(config.api_key.get_secret_value())
    with factory.begin() as session:
        session.merge(ApiWorkerHeartbeat(id=node, checked_at=utcnow(),
            state='ready' if ready else 'unavailable',
            capacity=capacity if type(capacity) is int and capacity > 0 else None))


@worker_ready.connect
def start_health(sender=None, **kwargs):
    if getattr(getattr(sender, 'app', None), 'main', None) != 'api_image_edits':
        return
    _stop.clear()
    node = str(sender.hostname)
    capacity = getattr(getattr(sender, 'pool', None), 'limit', None)

    def loop():
        while not _stop.is_set():
            try:
                pulse(session_factory(), node, capacity)
            except Exception:
                pass  # The last observation expires; never fabricate success.
            _stop.wait(5)
    threading.Thread(target=loop, daemon=True, name='api-worker-health').start()


@worker_shutdown.connect
def stop_health(sender=None, **kwargs):
    if getattr(getattr(sender, 'app', None), 'main', None) == 'api_image_edits':
        _stop.set()
