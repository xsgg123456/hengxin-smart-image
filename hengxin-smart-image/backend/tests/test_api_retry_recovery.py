"""Existing unknown records recover without resetting budgets or frozen input."""
from datetime import timedelta
import pytest
from sqlalchemy import select

from app.models import utcnow
from app.modules.api_image_edits.claims import claim, start_attempt
from app.modules.api_image_edits.execution import execute_next
from app.modules.api_image_edits.models import ApiAttempt, ApiChannel, ApiItem
from app.modules.api_image_edits.outcomes import failure, save_response
from app.modules.api_image_edits.relay import RelayResult
from app.modules.api_image_edits.state import aware
from files_helpers import files_env, image_bytes
from test_api_image_domain import ROOT, create, enabled_api
from test_api_image_execution import Client, due


def expired(factory, state='running'):
    value = claim(factory)
    assert start_attempt(factory, *value[:2])
    with factory.begin() as session:
        item = session.get(ApiItem, value[0])
        item.state, item.lease_until = state, utcnow() - timedelta(seconds=1)
        if state == 'uncertain':
            attempt = session.scalar(select(ApiAttempt).where(ApiAttempt.item_id == item.id))
            attempt.state, attempt.completed_at = 'uncertain', utcnow()
    return value


@pytest.mark.parametrize('state', ['running', 'uncertain'])
def test_recovery_retains_cycle_deadline_capacity_and_one_backoff(files_env, state):
    web, factory, store, _ = files_env
    task_id, _ = create(web, 1)
    item_id, token, _ = expired(factory, state)
    with factory() as session:
        item = session.get(ApiItem, item_id)
        frozen = (item.retry_cycle_id, item.retry_policy_version, item.attempts,
                  item.retry_started_at, item.retry_deadline_at, item.capacity_cycle_id, item.revision_snapshot)
    assert claim(factory) is None
    with factory() as session:
        item = session.get(ApiItem, item_id)
        assert item.state == 'retry_wait' and item.lease_token is None
        assert frozen == (item.retry_cycle_id, item.retry_policy_version, item.attempts,
                          item.retry_started_at, item.retry_deadline_at, item.capacity_cycle_id, item.revision_snapshot)
        next_attempt = item.next_attempt_at
        assert item.cycle_retries == 1
        assert session.scalar(select(ApiAttempt)).state == 'uncertain'
    assert claim(factory) is None
    with factory() as session:
        item = session.get(ApiItem, item_id)
        assert item.next_attempt_at == next_attempt and item.cycle_retries == 1
    assert not start_attempt(factory, item_id, token)
    assert not save_response(factory, item_id, token, RelayResult(image_bytes=image_bytes()))
    due(factory)
    assert execute_next(factory, store, Client())
    assert web.get(f'{ROOT}/tasks/{task_id}').json()['items'][0]['retry']['attempts'] == 2


@pytest.mark.parametrize('state', ['running', 'uncertain'])
def test_valid_lease_is_never_recovered_even_when_stopped_or_deadline_elapsed(files_env, state):
    web, factory, _, _ = files_env
    create(web, 1)
    item_id, token, _ = claim(factory)
    assert start_attempt(factory, item_id, token)
    with factory.begin() as session:
        item = session.get(ApiItem, item_id)
        item.state, item.stop_requested = state, True
        item.retry_deadline_at = utcnow() - timedelta(seconds=1)
    assert claim(factory) is None
    with factory() as session:
        item = session.get(ApiItem, item_id)
        assert item.state == state and item.lease_token == token
        assert session.scalar(select(ApiAttempt)).state == 'running'
    assert save_response(factory, item_id, token, RelayResult(image_bytes=image_bytes()))


@pytest.mark.parametrize('reason', ['user_stopped', 'deadline_exceeded', 'attempts_exhausted'])
@pytest.mark.parametrize('state', ['running', 'uncertain'])
def test_expired_unknown_respects_original_end_conditions(files_env, reason, state):
    web, factory, _, _ = files_env
    create(web, 1)
    item_id, token, _ = expired(factory, state)
    with factory.begin() as session:
        item = session.get(ApiItem, item_id)
        if reason == 'user_stopped':
            item.stop_requested = True
        elif reason == 'deadline_exceeded':
            item.retry_deadline_at = utcnow() - timedelta(seconds=1)
        else:
            item.attempts = item.max_attempts
        cycle = item.retry_cycle_id
    assert claim(factory) is None
    with factory() as session:
        item = session.get(ApiItem, item_id)
        assert item.state == 'failed' and item.retry_reason == reason
        assert item.retry_cycle_id == cycle and item.lease_token is None
        assert session.scalar(select(ApiAttempt)).completed_at


