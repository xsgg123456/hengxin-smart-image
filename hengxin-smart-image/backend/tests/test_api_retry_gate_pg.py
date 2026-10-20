"""Real PostgreSQL locks, with independent processes for shared send/probe gates."""
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from multiprocessing import Manager
from uuid import UUID

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from app.models import utcnow
from app.modules.api_image_edits.claims import claim, start_attempt
from app.modules.api_image_edits.config import get_api_settings
from app.modules.api_image_edits.limiter import occupancy
from app.modules.api_image_edits.models import ApiAttempt, ApiChannel, ApiItem
from app.modules.api_image_edits.outcomes import failure, save_response
from app.modules.api_image_edits.relay import RelayResult
from app.modules.api_image_edits.retry_policy import database_now
from app.modules.api_image_edits.retry_stop import stop
from app.modules.api_image_edits.service import submit
from app.modules.api_image_edits.state import aware
from files_helpers import image_bytes
from test_api_image_domain import enabled_api
from test_api_image_execution import due
from test_api_image_execution_pg import pg_api
from test_api_image_parallel_pg import task11

pytestmark = pytest.mark.integration


def separate_process_permission(args):
    url, schema, item, token, barrier = args
    engine = create_engine(url, connect_args={'options': f'-csearch_path={schema}'})
    try:
        barrier.wait(timeout=30)
        return start_attempt(sessionmaker(engine, expire_on_commit=False), UUID(item), UUID(token))
    finally:
        engine.dispose()


def process_permissions(factory, claims):
    with factory() as session:
        schema = session.scalar(text('SELECT current_schema()'))
    url = factory.kw['bind'].url.render_as_string(hide_password=False)
    with Manager() as manager:
        barrier = manager.Barrier(len(claims))
        args = [(url, schema, str(c[0]), str(c[1]), barrier) for c in claims]
        with ProcessPoolExecutor(max_workers=len(claims)) as pool:
            return list(pool.map(separate_process_permission, args))


def reset_wait(factory, cooldown=False):
    with factory.begin() as session:
        now = database_now(session)
        gate = session.get(ApiChannel, 1)
        gate.next_send_at = now - timedelta(seconds=1)
        if cooldown:
            gate.cooldown_until = now - timedelta(seconds=1)
        for row in session.scalars(select(ApiItem)):
            row.next_attempt_at = now - timedelta(seconds=1)


def test_global_five_second_permission_across_processes(pg_api, monkeypatch):
    factory, user, _, store = pg_api
    monkeypatch.setenv('API_IMAGE_SEND_INTERVAL_SECONDS', '5')
    get_api_settings.cache_clear()
    task11(factory, user, store)
    claims = [claim(factory) for _ in range(4)]
    assert sum(process_permissions(factory, claims)) == 1
    with factory() as session:
        gate = session.get(ApiChannel, 1)
        attempt = session.scalar(select(ApiAttempt))
        item = session.get(ApiItem, attempt.item_id)
        assert aware(gate.next_send_at) - aware(item.retry_started_at) == timedelta(seconds=5)
        assert item.attempts == 1
    reset_wait(factory)
    second = claim(factory)
    assert start_attempt(factory, *second[:2])
    assert not start_attempt(factory, *second[:2])  # Duplicate worker does not send twice.


def test_global_ten_inflight_releases_ended_unknown_and_ignores_old_audit(pg_api):
    factory, user, data, store = pg_api
    task11(factory, user, store)
    with factory() as session:
        other = submit(session, user, data, 'second')
    holds = [claim(factory) for _ in range(11)]
    assert all(holds)
    assert sum(start_attempt(factory, *value[:2]) for value in holds) == 10
    failure(factory, *holds[0][:2], 'uncertain', 'REQUEST_UNCERTAIN')
    with factory() as session:
        assert occupancy(session) == 9
    failure(factory, *holds[1][:2], 'permanent', 'INVALID_INPUT')
    reset_wait(factory)
    candidate = claim(factory)
    assert candidate and start_attempt(factory, *candidate[:2])
    with factory() as session:
        assert occupancy(session) == 9
    # Historical v1 uncertain entries attached to a terminal image remain audit only.
    failure(factory, *holds[2][:2], 'permanent', 'INVALID_INPUT')
    with factory.begin() as session:
        item = session.get(ApiItem, holds[2][0])
        session.add(ApiAttempt(item_id=item.id, operator_id=user.id, state='uncertain', completed_at=utcnow()))
    with factory() as session:
        assert occupancy(session) == 8


