from datetime import datetime, timedelta
from uuid import UUID

import pytest
from sqlalchemy import select

from app.models import utcnow
from app.modules.api_image_edits.claims import claim, start_attempt
from app.modules.api_image_edits.config import get_api_settings
from app.modules.api_image_edits.execution import execute_next
from app.modules.api_image_edits.models import ApiAttempt, ApiChannel, ApiItem
from app.modules.api_image_edits.outcomes import failure, save_response
from app.modules.api_image_edits.relay import RelayError, RelayResult, retry_after_seconds
from app.modules.api_image_edits.state import aware
from files_helpers import files_env, image_bytes
from test_api_image_domain import ROOT, create, enabled_api
from test_api_image_execution import Client, due


def current(web, task_id):
    return web.get(f'{ROOT}/tasks/{task_id}').json()['items'][0]


def test_twenty_attempts_never_twenty_one_and_manual_new_cycle(files_env, monkeypatch):
    web, factory, store, _ = files_env
    monkeypatch.setenv('API_IMAGE_FAILURE_THRESHOLD', '20')
    get_api_settings.cache_clear()
    task_id, _ = create(web, 1)
    cycle = current(web, task_id)['retry']['cycleId']
    client = Client([RelayError('retryable', 'HTTP_503', 'safe')] * 20)
    for index in range(20):
        assert execute_next(factory, store, client)
        item = current(web, task_id)
        assert item['retry']['attempts'] == index + 1
        assert item['state'] == ('failed' if index == 19 else 'retry_wait')
        if index < 19:
            before = item['nextAttemptAt']
            assert not execute_next(factory, store, client)
            assert current(web, task_id)['nextAttemptAt'] == before
            due(factory)
    assert not execute_next(factory, store, client)
    assert len(client.calls) == 20
    retry = f"{ROOT}/tasks/{task_id}/items/{item['id']}/retry"
    assert web.post(retry, headers={'Idempotency-Key': 'new-cycle'}).status_code == 202
    assert web.post(retry, headers={'Idempotency-Key': 'new-cycle'}).status_code == 202
    assert web.post(retry, headers={'Idempotency-Key': 'competing'}).status_code == 409
    item = current(web, task_id)
    assert item['retry']['cycleId'] != cycle and item['retry']['attempts'] == 0
    assert item['retry']['startedAt'] is None
    # Manual retry cannot bypass the cooling circuit.
    assert execute_next(factory, store, client)
    assert len(client.calls) == 20


def test_deadline_is_first_send_and_prevents_new_post(files_env):
    web, factory, store, _ = files_env
    task_id, _ = create(web, 1)
    item = current(web, task_id)
    assert item['retry']['startedAt'] is None
    client = Client([RelayError('retryable', 'HTTP_503', 'safe')])
    execute_next(factory, store, client)
    item = current(web, task_id)
    start = datetime.fromisoformat(item['retry']['startedAt'])
    assert datetime.fromisoformat(item['retry']['deadlineAt']) - start == timedelta(minutes=45)
    with factory.begin() as session:
        row = session.get(ApiItem, UUID(item['id']))
        row.retry_deadline_at = utcnow() - timedelta(seconds=1)
        row.next_attempt_at = utcnow() - timedelta(seconds=1)
    assert not execute_next(factory, store, client)
    assert current(web, task_id)['state'] == 'failed'
    assert '45' in current(web, task_id)['retry']['reason']
    assert len(client.calls) == 1


@pytest.mark.parametrize('sent', [False, True])
def test_stop_before_send_or_after_send_retains_late_success(files_env, sent):
    web, factory, store, _ = files_env
    task_id, _ = create(web, 1)
    item_id, token, _ = claim(factory)
    if sent:
        assert start_attempt(factory, item_id, token)
    endpoint = f'{ROOT}/tasks/{task_id}/items/{item_id}/stop'
    assert web.post(endpoint, headers={'Idempotency-Key': 'stop'}).status_code == 202
    assert web.post(endpoint, headers={'Idempotency-Key': 'stop'}).status_code == 202
    assert not start_attempt(factory, item_id, token)
    item = current(web, task_id)
    assert item['retry']['stopRequested']
    if sent:
        assert item['state'] == 'running'
        assert web.delete(f'{ROOT}/tasks/{task_id}').status_code == 409
        assert save_response(factory, item_id, token, RelayResult(image_bytes=image_bytes(), request_id='req-1'))
        from app.modules.api_image_edits.execution import collect
        collect(factory, store, item_id, token, lambda _: b'')
        assert current(web, task_id)['state'] == 'succeeded'
        with factory() as session:
            assert session.scalar(select(ApiAttempt)).request_id == 'req-1'
    else:
        assert item['state'] == 'failed'
        assert item['retry']['attempts'] == 0


