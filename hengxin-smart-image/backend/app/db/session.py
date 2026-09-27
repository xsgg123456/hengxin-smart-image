import os
from threading import Lock

from sqlalchemy import create_engine, event, exc
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings


_engine = None
_engine_pid = os.getpid()
_engine_lock = Lock()


def reset_after_fork(**kwargs):
    """Replace inherited pool/lock without closing the parent's live sockets."""
    global _engine_pid, _engine_lock
    if _engine_pid == os.getpid():
        return
    _engine_lock = Lock()  # A vanished parent thread may have owned the old lock.
    if _engine is not None:
        _engine.dispose(close=False)
    _engine_pid = os.getpid()


if hasattr(os, 'register_at_fork'):
    os.register_at_fork(after_in_child=reset_after_fork)


def _record_process(connection, record):
    record.info['pid'] = os.getpid()


def _check_process(connection, record, proxy):
    if record.info.get('pid') != os.getpid():
        record.dbapi_connection = proxy.dbapi_connection = None
        raise exc.DisconnectionError('Database connection belongs to another process')


def _create_engine():
    settings = get_settings()
    engine = create_engine(
        settings.database_url, pool_pre_ping=True, pool_timeout=3,
        pool_size=settings.db_pool_size, max_overflow=settings.db_max_overflow,
        connect_args={"connect_timeout": 3, "options": "-c statement_timeout=45000",
                      "application_name": settings.db_application_name},
    )
    event.listen(engine, 'connect', _record_process)
    event.listen(engine, 'checkout', _check_process)
    return engine


def get_engine():
    global _engine
    reset_after_fork()
    # lru_cache may evaluate concurrent first misses more than once. Serialize
    # construction so a process has exactly one pool, including cold starts.
    with _engine_lock:
        if _engine is None:
            _engine = _create_engine()
        return _engine


def session_factory():
    return sessionmaker(get_engine(), expire_on_commit=False)


def get_session():
    with session_factory()() as session:
        yield session
