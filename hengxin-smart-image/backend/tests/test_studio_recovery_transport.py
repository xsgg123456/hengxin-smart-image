"""The API owns no original files; only the native consumer can read/save them."""
import json
import time
from uuid import UUID, uuid4

import pytest
from fastapi import HTTPException
from redis.exceptions import ConnectionError

from app.core.config import get_settings
from app.overseas.execution.models import Job
from app.overseas.studio import recovery_listing, recovery_transport as transport
from app.overseas.studio.models import OutputFile
from test_overseas_assignment import change_roles
from test_overseas_studio_file_recovery import missed, studio, materials, overseas, listed, take, count

REQUEST = transport.request


class MemoryRedis:
    """Only the metadata transport is fake; native SQL, filesystem and receipt are real."""
    def __init__(self):
        self.values, self.pending, self.writes, self.ttls = {}, [], [], {}
        self.poll = None

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def eval(self, script, nkeys, queue, key, identity, raw, limit, ttl):
        assert script == transport.ENQUEUE and nkeys == 2 and queue == transport.QUEUE
        if len(self.pending) >= limit:
            return 0
        self.set(key, raw, ex=ttl)
        self.pending.append(identity)
        self.ttls[queue] = ttl
        return 1

    def get(self, key):
        if ':response:' in key and self.poll:
            self.poll()
        return self.values.get(key)

    def delete(self, key):
        self.values.pop(key, None)

    def set(self, key, value, ex):
        self.values[key] = value
        self.ttls[key] = ex
        self.writes.append(value)

    def lpop(self, queue):
        assert queue == transport.QUEUE
        return self.pending.pop(0) if self.pending else None


@pytest.fixture
def remote(missed, monkeypatch, tmp_path):
    client = MemoryRedis()
    native_root = get_settings().codex_execution_root
    api_root = str(tmp_path / 'api-unmounted-execution')
    monkeypatch.setattr(get_settings(), 'codex_execution_root', api_root)
    handler = transport.handle_native
    candidates = recovery_listing.candidates
    native = []
    def checked_candidates(*args, **kwargs):
        assert native, 'API attempted to read native private files'
        return candidates(*args, **kwargs)
    def handle(factory, message):
        assert get_settings().codex_execution_root == api_root
        native.append(True)
        get_settings().codex_execution_root = native_root
        try:
            return handler(factory, message, missed.store)
        finally:
            get_settings().codex_execution_root = api_root
            native.pop()
    monkeypatch.setattr(transport, 'request', REQUEST)
    monkeypatch.setattr(transport, 'connection', lambda: client)
    monkeypatch.setattr(transport, 'handle_native', handle)
    monkeypatch.setattr(recovery_listing, 'candidates', checked_candidates)
    client.poll = lambda: transport.consume_once(missed.factory)
    missed.redis = client
    return missed


def message(**overrides):
    data = dict(id=str(uuid4()), operation='available', actor_id=str(uuid4()),
        task_id=str(uuid4()), conversation_id=str(uuid4()), expires_at=time.time() + 20,
        files=[])
    return data | overrides


def enqueue(client, data):
    identity = data['id']
    client.pending.append(identity)
    client.set(transport.PREFIX + 'request:' + identity, json.dumps(data), ex=transport.TTL)


def test_native_reads_separate_disk_and_metadata_never_contains_original(remote):
    content = b'ORIGINAL-BYTES-MUST-NEVER-ENTER-REDIS'
    (remote.work / 'output.txt').write_bytes(content)
    choices = listed(remote)['items']
    assert len(choices) == 1
    first = take(remote, choices).json()
    assert first['errors'] == [] and len(first['saved']) == 1
    assert take(remote, choices).json() == first
    assert count(remote, OutputFile) == 1
    with remote.factory() as session:
        row = session.get(OutputFile, UUID(first['saved'][0]['id']))
        assert remote.store.data[row.object_key] == content
        assert session.get(Job, UUID(remote.turn['jobId'])).execution_count == 1
    assert count(remote, Job) == 1
    assert all(content.decode() not in raw for raw in remote.redis.writes)
    for raw in remote.redis.writes:
        payload = json.loads(raw)
        if 'operation' in payload:
            assert set(payload) == {'id', 'operation', 'actor_id', 'task_id',
                                    'conversation_id', 'expires_at', 'files'}
            assert all(set(item) == {'id', 'version'} for item in payload['files'])
    assert set(remote.redis.ttls.values()) == {transport.TTL}


@pytest.mark.parametrize('operation', ['available', 'receive'])
def test_native_reauthorizes_after_api_releases_transaction(remote, operation):
    (remote.work / 'output.txt').write_bytes(b'original')
    choices = listed(remote)['items']
    def changed_permissions():
        # A separate transaction can write while the API waits.
        change_roles(remote.factory, remote.actor, ('operator',))
        transport.consume_once(remote.factory)
    remote.redis.poll = changed_permissions
    response = (remote.client.get(remote.url + '/recoverable-files') if operation == 'available'
                else take(remote, choices))
    assert response.status_code == 403
    assert count(remote, OutputFile) == 0


