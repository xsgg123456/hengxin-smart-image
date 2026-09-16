import os
import re
import shutil
import subprocess
import threading
from pathlib import Path
from celery.signals import worker_ready, worker_shutdown
from app.core.config import get_settings
from app.db.session import session_factory
from app.models import utcnow
from app.modules.tasks.attempts import WorkerHeartbeat
from app.worker.reconcile import reconcile_once

_stop = threading.Event()


def pulse(factory, concurrency=None):
    settings = get_settings()
    version = None
    try:
        result = subprocess.run([settings.codex_binary, '--version'], capture_output=True,
                                text=True, timeout=2)
        match = re.fullmatch(r'codex-cli ([0-9]+\.[0-9]+\.[0-9]+(?:[-.][a-zA-Z0-9.]+)?)',
                             result.stdout.strip())
        if result.returncode == 0 and match:
            version = match[1]
    except (OSError, subprocess.SubprocessError, UnicodeError):
        pass
    try:
        free = shutil.disk_usage(settings.codex_execution_root).free
    except OSError:
        free = None
    dependencies = {'cli': version == settings.codex_version,
                    'isolation': Path(settings.codex_bwrap_binary).is_file()
                    and os.access(settings.codex_bwrap_binary, os.X_OK),
                    'authenticationConfigured': Path(settings.codex_auth_file).is_file()
                    and os.access(settings.codex_auth_file, os.R_OK),
                    'cliVersion': version, 'freeDiskBytes': free,
                    'capacity': concurrency if type(concurrency) is int and concurrency > 0 else None,
                    'concurrency': concurrency if type(concurrency) is int and concurrency > 0 else None}
    ready = all(dependencies[key] for key in ('cli', 'isolation', 'authenticationConfigured'))
    with factory.begin() as session:
        session.merge(WorkerHeartbeat(node=settings.worker_node_name, checked_at=utcnow(),
            state='ready' if ready else 'unavailable', dependencies=dependencies))


@worker_ready.connect
def start_health(sender=None, **kwargs):
    if not get_settings().enable_codex_executor:
        return
    _stop.clear()
    def loop():
        while not _stop.is_set():
            try:
                factory = session_factory()
                pulse(factory, getattr(getattr(sender, 'pool', None), 'limit', None))
                reconcile_once(factory)
            except Exception:
                pass  # Stale checked_at exposes loss; never fabricate a fresh success.
            _stop.wait(5)
    threading.Thread(target=loop, daemon=True).start()


@worker_shutdown.connect
def stop_health(**kwargs):
    _stop.set()
