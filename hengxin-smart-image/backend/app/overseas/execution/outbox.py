"""Durable periodic delivery and local exit reconciliation."""
import logging
import signal
import threading
from app.core.config import get_settings
from app.overseas.db import require_overseas_context, session_factory
from .queue import dispatch_once
from .reconcile import reconcile_once


def main():
    require_overseas_context()
    stopped = threading.Event()
    for sig in (signal.SIGINT, signal.SIGTERM):
        signal.signal(sig, lambda *_: stopped.set())
    while not stopped.is_set():
        try:
            factory = session_factory()
            reconcile_once(factory)
            dispatch_once(factory)
        except Exception:
            logging.warning('Overseas execution maintenance unavailable; durable work retained')
        stopped.wait(get_settings().outbox_poll_seconds)


if __name__ == '__main__':
    main()
