"""Opt in with TEST_DATABASE_URL pointing to a disposable *_test database."""
import hashlib
import os
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta

import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings
from app.jobs import TestJobInput as JobInput, create_job
from app.models import Base, Job, Outbox, utcnow
from app.worker.outbox import dispatch_once
from app.worker.tasks import run_job

pytestmark = pytest.mark.integration


@pytest.fixture
def factory(monkeypatch):
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not configured")
    parsed = make_url(url)
    if not parsed.drivername.startswith("postgresql") or not (parsed.database or "").endswith("_test"):
        pytest.fail("Integration tests require a dedicated PostgreSQL database ending in _test")
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("ENABLE_TEST_JOBS", "true")
    get_settings.cache_clear()
    engine = create_engine(url)
    schema = 'test_queue_' + uuid4().hex
    with engine.begin() as conn:
        conn.execute(text(f'CREATE SCHEMA {schema}'))
    isolated = engine.execution_options(schema_translate_map={None: schema})
    Base.metadata.create_all(isolated)
    try:
        yield sessionmaker(isolated, expire_on_commit=False)
    finally:
        with engine.begin() as conn:
            conn.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        engine.dispose()
    get_settings.cache_clear()


def submit(factory, key="key", value="hello"):
    with factory() as session:
        return create_job(session, key, JobInput(value=value))


def test_concurrent_idempotency_and_payload_conflict(factory):
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = list(pool.map(lambda _: submit(factory), range(4)))
    assert len({job.id for job in jobs}) == 1
    with pytest.raises(HTTPException) as error:
        submit(factory, value="different")
    assert error.value.status_code == 409
    with factory() as session:
        assert len(session.scalars(select(Outbox)).all()) == 1


def test_publish_failure_rolls_back_and_lost_message_is_redispatched(factory):
    job = submit(factory)
    def unavailable(_):
        raise ConnectionError("broker unavailable")
    with pytest.raises(ConnectionError):
        dispatch_once(factory, unavailable)
    with factory() as session:
        assert session.get(Outbox, job.id).dispatch_count == 0
    sent = []
    assert dispatch_once(factory, sent.append) == 1
    with factory.begin() as session:
        session.get(Outbox, job.id).next_dispatch_at = utcnow() - timedelta(seconds=1)
    assert dispatch_once(factory, sent.append) == 1
    assert sent == [job.id, job.id]
    run_job(str(job.id), factory)
    with factory.begin() as session:
        session.get(Outbox, job.id).next_dispatch_at = utcnow() - timedelta(seconds=1)
    assert dispatch_once(factory, sent.append) == 0


def test_concurrent_delivery_only_commits_one_result(factory):
    job = submit(factory)
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda _: run_job(str(job.id), factory), range(4)))
    with factory() as session:
        saved = session.get(Job, job.id)
        assert saved.status == "succeeded"
        assert saved.execution_count == 1
        assert saved.result == hashlib.sha256(b"hello").hexdigest()
        assert session.get(Outbox, job.id).completed_at is not None


def test_computation_failure_rolls_back_and_retry_succeeds(factory, monkeypatch):
    job = submit(factory)
    def crash(_):
        raise RuntimeError("simulated process interruption")
    with monkeypatch.context() as patch:
        patch.setattr("app.worker.tasks.time.sleep", crash)
        with pytest.raises(RuntimeError):
            run_job(str(job.id), factory)
    with factory() as session:
        assert session.get(Job, job.id).status == "queued"
        assert session.get(Job, job.id).execution_count == 0
    run_job(str(job.id), factory)
    with factory() as session:
        assert session.get(Job, job.id).execution_count == 1
