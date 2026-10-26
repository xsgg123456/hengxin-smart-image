"""Actual framing helpers, shared deadline, and nonblocking HTTP adapter."""
import asyncio
import json
import struct
import threading
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.account_management import client
from app.account_management.schemas import Account
from app.core.config import get_settings
from test_account_management_api import ACCOUNT
from test_overseas_configuration import configure_overseas


@pytest.fixture(autouse=True)
def unix_socket_symbol(monkeypatch):
    # Framing uses a fake transport; Windows does not expose the Linux family.
    monkeypatch.setattr(client.socket, 'AF_UNIX', 1, raising=False)


class Connection:
    def __init__(self, response):
        self.response = response
        self.sent = b''
        self.timeouts = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.closed = True

    def connect(self, path):
        self.path = path

    def settimeout(self, seconds):
        self.timeouts.append(seconds)

    def sendall(self, payload):
        self.sent += payload

    def recv(self, length):
        block = self.response[:min(length, 3)]
        self.response = self.response[len(block):]
        return block


def framed(value):
    raw = json.dumps(value).encode()
    return struct.pack('!I', len(raw)) + raw


def test_framing_fragmented_response_and_single_budget(monkeypatch):
    connection = Connection(framed({'data': ACCOUNT}))
    monkeypatch.setattr(client.socket, 'socket', lambda *args: connection)
    ticks = iter([10, 11, 12] + [13] * 200)
    monkeypatch.setattr(client.time, 'monotonic', lambda: next(ticks))
    request = {'action': 'status', 'actor': {'id': 'a', 'name': '管理员'}}
    assert client._exchange('/business.sock', request) == {'data': ACCOUNT}
    assert json.loads(connection.sent[4:]) == request
    assert struct.unpack('!I', connection.sent[:4])[0] == len(connection.sent) - 4
    assert connection.path == '/business.sock' and connection.closed
    assert connection.timeouts[:3] == [7, 6, 5]
    assert all(0 < value <= 8 for value in connection.timeouts)


@pytest.mark.parametrize('response', [struct.pack('!I', 128 * 1024 + 1),
    struct.pack('!I', 0), struct.pack('!I', 3) + b'{',
    struct.pack('!I', 7) + b'notjson'])
def test_bad_frames_rejected_and_connection_closed(monkeypatch, response):
    connection = Connection(response)
    monkeypatch.setattr(client.socket, 'socket', lambda *args: connection)
    with pytest.raises(ValueError):
        client._exchange('/business.sock', {'action': 'status'})
    assert connection.closed


def test_oversized_request_not_sent(monkeypatch):
    connection = Connection(b'')
    monkeypatch.setattr(client.socket, 'socket', lambda *args: connection)
    with pytest.raises(ValueError):
        client._exchange('/business.sock', {'action': 'x' * (16 * 1024)})
    assert connection.sent == b'' and connection.closed


def test_expired_budget_closes_connection(monkeypatch):
    connection = Connection(framed({'data': ACCOUNT}))
    monkeypatch.setattr(client.socket, 'socket', lambda *args: connection)
    ticks = iter([10, 10, 19])
    monkeypatch.setattr(client.time, 'monotonic', lambda: next(ticks))
    with pytest.raises(TimeoutError):
        client._exchange('/business.sock', {'action': 'status'})
    assert connection.closed and connection.sent == b''


def test_socket_wait_does_not_block_event_loop(monkeypatch):
    monkeypatch.setattr(get_settings(), 'codex_account_management_socket', '/business.sock')
    entered, release = threading.Event(), threading.Event()

    def exchange(*args):
        entered.set()
        assert release.wait(2), 'event loop was blocked by socket exchange'
        return {'data': ACCOUNT}

    monkeypatch.setattr(client, '_exchange', exchange)

    async def check():
        task = asyncio.create_task(client.request('status', SimpleNamespace(id='1', name='n'), Account))
        await asyncio.to_thread(entered.wait, 1)
        release.set()
        assert (await task).status == 'empty'

    asyncio.run(check())


def test_timeout_maps_to_safe_unavailable(monkeypatch):
    monkeypatch.setattr(get_settings(), 'codex_account_management_socket', '/business.sock')

    def timeout(*args):
        raise TimeoutError('private-path')

    monkeypatch.setattr(client, '_exchange', timeout)
    with pytest.raises(HTTPException) as caught:
        asyncio.run(client.request('status', SimpleNamespace(id='1', name='n'), Account))
    assert caught.value.status_code == 503 and 'private-path' not in caught.value.detail


def test_management_socket_settings_use_business_prefix(monkeypatch):
    monkeypatch.setenv('CODEX_ACCOUNT_MANAGEMENT_SOCKET', '/domestic.sock')
    monkeypatch.setenv('OVERSEAS_CODEX_ACCOUNT_MANAGEMENT_SOCKET', '/overseas.sock')
    get_settings.cache_clear()
    try:
        assert get_settings().codex_account_management_socket == '/domestic.sock'
        configure_overseas(monkeypatch)
        get_settings.cache_clear()
        assert get_settings().codex_account_management_socket == '/overseas.sock'
        monkeypatch.delenv('OVERSEAS_CODEX_ACCOUNT_MANAGEMENT_SOCKET')
        get_settings.cache_clear()
        assert get_settings().codex_account_management_socket == ''
    finally:
        get_settings.cache_clear()