def test_partial_failure_retry_preserves_success_without_running_model(remote, monkeypatch):
    (remote.work / 'good.txt').write_bytes(b'good')
    (remote.work / 'bad.txt').write_bytes(b'bad')
    original = remote.store.put
    def fail_one(row, data):
        if data == b'bad':
            raise OSError('private storage diagnostic')
        original(row, data)
    monkeypatch.setattr(remote.store, 'put', fail_one)
    first = take(remote).json()
    assert len(first['saved']) == len(first['errors']) == 1
    monkeypatch.setattr(remote.store, 'put', original)
    second = take(remote).json()
    assert not second['errors'] and len(second['saved']) == 2
    assert first['saved'][0] in second['saved'] and count(remote, OutputFile) == 2
    with remote.factory() as session:
        assert session.get(Job, UUID(remote.turn['jobId'])).execution_count == 1


def test_lost_response_reports_timeout_and_retry_reuses_saved_original(remote, monkeypatch):
    (remote.work / 'output.txt').write_bytes(b'original')
    choices = listed(remote)['items']
    def lose_response():
        transport.consume_once(remote.factory)
        for key in list(remote.redis.values):
            if ':response:' in key:
                remote.redis.delete(key)
    remote.redis.poll = lose_response
    monkeypatch.setattr(transport, 'WAIT_SECONDS', 0.1)
    response = take(remote, choices)
    assert response.status_code == 503 and count(remote, OutputFile) == 1
    remote.redis.poll = lambda: transport.consume_once(remote.factory)
    monkeypatch.setattr(transport, 'WAIT_SECONDS', 25)
    assert len(take(remote, choices).json()['saved']) == 1
    assert count(remote, OutputFile) == 1


def test_api_closes_transaction_before_native_hop(remote, monkeypatch):
    from app.overseas.studio import recovery_router
    original, seen = recovery_router.queries.access, []
    def access(session, *args, **kwargs):
        seen.append(session)
        return original(session, *args, **kwargs)
    def request(*args, **kwargs):
        assert not seen[-1].in_transaction()
        return REQUEST(*args, **kwargs)
    monkeypatch.setattr(recovery_router.queries, 'access', access)
    monkeypatch.setattr(transport, 'request', request)
    assert listed(remote) == {'items': [], 'busy': False}


def test_api_permission_failure_does_not_enqueue(remote):
    change_roles(remote.factory, remote.actor, ('operator',))
    assert remote.client.get(remote.url + '/recoverable-files').status_code == 403
    assert not remote.redis.writes


@pytest.mark.parametrize('failure', ['connection', 'timeout', 'full'])
def test_transport_failure_is_503_never_an_empty_file_list(remote, monkeypatch, failure):
    if failure == 'connection':
        def fail():
            raise ConnectionError('private Redis connection diagnostic')
        monkeypatch.setattr(transport, 'connection', fail)
    elif failure == 'timeout':
        remote.redis.poll = None
        monkeypatch.setattr(transport, 'WAIT_SECONDS', 0.01)
    else:
        remote.redis.pending = [str(uuid4())] * transport.MAX_PENDING
    response = remote.client.get(remote.url + '/recoverable-files')
    assert response.status_code == 503 and '刷新' in str(response.json())
    assert 'private' not in response.text


def test_expired_and_invalid_requests_do_not_run_or_stop_next_request(monkeypatch):
    client, called = MemoryRedis(), []
    monkeypatch.setattr(transport, 'connection', lambda: client)
    monkeypatch.setattr(transport, 'handle_native', lambda *_: called.append(True) or {'items': []})
    enqueue(client, message(expires_at=time.time() - 1))
    enqueue(client, message(files=[{'id': 'x', 'version': 'v', 'path': '/etc/passwd'}]))
    enqueue(client, message())
    assert not transport.consume_once(None) and not called
    assert not transport.consume_once(None) and not called
    assert transport.consume_once(None) and called == [True]
    assert not client.pending


def test_consumer_processes_one_request_and_failure_is_safe(monkeypatch):
    client = MemoryRedis()
    monkeypatch.setattr(transport, 'connection', lambda: client)
    def fail(*_args):
        raise OSError('private path')
    monkeypatch.setattr(transport, 'handle_native', fail)
    first, second = message(), message()
    enqueue(client, first)
    enqueue(client, second)
    assert transport.consume_once(None) and len(client.pending) == 1
    response = json.loads(client.values[transport.PREFIX + 'response:' + first['id']])
    assert response['status'] == 503 and 'private' not in response['detail']
    assert transport.consume_once(None) and not client.pending


def test_native_handler_itself_rejects_expired_request_before_access():
    with pytest.raises(HTTPException) as error:
        transport.handle_native(None, message(expires_at=time.time() - 1))
    assert error.value.status_code == 503
