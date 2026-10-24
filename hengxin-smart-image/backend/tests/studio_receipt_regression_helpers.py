"""Manual receipt requests and genuine interrupted-worker fixtures."""
import pytest
import time
from unittest.mock import patch
from uuid import uuid4

from app.overseas.studio import delivery_job
from test_overseas_tasks import HEADERS


def native_request_bridge(factory, store):
    """Real native handler/DB/disk, replacing only the external Redis hop."""
    from app.overseas.studio import recovery_transport as transport
    def request(operation, actor_id, task_id, conversation_id, files=()):
        message = dict(id=str(uuid4()), operation=operation, actor_id=str(actor_id),
            task_id=str(task_id), conversation_id=str(conversation_id),
            expires_at=time.time() + 25, files=[item.model_dump() for item in files])
        return transport.handle_native(factory, message, store)
    return request


class WorkerInterrupted(BaseException):
    """A worker stops before its exception handler can settle the invocation."""


def interrupted(*_args, **_kwargs):
    raise WorkerInterrupted('worker terminated')


def stop_before_upload(case, monkeypatch):
    with monkeypatch.context() as patch:
        patch.setattr(delivery_job, 'upload', interrupted)
        with pytest.raises(WorkerInterrupted):
            case.run()
    assert case.current()['status'] == 'collecting'
    assert case.job().completed_at is None and case.job().process_exited
    assert case.count() == 0


def recoverable(case, source='snapshot'):
    url = case.root + '/conversations/' + case.turn['conversationId']
    with patch('app.overseas.studio.recovery_transport.request',
               native_request_bridge(case.factory, case.store)):
        response = case.client.get(url + '/recoverable-files')
    assert response.status_code == 200, response.text
    assert not response.json()['busy']
    return [item for item in response.json()['items'] if item['source'] == source]


def take(case, items=None, source='snapshot'):
    items = recoverable(case, source) if items is None else items
    assert items
    url = case.root + '/conversations/' + case.turn['conversationId']
    with patch('app.overseas.studio.recovery_transport.request',
               native_request_bridge(case.factory, case.store)):
        response = case.client.post(url + '/recover-files', headers=HEADERS,
            json={'files': [{key: item[key] for key in ('id', 'version')} for item in items]})
    assert response.status_code == 200, response.text
    result = response.json()
    assert result['errors'] == [], result
    assert len(result['saved']) == len(items), result
    return result['saved']


def partial(case, expected, saved):
    turn = case.current()
    assert turn['status'] == 'succeeded'
    assert turn['deliveryStatus'] == dict(state='partial', expected=expected, saved=saved)
    assert turn['deliveryError']
    assert case.view()['activeTurnId'] is None
    assert case.job().completed_at is not None and case.job().execution_count == 1
    assert len(case.commands) == 1