def test_single_probe_across_processes_old_unknown_and_late_success(pg_api):
    factory, user, _, store = pg_api
    task11(factory, user, store)
    holds = [claim(factory) for _ in range(7)]
    assert all(start_attempt(factory, *value[:2]) for value in holds)
    # Ended unknowns use the same failure threshold as retryable outcomes.
    failure(factory, *holds[0][:2], 'uncertain', 'REQUEST_UNCERTAIN')
    for value in holds[1:6]:
        failure(factory, *value[:2], 'retryable', 'HTTP_503')
    with factory() as session:
        gate = session.get(ApiChannel, 1)
        generation, cooldown = gate.generation, gate.cooldown_until
        assert generation == 1 and cooldown
    assert save_response(factory, *holds[6][:2], RelayResult(image_bytes=image_bytes()))
    with factory() as session:
        gate = session.get(ApiChannel, 1)
        assert gate.generation == generation and gate.cooldown_until == cooldown
    reset_wait(factory, cooldown=True)
    # Exclude collecting old success; collect its bytes without a new generation.
    candidates = []
    for _ in range(5):
        value = claim(factory)
        if value and value[2] == 'running':
            candidates.append(value)
    results = process_permissions(factory, candidates)
    assert sum(results) == 1
    probe = candidates[results.index(True)]
    with factory() as session:
        gate = session.get(ApiChannel, 1)
        assert gate.probe_attempt_id and occupancy(session) == 1
    failure(factory, *probe[:2], 'uncertain', 'REQUEST_UNCERTAIN')
    with factory() as session:
        gate = session.get(ApiChannel, 1)
        assert gate.generation == 2 and gate.probe_attempt_id is None
        assert occupancy(session) == 0  # Ended calls release their slots; cooldown stays.
    reset_wait(factory, cooldown=True)
    next_probe = claim(factory)
    assert next_probe and start_attempt(factory, *next_probe[:2])
    assert save_response(factory, *next_probe[:2], RelayResult(image_bytes=image_bytes()))
    with factory() as session:
        gate = session.get(ApiChannel, 1)
        assert gate.cooldown_until is None and gate.recovering and gate.recovery_limit == 1
    reset_wait(factory)
    one = claim(factory)
    assert one and start_attempt(factory, *one[:2])
    two = claim(factory)
    assert two and not start_attempt(factory, *two[:2])
    assert save_response(factory, *one[:2], RelayResult(image_bytes=image_bytes()))
    with factory() as session:
        assert session.get(ApiChannel, 1).recovery_limit == 2


def test_stop_races_final_permission_without_clearing_inflight(pg_api):
    factory, user, data, _ = pg_api
    with factory() as session:
        task = submit(session, user, data, 'stop-race')
    item, token, _ = claim(factory)
    barrier = Barrier(2)
    def sending():
        barrier.wait()
        return start_attempt(factory, item, token)
    def stopping():
        barrier.wait()
        with factory() as session:
            return stop(session, user, task, item, 'stop-key')
    with ThreadPoolExecutor(max_workers=2) as pool:
        sent, stopped = pool.submit(sending), pool.submit(stopping)
        permitted = sent.result()
        assert stopped.result() == task
    with factory() as session:
        row = session.get(ApiItem, item)
        assert row.stop_requested
        assert row.attempts == int(permitted)
        assert (row.state, bool(row.lease_token)) == (('running', True) if permitted else ('failed', False))
    assert not start_attempt(factory, item, token)
    if permitted:
        assert save_response(factory, item, token, RelayResult(image_bytes=image_bytes()))


def test_legacy_cycle_keeps_four_budget_and_expired_sent_claim_revokes_token(pg_api):
    factory, user, data, _ = pg_api
    with factory() as session:
        task = submit(session, user, data, 'legacy')
    with factory.begin() as session:
        row = session.scalar(select(ApiItem).where(ApiItem.task_id == task))
        row.retry_cycle_id, row.retry_policy_version = None, 'legacy-v1'
        row.max_attempts, row.cycle_retries = 4, 3
        for _ in range(4):
            session.add(ApiAttempt(item_id=row.id, operator_id=user.id, state='retryable', completed_at=utcnow()))
    assert claim(factory) is None
    with factory() as session:
        row = session.scalar(select(ApiItem).where(ApiItem.task_id == task))
        assert row.state == 'failed' and row.attempts == row.max_attempts == 4
    from app.modules.api_image_edits.versions import retry_item
    with factory() as session:
        retry_item(session, user, task, row.id, 'explicit-new')
    value = claim(factory)
    assert start_attempt(factory, *value[:2])
    with factory.begin() as session:
        session.get(ApiItem, value[0]).lease_until = database_now(session) - timedelta(seconds=1)
    assert claim(factory) is None
    with factory() as session:
        row = session.get(ApiItem, value[0])
        assert row.max_attempts == 20 and row.attempts == 1
        assert row.state == 'retry_wait' and row.lease_token is None
    assert not save_response(factory, *value[:2], RelayResult(image_bytes=image_bytes()))


def test_oversized_retry_after_survives_postgres_json_and_admin_resume(pg_api):
    from unittest.mock import Mock
    from fastapi.encoders import jsonable_encoder
    from app.modules.api_image_edits.config import ApiImageSettings
    from app.modules.api_image_edits.control import resume
    from app.modules.api_image_edits.execution import execute_next
    from app.modules.api_image_edits.relay import RelayClient
    from app.modules.api_image_edits.router import status
    from app.modules.api_image_edits.versions import retry_item
    from test_api_image_relay import response
    factory, user, data, store = pg_api
    with factory() as session:
        task_id = submit(session, user, data, 'long-header')
    pool = Mock()
    pool.request.return_value = response(429, headers={'Retry-After': '999999999999999'})
    relay = RelayClient(ApiImageSettings(_env_file=None, api_key='test-only'), pool)
    assert execute_next(factory, store, relay)
    with factory() as session:
        gate = session.get(ApiChannel, 1)
        assert gate.paused and gate.cooldown_until.year == 9999
        encoded = jsonable_encoder(status(user, session))
        assert encoded['cooldownUntil'].startswith('9999-12-31T23:59:59.999999')
        item = session.scalar(select(ApiItem).where(ApiItem.task_id == task_id))
        assert item.state == 'failed' and item.attempts == 1
        identifier = item.id
    with factory() as session:
        resume(session, user)
    with factory() as session:
        retry_item(session, user, task_id, identifier, 'manual-after-long-header')
    assert execute_next(factory, store, relay)
    assert pool.request.call_count == 1
    with factory() as session:
        row = session.get(ApiItem, identifier)
        assert row.attempts == 0 and row.retry_reason == 'cooldown'
        assert session.get(ApiChannel, 1).cooldown_until.year == 9999
