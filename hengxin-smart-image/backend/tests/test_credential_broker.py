import concurrent.futures
import os
import socket
import struct
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

from app.execution import credential_broker_client as client
from app.execution import managed_credentials as credentials
from test_managed_credentials import auth, read, write

if os.name == 'posix':
    from app.execution import credential_broker as broker

linux = pytest.mark.skipif(os.name != 'posix', reason='Linux SO_PEERCRED and Unix socket service')


@pytest.fixture
def running(monkeypatch):
    if os.name != 'posix':
        pytest.skip('Linux credential broker')
    with tempfile.TemporaryDirectory(prefix='hxauth-') as root:
        root = Path(root)
        source, path = root / 'auth.json', root / 'broker.sock'
        write(source, auth())
        monkeypatch.setattr(credentials, '_request_refresh', lambda _: pytest.fail('unexpected refresh'))
        server = broker.BrokerServer(path, source, {os.getuid()})
        thread = threading.Thread(target=server.serve_forever, kwargs={'poll_interval': 0.01})
        thread.start()
        try:
            yield server, path, source
        finally:
            server.shutdown()
            server.server_close()
            thread.join(5)


def raw_request(path, payload):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.settimeout(2)
        connection.connect(str(path))
        connection.sendall(struct.pack('!I', len(payload)) + payload)
        return client.receive(connection, client.MAX_RESPONSE, time.monotonic() + 2)


def test_broker_access_only_and_socket_permissions(running):
    server, path, source = running
    value = client.request_credentials(path, 600)
    assert value['tokens']['refresh_token'] == ''
    assert read(source)['tokens']['refresh_token'] == 'secret-refresh'
    assert path.stat().st_mode & 0o777 == 0o660


def test_uid_allowlist_rejects_before_reading_credentials(running, monkeypatch):
    server, path, _ = running
    server.allowed_uids = {os.getuid() + 100000}
    monkeypatch.setattr(broker, 'access_credentials', lambda *args: pytest.fail('unauthorized read'))
    with pytest.raises(credentials.CredentialsError) as error:
        client.request_credentials(path, 600)
    assert error.value.code == 'credentials_invalid'


@pytest.mark.parametrize('payload', [b'{}', b'[]', b'null', b'bad-json',
    b'{"timeout_seconds":600,"source":"/secret/path"}',
    b'{"timeout_seconds":600,"account":"other"}',
    b'{"timeout_seconds":600,"timeout_seconds":700}',
    b'{"timeout_seconds":true}', b'{"timeout_seconds":9}',
    b'{"timeout_seconds":7201}', b'{"timeout_seconds":600.0}'])
def test_protocol_rejects_unknown_duplicate_and_invalid_fields(running, payload):
    assert raw_request(running[1], payload) == {'error': 'credentials_invalid'}


def test_protocol_oversize_rejected_without_reading_body(running):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(str(running[1]))
        connection.sendall(struct.pack('!I', client.MAX_REQUEST + 1))
        assert client.receive(connection, client.MAX_RESPONSE, time.monotonic() + 2) == {
            'error': 'credentials_invalid'}


def test_concurrent_broker_clients_refresh_once(running, monkeypatch):
    _, path, source = running
    write(source, auth(ttl=-1))
    calls = []
    def refresh(token):
        calls.append(token)
        time.sleep(0.1)
        return {**auth()['tokens'], 'refresh_token': 'rotated-secret'}
    monkeypatch.setattr(credentials, '_request_refresh', refresh)
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:
        values = list(pool.map(lambda _: client.request_credentials(path, 600), range(8)))
    assert calls == ['secret-refresh']
    assert all(value['tokens']['refresh_token'] == '' for value in values)
    assert read(source)['tokens']['refresh_token'] == 'rotated-secret'


def test_broker_failure_and_disconnect_do_not_log_secrets(running, monkeypatch, capsys):
    def fail(*args):
        raise RuntimeError('very-secret-token /private/path')
    monkeypatch.setattr(broker, 'access_credentials', fail)
    with pytest.raises(credentials.CredentialsError) as error:
        client.request_credentials(running[1], 600)
    assert error.value.code == 'credentials_invalid'
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(str(running[1]))
        client.send(connection, {'timeout_seconds': 600}, 128, time.monotonic() + 1)
    time.sleep(0.05)
    output = capsys.readouterr()
    assert output.out == output.err == ''


