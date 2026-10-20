"""Production failure/collection paths define idle recovery data, not synthetic state."""
from uuid import UUID
import pytest
from sqlalchemy import select
from app.modules.api_image_edits import deletion
from app.modules.api_image_edits.claims import claim, start_attempt
from app.modules.api_image_edits.execution import execute_next
from app.modules.api_image_edits.outcomes import failure, save_response, collection_failure
from app.modules.api_image_edits.relay import RelayResult
from app.modules.api_image_edits.models import ApiAttempt, ApiItem
from files_helpers import files_env, image_bytes
from test_api_image_domain import ROOT, create, enabled_api
from test_api_image_execution import Client, due
from test_api_cli_conversation import cli_enabled


@pytest.mark.parametrize('kind', ['permanent', 'channel', 'retryable'])
def test_known_completed_attempts_allow_idle_deletion(files_env, cli_enabled, kind):
    client, factory, store, _ = files_env
    task_id, _ = create(client, count=1)
    claimed = claim(factory)
    assert start_attempt(factory, claimed[0], claimed[1])
    failure(factory, *claimed[:2], kind, 'isolated_failure')
    if kind == 'retryable':
        assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 409
        due(factory)
        assert execute_next(factory, store, Client())
    assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 202
    assert deletion.process(factory, store, task_id, cli_enabled) == 'deleted'


def test_unknown_attempt_protects_deletion_until_automatic_retry_finishes(files_env, cli_enabled):
    client, factory, store, _ = files_env
    task_id, _ = create(client, count=1)
    claimed = claim(factory)
    assert start_attempt(factory, *claimed[:2])
    failure(factory, *claimed[:2], 'uncertain', 'isolated_failure')
    assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 409
    with factory() as session:
        item = session.get(ApiItem, claimed[0])
        assert item.state == 'retry_wait' and item.lease_token is None
    assert not save_response(factory, *claimed[:2], RelayResult(image_bytes=image_bytes()))
    due(factory)
    relay = Client()
    assert execute_next(factory, store, relay)
    assert len(relay.calls) == 1
    assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 202
    assert deletion.process(factory, store, task_id, cli_enabled) == 'deleted'


def test_terminal_failed_collection_retains_inputs_but_no_execution(files_env, cli_enabled):
    client, factory, store, _ = files_env
    task_id, _ = create(client, count=1)
    claimed = claim(factory)
    assert start_attempt(factory, claimed[0], claimed[1])
    assert save_response(factory, *claimed[:2], RelayResult(image_bytes=image_bytes()))
    collection_failure(factory, *claimed[:2], permanent=True)
    with factory() as session:
        item = session.get(ApiItem, claimed[0])
        assert item.state == 'failed' and item.result_bytes and item.lease_token is None
    assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 202
    assert deletion.process(factory, store, task_id, cli_enabled) == 'deleted'


@pytest.mark.parametrize('state,finished', [('unknown', True), ('succeeded', False)])
def test_unknown_or_unfinished_attempt_remains_protected(files_env, state, finished):
    client, factory, store, _ = files_env
    task_id, _ = create(client, count=1)
    assert execute_next(factory, store, Client())
    with factory.begin() as session:
        attempt = session.scalar(select(ApiAttempt))
        attempt.state = state
        if not finished: attempt.completed_at = None
    assert client.delete(f'{ROOT}/tasks/{task_id}').status_code == 409
