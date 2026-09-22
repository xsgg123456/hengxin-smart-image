from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.models import utcnow
from app.modules.api_image_edits.claims import claim
from app.modules.api_image_edits.execution import execute_next
from app.modules.api_image_edits.heartbeat import renew
from app.modules.api_image_edits.models import ApiAttempt, ApiChannel, ApiItem
from app.modules.api_image_edits.relay import RelayError, RelayResult
from app.resource_models import UserRecord
from files_helpers import files_env, image_bytes
from test_api_image_domain import ROOT, create, enabled_api


class Client:
    def __init__(self, responses=None):
        self.calls = []
        self.responses = list(responses or [])

    def generate(self, *args):
        self.calls.append(args)
        response = self.responses.pop(0) if self.responses else RelayResult(image_bytes=image_bytes())
        if isinstance(response, Exception):
            raise response
        return response


def due(factory):
    with factory.begin() as session:
        for item in session.scalars(select(ApiItem)):
            item.next_attempt_at = utcnow() - timedelta(seconds=1)


def test_order_single_claim_success_and_message_replay(files_env):
    web, factory, store, _ = files_env
    task_id, payload = create(web)
    client = Client()
    first = claim(factory)
    assert first and claim(factory) is None
    # Expiry models process loss; it must block all further work, not resend.
    with factory.begin() as session:
        session.get(ApiChannel, 1).lease_until = utcnow() - timedelta(seconds=1)
    assert claim(factory) is None
    assert claim(factory) is None
    assert web.get(ROOT + '/tasks/' + task_id).json()['status'] == 'uncertain'
    assert execute_next(factory, store, client) is False
    assert not client.calls


def test_success_and_frozen_inputs_metrics(files_env):
    web, factory, store, _ = files_env
    task_id, payload = create(web)
    client = Client()
    assert execute_next(factory, store, client)
    assert execute_next(factory, store, client)
    assert execute_next(factory, store, client) is False
    assert len(client.calls) == 2
    assert all(args[4] == payload['prompt'] and args[5]['n'] == 1 for args in client.calls)
    task = web.get(ROOT + '/tasks/' + task_id).json()
    assert task['status'] == 'succeeded'
    assert task['metrics']['requestCount'] == 2
    assert task['metrics']['firstPassSuccessCount'] == 2
    assert all(web.get(i['result']['url']).content == image_bytes() for i in task['items'])


def test_missing_key_pauses_before_counting_network_attempt(files_env):
    from app.modules.api_image_edits.config import ApiImageSettings
    from app.modules.api_image_edits.relay import RelayClient
    web, factory, store, _ = files_env
    task_id, _ = create(web, 1)
    assert execute_next(factory, store, RelayClient(ApiImageSettings(_env_file=None, api_key='')))
    task = web.get(ROOT + '/tasks/' + task_id).json()
    assert task['metrics']['requestCount'] == 0
    assert task['status'] == 'failed'
    assert web.get(ROOT + '/status').json()['paused'] is True


def test_three_backoffs_then_continue_and_idempotent_manual_retry(files_env):
    web, factory, store, _ = files_env
    task_id, _ = create(web)
    client = Client([RelayError('retryable', 'HTTP_429', 'safe')] * 4)
    for index in range(4):
        assert execute_next(factory, store, client)
        task = web.get(ROOT + '/tasks/' + task_id).json()
        assert task['items'][0]['state'] == ('retry_wait' if index < 3 else 'failed')
        if index < 3:
            assert execute_next(factory, store, client) is False
            due(factory)
    assert execute_next(factory, store, client)
    task = web.get(ROOT + '/tasks/' + task_id).json()
    successful_result = task['items'][1]['result']
    assert task['status'] == 'partial_failed' and task['metrics']['requestCount'] == 5
    headers = {'Idempotency-Key': 'retry-one'}
    assert web.post(ROOT + '/tasks/' + task_id + '/retry', headers=headers).status_code == 202
    assert web.post(ROOT + '/tasks/' + task_id + '/retry', headers=headers).status_code == 202
    assert execute_next(factory, store, client)
    assert len(client.calls) == 6
    task = web.get(ROOT + '/tasks/' + task_id).json()
    assert task['status'] == 'succeeded' and task['items'][1]['result'] == successful_result


