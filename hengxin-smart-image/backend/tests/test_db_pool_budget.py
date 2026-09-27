from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from time import sleep
from types import SimpleNamespace

import pytest
from celery import Celery
from sqlalchemy import exc

from app.db import session as db
from app.db import worker_budget


def test_concurrent_first_access_builds_exactly_one_pool(monkeypatch):
    monkeypatch.setattr(db, '_engine', None)
    calls = []
    def create():
        sleep(.03)  # Reproduce concurrent lru_cache misses deterministically.
        engine = object()
        calls.append(engine)
        return engine
    monkeypatch.setattr(db, '_create_engine', create)
    barrier = Barrier(16)
    def first(_):
        barrier.wait()
        return db.get_engine()
    with ThreadPoolExecutor(max_workers=16) as pool:
        engines = list(pool.map(first, range(16)))
    assert len(calls) == 1 and all(engine is calls[0] for engine in engines)


def test_foreign_connection_is_detached_not_closed():
    record = SimpleNamespace(info={'pid': -1}, dbapi_connection=object())
    proxy = SimpleNamespace(dbapi_connection=record.dbapi_connection)
    with pytest.raises(exc.DisconnectionError):
        db._check_process(record.dbapi_connection, record, proxy)
    assert record.dbapi_connection is None and proxy.dbapi_connection is None


@pytest.mark.parametrize('concurrency,autoscale', [(6, None), (5, '6,1'), (5, (6, 1)), (5, 'invalid')])
def test_actual_celery_startup_rejects_budget_overrun(monkeypatch, concurrency, autoscale):
    monkeypatch.setattr(worker_budget, 'get_settings', lambda: SimpleNamespace(db_worker_process_limit=5))
    app = Celery('budget-test', broker='memory://')
    with pytest.raises(SystemExit, match='budget'):
        app.Worker(concurrency=concurrency, autoscale=autoscale, pool='solo', without_heartbeat=True)
    app.close()


def test_allowed_count_and_legacy_disabled_guard(monkeypatch):
    monkeypatch.setattr(worker_budget, 'get_settings', lambda: SimpleNamespace(db_worker_process_limit=5))
    worker_budget.validate_worker_budget(SimpleNamespace(concurrency=5, options={'autoscale': '5,1'}))
    monkeypatch.setattr(worker_budget, 'get_settings', lambda: SimpleNamespace(db_worker_process_limit=None))
    worker_budget.validate_worker_budget(SimpleNamespace(concurrency=20, options={}))