def test_server_concurrency_slots_are_bounded(running):
    server, path, _ = running
    acquired = []
    try:
        while server.slots.acquire(blocking=False):
            acquired.append(True)
        with pytest.raises(credentials.CredentialsError):
            client.request_credentials(path, 600)
        assert len(acquired) == 16
    finally:
        for _ in acquired:
            server.slots.release()
    assert client.request_credentials(path, 600)['tokens']['refresh_token'] == ''


def test_existing_live_socket_is_not_replaced(running):
    _, path, source = running
    with pytest.raises(ValueError, match='already running'):
        broker.BrokerServer(path, source, {os.getuid()})
    assert client.request_credentials(path, 600)['tokens']['refresh_token'] == ''


@linux
def test_stale_socket_restart_and_untrusted_parent(tmp_path):
    with tempfile.TemporaryDirectory(prefix='hxauth-') as root:
        root = Path(root)
        path = root / 'broker.sock'
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.bind(str(path))
        with broker.BrokerServer(path, root / 'auth.json', {os.getuid()}):
            assert path.exists()
        assert not path.exists()
        root.chmod(0o770)
        with pytest.raises(ValueError, match='unsafe broker directory'):
            broker.BrokerServer(path, root / 'auth.json', {os.getuid()})


@pytest.mark.parametrize('timeout', [True, 0, 9, 7201, 600.0, '600'])
def test_client_rejects_invalid_timeout_without_connecting(timeout):
    with pytest.raises(credentials.CredentialsError):
        client.request_credentials('/missing/socket', timeout)


def test_client_missing_service_returns_only_fixed_error():
    with pytest.raises(credentials.CredentialsError) as error:
        client.request_credentials('/secret/missing/socket', 600)
    assert error.value.code == 'credentials_invalid'
    assert 'secret' not in str(error.value)


@linux
def test_client_total_deadline_against_trickle_server(monkeypatch):
    with tempfile.TemporaryDirectory(prefix='hxauth-') as root:
        path = str(Path(root) / 'slow.sock')
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(path)
            listener.listen()
            def trickle():
                connection, _ = listener.accept()
                with connection:
                    connection.recv(1024)
                    try:
                        for value in struct.pack('!I', 100) + b'x' * 100:
                            connection.sendall(bytes([value]))
                            time.sleep(0.03)
                    except OSError:
                        pass
            thread = threading.Thread(target=trickle)
            thread.start()
            monkeypatch.setattr(client, 'CLIENT_TIMEOUT', 0.12)
            started = time.monotonic()
            with pytest.raises(credentials.CredentialsError):
                client.request_credentials(path, 600)
            assert time.monotonic() - started < 1
            thread.join(2)


@pytest.mark.parametrize('response', [{'error': 'secret-token'}, {'auth': auth()},
                                    {'auth': auth(ttl=-1)}, {'other': 'secret-token'}])
def test_client_rejects_invalid_response(monkeypatch, response):
    class Connection:
        def __enter__(self): return self
        def __exit__(self, *args): pass
        def settimeout(self, timeout): pass
        def connect(self, path): pass
    monkeypatch.setattr(client.socket, 'socket', lambda *args: Connection())
    monkeypatch.setattr(client, 'send', lambda *args: None)
    monkeypatch.setattr(client, 'receive', lambda *args: response)
    with pytest.raises(credentials.CredentialsError) as error:
        client.request_credentials('/fake/socket', 600)
    assert 'secret-token' not in str(error.value)


@linux
@pytest.mark.skipif(not hasattr(os, 'geteuid') or getattr(os, 'geteuid', lambda: -1)() != 0,
                    reason='root required to verify real production UID separation')
def test_real_two_worker_uids_share_access_without_reading_master(running):
    server, path, source = running
    server.allowed_uids = {1001, 999}
    path.parent.chmod(0o750)
    source.chmod(0o600)
    script = '''
import os, sys
from pathlib import Path
from app.execution.credential_broker_client import request_credentials
from app.execution.managed_credentials import CredentialsError
os.setgroups([0]); os.setgid(0); os.setuid(int(sys.argv[1]))
try:
    Path(sys.argv[3]).read_bytes()
except PermissionError:
    pass
else:
    sys.exit(10)
try:
    value = request_credentials(sys.argv[2], 600)
except CredentialsError:
    sys.exit(0 if sys.argv[1] == '1002' else 11)
assert sys.argv[1] != '1002'
assert value['tokens']['refresh_token'] == ''
'''
    for uid in (1001, 999, 1002):
        result = subprocess.run([sys.executable, '-c', script, str(uid), str(path), str(source)],
                                capture_output=True, timeout=5)
        assert result.returncode == 0, result.stderr.decode()
        assert result.stdout == b''