def test_unknown_not_retried_and_does_not_block_unrelated_send(files_env):
    web, factory, store, _ = files_env
    task_id, _ = create(web, 2)
    client = Client([RelayError('uncertain', 'REQUEST_UNCERTAIN', 'safe')])
    assert execute_next(factory, store, client)
    item = current(web, task_id)
    assert item['state'] == 'uncertain'
    assert execute_next(factory, store, client)
    due(factory)
    assert not execute_next(factory, store, client)
    assert len(client.calls) == 2
    assert web.post(f"{ROOT}/tasks/{task_id}/items/{item['id']}/retry",
                    headers={'Idempotency-Key': 'unknown'}).status_code == 409
    with factory() as session:
        row = session.get(ApiItem, UUID(item['id']))
        assert row.lease_token and row.attempts == 1


def test_retry_after_long_value_and_durable_jitter(files_env):
    web, factory, store, _ = files_env
    task_id, _ = create(web, 1)
    before = utcnow()
    client = Client([RelayError('retryable', 'HTTP_429', 'safe', 90000)])
    execute_next(factory, store, client)
    item = current(web, task_id)
    due_at = datetime.fromisoformat(item['nextAttemptAt'])
    assert due_at >= before + timedelta(seconds=90000)
    with factory() as session:
        assert aware(session.get(ApiChannel, 1).cooldown_until) >= before + timedelta(seconds=90000)
    assert retry_after_seconds('90000') == 90000
    assert not execute_next(factory, store, client)
    assert current(web, task_id)['nextAttemptAt'] == item['nextAttemptAt']


def test_equal_jitter_ranges_and_http_date_rounds_up(monkeypatch):
    from types import SimpleNamespace
    from app.modules.api_image_edits.retry_policy import retry_delay
    for attempt, low, high in [(1, 5, 10), (2, 10, 20), (3, 20, 40), (4, 30, 60), (19, 30, 60)]:
        item = SimpleNamespace(attempts=attempt, retry_policy_version='bounded-v2')
        assert all(low <= retry_delay(item) <= high for _ in range(30))
    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 20, 0, 0, 0, 700000, tzinfo=tz)
    monkeypatch.setattr('app.modules.api_image_edits.relay.datetime', FrozenDatetime)
    assert retry_after_seconds('Tue, 20 Oct 2026 00:00:01 GMT') == 1
    with pytest.raises(RelayError) as error:
        retry_after_seconds('999999999999999')
    assert error.value.kind == 'channel'


def test_serialization_is_finished_before_permission(files_env):
    web, factory, store, _ = files_env
    task_id, _ = create(web, 1)
    class PreparedClient:
        def prepare(self, *args):
            assert current(web, task_id)['retry']['attempts'] == 0
            return b'serialized'
        def send_prepared(self, body):
            assert body == b'serialized'
            assert current(web, task_id)['retry']['attempts'] == 1
            return RelayResult(image_bytes=image_bytes())
    assert execute_next(factory, store, PreparedClient())
    assert current(web, task_id)['state'] == 'succeeded'


def test_http_date_uses_database_clock_and_error_request_id_is_private(files_env):
    web, factory, store, _ = files_env
    task_id, _ = create(web, 1)
    deadline = utcnow() + timedelta(minutes=2)
    client = Client([RelayError('retryable', 'HTTP_503', 'safe', 1,
                               request_id='upstream-private-id', retry_after_at=deadline)])
    execute_next(factory, store, client)
    item = current(web, task_id)
    assert datetime.fromisoformat(item['nextAttemptAt']) >= deadline
    with factory() as session:
        assert session.scalar(select(ApiAttempt)).request_id == 'upstream-private-id'
        assert aware(session.get(ApiChannel, 1).cooldown_until) >= deadline
    assert 'upstream-private-id' not in str(web.get(f'{ROOT}/tasks/{task_id}').json())


def test_already_sent_result_survives_deadline_and_manual_pause(files_env):
    web, factory, store, _ = files_env
    task_id, _ = create(web, 1)
    item_id, token, _ = claim(factory)
    assert start_attempt(factory, item_id, token)
    with factory.begin() as session:
        session.get(ApiItem, item_id).retry_deadline_at = utcnow() - timedelta(seconds=1)
        session.get(ApiChannel, 1).paused = True
    assert save_response(factory, item_id, token, RelayResult(image_bytes=image_bytes()))
    from app.modules.api_image_edits.execution import collect
    collect(factory, store, item_id, token, lambda _: b'')
    assert current(web, task_id)['state'] == 'succeeded'
    assert current(web, task_id)['retry']['attempts'] == 1