@pytest.mark.parametrize('state', ['running', 'uncertain'])
@pytest.mark.parametrize('receipt', ['result_url', 'result_bytes'])
def test_persisted_result_wins_stop_deadline_pause_and_budget(files_env, state, receipt):
    web, factory, store, _ = files_env
    task_id, _ = create(web, 1)
    item_id, token, _ = expired(factory, state)
    with factory.begin() as session:
        item = session.get(ApiItem, item_id)
        setattr(item, receipt, image_bytes() if receipt == 'result_bytes' else 'https://example.test/result')
        item.stop_requested, item.attempts = True, item.max_attempts
        item.retry_deadline_at = utcnow() - timedelta(seconds=1)
        session.get(ApiChannel, 1).paused = True
    client = Client()
    assert execute_next(factory, store, client, lambda _: image_bytes())
    assert not client.calls
    item = web.get(f'{ROOT}/tasks/{task_id}').json()['items'][0]
    assert item['state'] == 'succeeded' and item['retry']['attempts'] == 20
    assert not save_response(factory, item_id, token, RelayResult(image_bytes=image_bytes()))


def test_legacy_unknown_keeps_four_attempt_limit_and_historical_audit(files_env):
    web, factory, _, _ = files_env
    create(web, 1)
    item_id, _, _ = expired(factory, 'uncertain')
    with factory.begin() as session:
        item = session.get(ApiItem, item_id)
        item.retry_cycle_id, item.retry_policy_version = None, 'legacy-v1'
        item.cycle_retries = 4
    assert claim(factory) is None
    with factory() as session:
        item = session.get(ApiItem, item_id)
        assert item.attempts == item.max_attempts == 4 and item.state == 'failed'
        attempt = session.scalar(select(ApiAttempt))
        audit = (attempt.state, attempt.completed_at, attempt.error, attempt.retry_cycle_id)
    assert claim(factory) is None
    with factory() as session:
        attempt = session.scalar(select(ApiAttempt))
        assert audit == (attempt.state, attempt.completed_at, attempt.error, attempt.retry_cycle_id)


def test_local_unknown_end_releases_token_and_opens_existing_cooldown(files_env):
    web, factory, _, _ = files_env
    create(web, 5)
    for _ in range(5):
        item_id, token, _ = claim(factory)
        assert start_attempt(factory, item_id, token)
        failure(factory, item_id, token, 'uncertain', 'REQUEST_UNCERTAIN')
    with factory() as session:
        gate = session.get(ApiChannel, 1)
        assert gate.failure_streak == 5 and aware(gate.cooldown_until) > utcnow()
        assert all(item.state == 'retry_wait' and item.lease_token is None
                   for item in session.scalars(select(ApiItem)))
        assert all(a.state == 'uncertain' and a.completed_at
                   for a in session.scalars(select(ApiAttempt)))


def test_successful_image_old_unknown_audit_is_never_recovered(files_env):
    web, factory, store, identity = files_env
    task_id, _ = create(web, 1)
    assert execute_next(factory, store, Client())
    with factory.begin() as session:
        item = session.scalar(select(ApiItem))
        result_id, version = item.result_id, item.current_version
        old = ApiAttempt(item_id=item.id, operator_id=identity[0], state='uncertain',
                         completed_at=utcnow(), error='historical')
        session.add(old)
        session.flush()
        old_id, finished = old.id, old.completed_at
    assert claim(factory) is None
    with factory() as session:
        old = session.get(ApiAttempt, old_id)
        assert old.state == 'uncertain' and aware(old.completed_at) == finished and old.error == 'historical'
        item = session.scalar(select(ApiItem))
        assert item.result_id == result_id and item.current_version == version and item.state == 'succeeded'


def test_expired_preflight_does_not_recount_older_unknown_failure(files_env):
    web, factory, _, _ = files_env
    create(web, 1)
    item_id, token, _ = claim(factory)
    assert start_attempt(factory, item_id, token)
    failure(factory, item_id, token, 'uncertain', 'REQUEST_UNCERTAIN')
    due(factory)
    second = claim(factory)
    with factory.begin() as session:
        session.get(ApiItem, item_id).lease_until = utcnow() - timedelta(seconds=1)
    assert not start_attempt(factory, *second[:2])
    third = claim(factory)
    assert third and third[1] != second[1]
    with factory() as session:
        assert session.get(ApiChannel, 1).failure_streak == 1
        item = session.get(ApiItem, item_id)
        assert item.attempts == 1 and item.cycle_retries == 1
        assert session.scalar(select(ApiAttempt)).state == 'uncertain'


def test_retry_preflight_failure_does_not_overwrite_finished_unknown_audit(files_env):
    web, factory, _, _ = files_env
    create(web, 1)
    item_id, token, _ = claim(factory)
    assert start_attempt(factory, item_id, token)
    failure(factory, item_id, token, 'uncertain', 'REQUEST_UNCERTAIN')
    with factory() as session:
        attempt = session.scalar(select(ApiAttempt))
        completed = attempt.completed_at
    due(factory)
    second = claim(factory)
    failure(factory, *second[:2], 'permanent', 'INVALID_INPUT')
    with factory() as session:
        attempt = session.scalar(select(ApiAttempt))
        assert attempt.state == 'uncertain' and attempt.error == 'REQUEST_UNCERTAIN'
        assert attempt.completed_at == completed
        assert session.get(ApiItem, item_id).state == 'failed'

