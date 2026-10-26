import os
import socket
import tempfile
import threading
import time
from pathlib import Path
from uuid import uuid4

import pytest

from app.account_management.manager import AccountManager
from app.account_management.store import AccountStore
from app.execution.credential_broker_client import send, receive, request_credentials
from app.execution.managed_credentials import CredentialsError
from test_managed_credentials import auth, write

pytestmark = pytest.mark.skipif(os.name != 'posix', reason='Linux SO_PEERCRED and real Unix socket')


@pytest.fixture
def servers():
    from app.account_management.service import BusinessBroker, ControlServer
    with tempfile.TemporaryDirectory(prefix='hxaccounts-') as temporary:
        root = Path(temporary)
        source = root / 'legacy.json'
        write(source, auth())
        managers = {side: AccountManager(AccountStore(root / side, source), 'fake-cli', 'fake-bwrap',
                    verify=lambda *args: 'ready') for side in ('domestic', 'overseas')}
        broker = BusinessBroker(root / 'worker.sock', managers, os.getuid(), os.getuid() + 100000)
        control = ControlServer(root / 'control.sock', managers['domestic'], os.getuid())
        threads = [threading.Thread(target=s.serve_forever, kwargs={'poll_interval': .01}) for s in (broker, control)]
        for thread in threads:
            thread.start()
        try:
            yield root, managers, broker, control
        finally:
            for server in (broker, control):
                server.shutdown()
                server.server_close()
            for manager in managers.values():
                manager.close()
            for thread in threads:
                thread.join(3)


def rpc(path, action='status', **params):
    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
        connection.connect(str(path))
        deadline = time.monotonic() + 3
        send(connection, dict(action=action, actor={'id': str(uuid4()), 'name': '测试管理员'}, **params), 16384, deadline)
        return receive(connection, 131072, deadline)


def test_control_socket_is_metadata_only_and_refuses_injection(servers):
    root, managers, broker, control = servers
    value = rpc(root / 'control.sock')
    assert value['data']['status'] == 'unchecked'
    assert not any(secret in str(value) for secret in ('secret-refresh', 'test-signature', 'auth.json'))
    assert rpc(root / 'control.sock', source='/arbitrary/file')['error']['status'] == 400
    assert rpc(root / 'control.sock', business='overseas')['error']['status'] == 400
    control.allowed_uids = {os.getuid() + 100000}
    assert rpc(root / 'control.sock')['error']['status'] == 403


def test_business_worker_uses_its_profile_and_same_legacy_file(servers):
    root, managers, broker, _ = servers
    original = request_credentials(root / 'worker.sock', 60)
    assert original['tokens']['refresh_token'] == ''
    actor = {'id': str(uuid4()), 'name': '测试管理员'}
    managers['overseas'].store.activate(auth(account='other-business'), 0, actor)
    assert request_credentials(root / 'worker.sock', 60)['tokens']['account_id'] == 'workspace-one'
    managers['domestic'].store.remove(0, actor)
    with pytest.raises(CredentialsError):
        request_credentials(root / 'worker.sock', 60)
    assert broker.credentials(os.getuid() + 100000, 60)['tokens']['account_id'] == 'other-business'
    assert (root / 'legacy.json').exists()


def test_api_uid_cannot_use_worker_credential_protocol(servers):
    root, _, broker, _ = servers
    broker.allowed_uids = {os.getuid() + 100000}
    with pytest.raises(CredentialsError):
        request_credentials(root / 'worker.sock', 60)
    value = rpc(root / 'control.sock', action='credentials', timeout_seconds=60)
    assert value['error']['status'] == 400


def test_control_socket_permissions_and_bad_revision(servers):
    root, _, _, _ = servers
    assert (root / 'control.sock').stat().st_mode & 0o777 == 0o660
    assert rpc(root / 'control.sock', action='remove', revision=True)['error']['status'] == 400
    assert rpc(root / 'control.sock', action='start', revision=0, intent='upload')['error']['status'] == 409
