from contextlib import contextmanager
from datetime import timedelta
from threading import Event, Thread

from .claims import owned
from .config import get_api_settings
from .state import aware
from .retry_policy import database_now


def renew(factory, item_id, token):
    with factory.begin() as session:
        gate, item = owned(session, item_id, token)
        if not item or item.state not in {'running', 'collecting'}:
            return False
        now = database_now(session)
        if aware(item.lease_until) <= now:
            return False
        item.lease_until = now + timedelta(seconds=get_api_settings().lease_seconds)
        return True


@contextmanager
def heartbeat(factory, item_id, token):
    stopped = Event()
    interval = max(1, get_api_settings().lease_seconds / 3)

    def pulse():
        while not stopped.wait(interval):
            try:
                if not renew(factory, item_id, token):
                    return
            except Exception:
                # Never log connection errors (they may include deployment credentials).
                # The durable lease still fences this process if renewal cannot recover.
                continue

    thread = Thread(target=pulse, daemon=True, name='api-image-heartbeat')
    thread.start()
    try:
        yield
    finally:
        stopped.set()
        thread.join(timeout=1)
