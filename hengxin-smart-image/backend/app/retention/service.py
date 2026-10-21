"""Persist scan lifecycle and use a separate session for each heartbeat."""
from contextlib import contextmanager
from datetime import timedelta
from threading import Event, Thread
from sqlalchemy import delete, select
from app.models import utcnow
from .events import ensure_totals
from .observability_models import RetentionRecord, RetentionRun, RetentionService

HEARTBEAT_SECONDS = 30


def heartbeat(factory, next_scan=None, now=None):
    now = now or utcnow()
    with factory.begin() as session:
        if session.get_bind().dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        values = dict(heartbeat_at=now, updated_at=now)
        if next_scan is not None:
            values['next_scan_at'] = next_scan
        session.execute(insert(RetentionService).values(id='api_cli', **values)
            .on_conflict_do_update(index_elements=['id'], set_=values))


@contextmanager
def beating(factory):
    stop = Event()

    def loop():
        while not stop.wait(HEARTBEAT_SECONDS):
            try:
                heartbeat(factory)
            except Exception:
                pass  # A failed write must age out, never fabricate a heartbeat.

    heartbeat(factory)
    thread = Thread(target=loop, name='retention-heartbeat', daemon=True)
    thread.start()
    try:
        yield
    finally:
        stop.set()
        thread.join(timeout=5)


def begin_scan(factory, now):
    with factory.begin() as session:
        ensure_totals(session, now)
        # The native service owns the scanner. A previous crashed run stays visible as failed.
        for old in session.scalars(select(RetentionRun).where(
                RetentionRun.status == 'running', RetentionRun.started_at < now - timedelta(hours=2))):
            old.status, old.finished_at = 'failed', now
        row = RetentionRun(started_at=now, status='running')
        session.add(row)
        session.flush()
        return row.id


def end_scan(factory, identifier, status, now=None):
    now = now or utcnow()
    with factory.begin() as session:
        row = session.get(RetentionRun, identifier)
        row.status, row.finished_at = status, now
        cutoff = now - timedelta(days=90)
        session.execute(delete(RetentionRecord).where(RetentionRecord.completed_at < cutoff))
        session.execute(delete(RetentionRun).where(RetentionRun.finished_at < cutoff))
    heartbeat(factory, next_scan=now + timedelta(hours=1), now=now)
