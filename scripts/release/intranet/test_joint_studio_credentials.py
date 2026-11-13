import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
from types import SimpleNamespace

import pytest

import joint_studio_credentials as credentials

pytestmark = pytest.mark.skipif(sys.platform != 'linux' or os.geteuid() != 0,
                                reason='requires isolated root Linux identity changes')


@pytest.fixture
def runtime(monkeypatch):
    with tempfile.TemporaryDirectory(prefix='hx-release-credentials-') as temporary:
        root = Path(temporary)
        root.chmod(0o755)
        gate = root / 'gate'
        gate.mkdir(mode=0o755)
        for name in ('workers', 'ingress'):
            (gate / name).write_bytes(b'closed\n')
            (gate / name).chmod(0o644)
        for name in ('accounts', 'auth'):
            folder = root / name
            folder.mkdir(mode=0o750)
            os.chown(folder, 65534, 65534)
        endpoints = tuple(str(root / name) for name in
                           ('accounts/domestic.sock', 'accounts/overseas.sock', 'accounts/worker.sock', 'auth/broker.sock'))
        props = {'ActiveState': 'inactive', 'MainPID': '0', 'ControlGroup': ''}
        u = SimpleNamespace(ACCOUNT_SOCKETS=endpoints, prop=lambda name, key: props[key], safe=lambda path: None)
        state = {'sockets': [(name, 1, 0o660) for name in endpoints],
                 'ctx': {name: {'user': 65534} for name in credentials.SERVICES}}
        monkeypatch.setattr(credentials, 'RUNTIME_ROOT', root)
        yield root, gate, u, state, props


def broker(gate, endpoint):
    source = Path(__file__).resolve().parents[3] / 'hengxin-smart-image/backend'
    script = '''
import os,sys,time
from pathlib import Path
from app.execution import release_gate
from app.execution.credential_broker import BrokerServer
release_gate.DIRECTORY=sys.argv[1]
os.environ[release_gate.ENVIRONMENT]=sys.argv[1]
server=BrokerServer(Path(sys.argv[2]),Path(sys.argv[2]).parent/'unused-auth',{65534})
print('READY',flush=True)
time.sleep(60)
'''
    return subprocess.Popen([sys.executable, '-c', script, str(gate), str(endpoint)],
        user=65534, group=65534, extra_groups=[], env=dict(os.environ, PYTHONPATH=str(source)),
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


@pytest.mark.parametrize('signum', [signal.SIGTERM, signal.SIGKILL])
def test_nonroot_dead_gated_socket_can_restart_after_verified_cleanup(runtime, signum):
    _, gate, u, state, _ = runtime
    endpoint = Path(u.ACCOUNT_SOCKETS[0])
    process = broker(gate, endpoint)
    try:
        assert process.stdout.readline().strip() == 'READY'
        assert endpoint.stat().st_uid == 65534 and endpoint.stat().st_mode & 0o777 == 0
        process.send_signal(signum)
        assert process.wait(timeout=5) == -signum
        assert endpoint.exists()
        credentials.prepare(u, state)
        assert not endpoint.exists()
        process = broker(gate, endpoint)
        assert process.stdout.readline().strip() == 'READY'
        assert endpoint.stat().st_mode & 0o777 == 0
        process.kill()
        process.wait(timeout=5)
        credentials.prepare(u, state)
        credentials.prepare(u, state)  # An interrupted recovery is repeatable.
        assert not endpoint.exists()
    finally:
        if process.poll() is None:
            process.kill()
            process.wait(timeout=5)


def test_live_listener_is_never_removed_even_if_service_metadata_claims_stopped(runtime):
    _, gate, u, state, _ = runtime
    endpoint = Path(u.ACCOUNT_SOCKETS[0])
    process = broker(gate, endpoint)
    try:
        assert process.stdout.readline().strip() == 'READY'
        original = endpoint.stat().st_ino
        with pytest.raises(RuntimeError, match='listener'):
            credentials.prepare(u, state)
        assert endpoint.stat().st_ino == original
    finally:
        process.kill()
        process.wait(timeout=5)


@pytest.mark.parametrize('case', ['active', 'pid', 'unknown', 'regular', 'wrong_owner', 'open_mode', 'symlink'])
def test_unknown_or_active_socket_is_preserved(runtime, case):
    root, _, u, state, props = runtime
    endpoint = Path(u.ACCOUNT_SOCKETS[0])
    sock = socket.socket(socket.AF_UNIX)
    sock.bind(str(endpoint))
    sock.close()
    os.chown(endpoint, 65534, 65534)
    endpoint.chmod(0)
    if case == 'active': props['ActiveState'] = 'active'
    elif case == 'pid': props['MainPID'] = '123'
    elif case == 'unknown': state['sockets'].clear()
    elif case == 'regular':
        endpoint.unlink()
        endpoint.write_text('unrelated')
    elif case == 'wrong_owner': os.chown(endpoint, 1001, 1001)
    elif case == 'open_mode': endpoint.chmod(0o660)
    else:
        endpoint.unlink()
        endpoint.symlink_to(root / 'gate/workers')
    before = endpoint.lstat().st_ino
    with pytest.raises(RuntimeError):
        credentials.prepare(u, state)
    assert endpoint.lstat().st_ino == before


def test_remaining_cgroup_child_refuses_before_removal(runtime, monkeypatch):
    root, _, u, state, props = runtime
    cgroup = root / 'cgroup'
    child = cgroup / 'service' / 'child'
    child.mkdir(parents=True)
    (child.parent / 'cgroup.procs').write_text('')
    (child / 'cgroup.procs').write_text('123\n')
    monkeypatch.setattr(credentials, 'CGROUP_ROOT', cgroup)
    props['ControlGroup'] = '/service'
    with pytest.raises(RuntimeError, match='live processes'):
        credentials.prepare(u, state)
