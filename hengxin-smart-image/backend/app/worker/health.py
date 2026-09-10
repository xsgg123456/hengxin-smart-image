import os
import threading
from pathlib import Path
from celery.signals import worker_ready, worker_shutdown
from app.core.config import get_settings
from app.db.session import session_factory
from app.models import utcnow
from app.modules.tasks.attempts import WorkerHeartbeat
from app.worker.reconcile import reconcile_once

_stop = threading.Event()


def pulse(factory):
    settings = get_settings()
    dependencies = {'cli': Path(settings.codex_binary).is_file(),
                    'isolation': Path(settings.codex_bwrap_binary).is_file(),
                    'authenticationConfigured': Path(settings.codex_auth_file).is_file()}
    with factory.begin() as session:
        session.merge(WorkerHeartbeat(node=settings.worker_node_name, checked_at=utcnow(),
            state='ready' if all(dependencies.values()) else 'unavailable', dependencies=dependencies))


@worker_ready.connect
def start_health(**kwargs):
    if not get_settings().enable_codex_executor:
        return
    _stop.clear()
    def loop():
        while not _stop.is_set():
            try:
                factory = session_factory()
                pulse(factory)
                reconcile_once(factory)
            except Exception:
                pass  # Stale checked_at exposes loss; never fabricate a fresh success.
            _stop.wait(5)
    threading.Thread(target=loop, daemon=True).start()


@worker_shutdown.connect
def stop_health(**kwargs):
    _stop.set()