def test_download_and_storage_retries_never_regenerate(files_env):
    web, factory, store, _ = files_env
    task_id, _ = create(web, 1)
    client = Client([RelayResult(result_url='https://cdn3.dmiapi.com/private-result')])
    def broken(url):
        raise OSError('secret URL must never reach UI')
    assert execute_next(factory, store, client, broken)
    task = web.get(ROOT + '/tasks/' + task_id).json()
    assert task['items'][0]['state'] == 'collecting'
    assert 'private-result' not in str(task) and 'secret URL' not in str(task)
    due(factory)
    store.fail_put = True
    assert execute_next(factory, store, client, lambda _: image_bytes())
    due(factory)
    store.fail_put = False
    assert execute_next(factory, store, client, lambda _: image_bytes())
    assert len(client.calls) == 1
    assert web.get(ROOT + '/tasks/' + task_id).json()['status'] == 'succeeded'


def test_uncertain_admin_resolution_fences_late_worker(files_env):
    web, factory, store, identity = files_env
    task_id, _ = create(web, 1)
    client = Client([RelayError('uncertain', 'READ_TIMEOUT', 'safe')])
    assert execute_next(factory, store, client)
    assert execute_next(factory, store, client) is False
    url = ROOT + '/tasks/' + task_id
    assert web.delete(url).status_code == 409
    assert web.post(url + '/resolve', json={'confirmedStopped': True}).status_code == 403
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'super_admin'
    assert web.post(url + '/resolve', json={'confirmedStopped': False}).status_code == 422
    assert web.post(url + '/resolve', json={'confirmedStopped': True}).status_code == 200
    assert web.get(url).json()['status'] == 'failed'
    with factory() as session:
        attempt = session.scalar(select(ApiAttempt))
        assert attempt.resolved_by == identity[0]
        assert session.get(ApiChannel, 1).item_id is None


def test_channel_error_pause_and_live_resolve_denied(files_env):
    web, factory, store, identity = files_env
    task_id, _ = create(web, 1)
    first = claim(factory)
    with factory.begin() as session:
        session.get(UserRecord, identity[0]).role = 'super_admin'
    assert renew(factory, first[0], first[1])
    assert not renew(factory, first[0], uuid4())
    assert web.post(ROOT + '/tasks/' + task_id + '/resolve',
                    json={'confirmedStopped': True}).status_code == 409
    from app.modules.api_image_edits.outcomes import failure
    failure(factory, first[0], first[1], 'channel', 'HTTP_401')
    assert web.get(ROOT + '/status').json()['paused'] is True
    assert execute_next(factory, store, Client()) is False
    assert web.post(ROOT + '/channel/resume').status_code == 200


def test_collection_exhaustion_manual_retry_retains_receipt(files_env):
    web, factory, store, _ = files_env
    task_id, _ = create(web, 1)
    client = Client([RelayResult(result_url='https://cdn3.dmiapi.com/result')])
    def broken(url):
        raise OSError('download unavailable')
    for _ in range(4):
        assert execute_next(factory, store, client, broken)
        due(factory)
    assert web.get(ROOT + '/tasks/' + task_id).json()['status'] == 'failed'
    assert len(client.calls) == 1
    assert web.post(ROOT + '/tasks/' + task_id + '/retry',
                    headers={'Idempotency-Key': 'collect-again'}).status_code == 202
    assert execute_next(factory, store, client, lambda _: image_bytes())
    assert len(client.calls) == 1
    assert web.get(ROOT + '/tasks/' + task_id).json()['status'] == 'succeeded'


def test_invalid_result_and_permanent_failure_continue(files_env):
    web, factory, store, _ = files_env
    task_id, _ = create(web, 3)
    client = Client([RelayError('permanent', 'INVALID_REQUEST', 'safe'),
                     RelayResult(image_bytes=b'not an image')])
    for _ in range(3):
        assert execute_next(factory, store, client)
    task = web.get(ROOT + '/tasks/' + task_id).json()
    assert task['status'] == 'partial_failed'
    assert [i['state'] for i in task['items']] == ['failed', 'failed', 'succeeded']
    assert len(client.calls) == 3


def test_outbox_publish_failure_is_recoverable_and_duplicates_safe(files_env):
    from app.modules.api_image_edits.models import ApiDispatch
    from app.modules.api_image_edits.outbox import dispatch_once
    web, factory, store, _ = files_env
    task_id, _ = create(web, 1)
    def broken():
        raise OSError('broker unavailable')
    with pytest.raises(OSError):
        dispatch_once(factory, broken)
    with factory.begin() as session:
        row = session.get(ApiDispatch, UUID(task_id))
        assert row.dispatch_count == 1 and row.completed_at is None
        row.next_dispatch_at = utcnow() - timedelta(seconds=1)
    messages = []
    assert dispatch_once(factory, lambda: messages.append('wake'))
    assert messages == ['wake']
    client = Client()
    assert execute_next(factory, store, client)
    assert not execute_next(factory, store, client)
    assert not dispatch_once(factory, lambda: messages.append('wake'))
    assert len(client.calls) == 1
