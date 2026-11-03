"""Two bounded API-side workers; jobs and leases survive all process restarts."""
from contextlib import asynccontextmanager
import logging
import os
from threading import Event, Thread
from types import SimpleNamespace
from uuid import uuid4
from app.core.config import get_settings
from app.overseas.db import session_factory
from app.storage.minio_store import get_store
from . import queue
from .transfer import TransferError, transfer

logger = logging.getLogger(__name__)


def run_job(factory, store, job):
    record = SimpleNamespace(id=uuid4(), bucket=get_settings().minio_bucket,
        object_key=f'materials/import-{job.id}/{job.lease_token}',
        content_type='application/octet-stream', size_bytes=0, checksum='')
    stopped, lost = Event(), Event()
    progress = [0]

    def heartbeat():
        while not stopped.wait(20):
            try:
                if not queue.renew(factory, job, progress[0]):
                    lost.set()
                    return
            except Exception:
                lost.set()
                return

    def advance(value):
        if lost.is_set():
            raise TransferError('附件导入已取消或租约到期')
        progress[0] = value

    thread = Thread(target=heartbeat, name='draft-import-lease', daemon=True)
    thread.start()
    uploaded = False
    try:
        transfer(job, record, store, advance)
        uploaded = True
        if not lost.is_set() and queue.complete(factory, job, record):
            return
    except Exception as error:
        safe = str(error) if isinstance(error, TransferError) else '附件导入失败，请重试'
        try:
            queue.fail(factory, job, safe)
        except Exception:
            logger.warning('Draft import result registration unavailable')
        # Unknown commit outcome: do not remove an object that may be referenced.
        return
    finally:
        stopped.set()
        thread.join(timeout=2)
    if uploaded:
        try:
            store.remove(record)
        except Exception:
            logger.warning('Cancelled draft import object cleanup unavailable')


def loop(stop):
    while not stop.is_set():
        try:
            factory = session_factory()
            job = queue.claim(factory)
            if job:
                run_job(factory, get_store(), job)
                continue
        except Exception:
            # Do not log exception strings: HTTP clients may include signed URLs.
            logger.warning('Draft import worker temporarily unavailable')
        stop.wait(3)


@asynccontextmanager
async def lifespan(app):
    stop, threads = Event(), []
    if os.environ.get('OVERSEAS_DESIGN_API_KEY', '').strip():
        threads = [Thread(target=loop, args=(stop,), name=f'draft-import-{index}', daemon=True)
                   for index in range(2)]
        for thread in threads:
            thread.start()
    try:
        yield
    finally:
        stop.set()
        # In-flight jobs keep heartbeating until process exit; a new process can
        # reclaim after the bounded lease, never while the original lease is live.
        for thread in threads:
            thread.join(timeout=1)
