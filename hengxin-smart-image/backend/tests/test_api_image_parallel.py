from datetime import timedelta
from uuid import UUID

from app.models import utcnow
from app.modules.api_image_edits.claims import claim
from app.modules.api_image_edits.execution import execute_next
from app.modules.api_image_edits.models import ApiItem
from app.modules.api_image_edits.relay import RelayError
from files_helpers import files_env
from test_api_image_domain import ROOT, create, enabled_api
from test_api_image_execution import Client, due


def test_waiting_retry_does_not_block_sibling_but_blocks_next_batch(files_env):
    web, factory, store, _ = files_env
    task_id, _ = create(web, 11)
    client = Client([RelayError('retryable', 'HTTP_503', 'safe')])
    assert execute_next(factory, store, client)
    first = web.get(ROOT + '/tasks/' + task_id).json()['items'][0]
    with factory.begin() as session:
        session.get(ApiItem, UUID(first['id'])).next_attempt_at = utcnow() + timedelta(hours=1)
    for _ in range(9):
        assert execute_next(factory, store, client)
    task = web.get(ROOT + '/tasks/' + task_id).json()
    assert task['items'][0]['state'] == 'retry_wait'
    assert all(item['state'] == 'succeeded' for item in task['items'][1:10])
    assert task['items'][10]['state'] == 'queued'
    assert claim(factory) is None
    due(factory)
    assert execute_next(factory, store, client)
    assert execute_next(factory, store, client)
    assert len(client.calls) == 12


def test_finished_timeout_call_retries_three_times_then_fails(files_env):
    web, factory, store, _ = files_env
    task_id, _ = create(web, 1)
    client = Client([RelayError('uncertain', 'REQUEST_UNCERTAIN', 'safe')] * 4)
    for index in range(4):
        before = utcnow()
        assert execute_next(factory, store, client)
        task = web.get(ROOT + '/tasks/' + task_id).json()
        item = task['items'][0]
        assert item['state'] == ('retry_wait' if index < 3 else 'failed')
        if index < 3:
            from datetime import datetime
            delay = (datetime.fromisoformat(item['nextAttemptAt']) - before).total_seconds()
            assert 2 ** index <= delay < 2 ** index + 2
        due(factory)
    assert len(client.calls) == 4
