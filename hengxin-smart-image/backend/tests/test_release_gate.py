"""Release gates are exercised with real sockets, processes and an isolated broker."""
import os
from pathlib import Path
import signal
import socket
import socketserver
import subprocess
import sys
import threading
import time
from uuid import uuid4

import pytest
from fastapi import FastAPI, WebSocket
from fastapi.testclient import TestClient

from app.execution import credential_broker, release_gate


pytestmark = pytest.mark.skipif(sys.platform != 'linux' or os.geteuid() != 0,
                                reason='requires isolated root Linux filesystem identities')


def test_native_credential_imports_require_only_standard_library():
    code = ('import sys; import app.account_management.service; '
            'import app.execution.credential_broker; '
            'from app.execution.release_gate import marker_open; '
            'assert not any(name.startswith("starlette") for name in sys.modules); '
            'assert marker_open("workers")')
    environment = {key: value for key, value in os.environ.items() if key != release_gate.ENVIRONMENT}
    subprocess.run([sys.executable, '-S', '-B', '-c', code],
                   cwd=Path(__file__).resolve().parents[1], env=environment,
                   capture_output=True, text=True, check=True, timeout=20)


@pytest.fixture
def gates(tmp_path, monkeypatch):
    root = tmp_path / 'gate'
    root.mkdir(mode=0o755)
    for name in ('workers', 'ingress'):
        (root / name).write_bytes(b'closed\n')
        (root / name).chmod(0o644)
    monkeypatch.setattr(release_gate, 'DIRECTORY', str(root))
    monkeypatch.setenv(release_gate.ENVIRONMENT, str(root))
    return root


def open_gate(root, name):
    target = root / name
    tmp = root / (name + '.next')
    tmp.write_bytes(b'open\n')
    tmp.chmod(0o644)
    os.replace(tmp, target)


def test_marker_is_fail_closed_on_missing_symlink_permissions_and_invalid_environment(gates, monkeypatch):
    assert not release_gate.marker_open('workers')
    open_gate(gates, 'workers')
    assert release_gate.marker_open('workers')
    (gates / 'workers').chmod(0o666)
    assert not release_gate.marker_open('workers')
    (gates / 'workers').unlink()
    (gates / 'workers').symlink_to(gates / 'ingress')
    assert not release_gate.marker_open('workers')
    monkeypatch.setenv(release_gate.ENVIRONMENT, '/untrusted')
    assert not release_gate.marker_open('workers')
    monkeypatch.delenv(release_gate.ENVIRONMENT)
    assert release_gate.marker_open('workers')


def test_closed_gate_keeps_health_available_but_blocks_business_and_websocket(gates):
    app = FastAPI()
    app.add_middleware(release_gate.ReleaseGateMiddleware)

    @app.get('/api/v1/health/ready')
    def health(): return {'ready': True}

    @app.get('/api/private')
    def business(): return {'business': True}

    @app.websocket('/socket')
    async def ws(websocket: WebSocket):
        await websocket.accept()
        await websocket.close()

    with TestClient(app) as client:
        assert client.get('/api/v1/health/ready').status_code == 200
        assert client.post('/api/v1/health/ready').status_code == 503
        assert client.get('/api/private').status_code == 503
        with pytest.raises(Exception) as disconnected:
            with client.websocket_connect('/socket'):
                pass
        assert getattr(disconnected.value, 'code', None) == 1013
        open_gate(gates, 'ingress')
        assert client.get('/api/private').status_code == 200


def test_waiting_background_loop_stops_without_opening_gate(gates):
    stopped, result = threading.Event(), []
    thread = threading.Thread(target=lambda: result.append(release_gate.wait_for_workers(stopped)))
    thread.start()
    stopped.set()
    thread.join(2)
    assert not thread.is_alive() and result == [False]


def test_credentials_socket_is_closed_from_bind_before_chmod(gates, tmp_path, monkeypatch):
    recorded = []
    original = socketserver.UnixStreamServer.server_bind
    def bind(server):
        original(server)
        recorded.append(server.path.lstat().st_mode & 0o777)
    monkeypatch.setattr(socketserver.UnixStreamServer, 'server_bind', bind)
    socket_dir = tmp_path / 'socket'
    socket_dir.mkdir(mode=0o700)
    with credential_broker.BrokerServer(socket_dir / 'broker.sock', tmp_path / 'source', {0}):
        assert (socket_dir / 'broker.sock').lstat().st_mode & 0o777 == 0
    assert recorded == [0]
    open_gate(gates, 'workers')
    with credential_broker.BrokerServer(socket_dir / 'broker.sock', tmp_path / 'source', {0}):
        assert (socket_dir / 'broker.sock').lstat().st_mode & 0o777 == 0o660


def test_celery_worker_cannot_consume_until_gate_opens(gates, tmp_path):
    from celery import Celery
    from redis import Redis
    broker = 'redis://127.0.0.1:35440/15'
    try:
        Redis.from_url(broker, socket_connect_timeout=1).ping()
    except Exception:
        pytest.skip('isolated test Redis is unavailable')
    queue = 'gate-test-' + uuid4().hex
    completed = tmp_path / 'task-completed'
    script = tmp_path / 'worker.py'
    script.write_text('''\
import os
from pathlib import Path
from celery import Celery
from app.execution import release_gate
release_gate.DIRECTORY = os.environ['HX_RELEASE_GATE_DIR']
app = Celery('gate_test', broker=os.environ['TEST_BROKER'])
app.conf.update(task_default_queue=os.environ['TEST_QUEUE'], task_ignore_result=True,
                worker_enable_remote_control=False, worker_send_task_events=False)
release_gate.guard_celery(app)
@app.task(name='gate_test.record')
def record(path): Path(path).write_text('done')
app.Worker(pool='solo', loglevel='ERROR', queues=[os.environ['TEST_QUEUE']],
           without_heartbeat=True, without_gossip=True, without_mingle=True).start()
''', encoding='utf-8')
    env = dict(os.environ, TEST_BROKER=broker, TEST_QUEUE=queue, C_FORCE_ROOT='1',
               PYTHONPATH=str(Path(__file__).resolve().parents[1]))
    process = subprocess.Popen([sys.executable, str(script)], env=env,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    producer = Celery('gate_producer', broker=broker)
    try:
        producer.send_task('gate_test.record', args=[str(completed)], queue=queue, ignore_result=True)
        time.sleep(2)
        assert process.poll() is None and not completed.exists()
        open_gate(gates, 'workers')
        deadline = time.monotonic() + 20
        while not completed.exists() and time.monotonic() < deadline and process.poll() is None:
            time.sleep(.1)
        assert completed.read_text() == 'done'
    finally:
        process.terminate()
        try:
            process.wait(timeout=8)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
        Redis.from_url(broker).delete(queue)


def test_sigkill_after_formal_gateway_start_leaves_real_request_gate_closed(gates, tmp_path, monkeypatch):
    from types import SimpleNamespace
    scripts = Path(__file__).resolve().parents[3] / 'scripts/release/intranet'
    monkeypatch.syspath_prepend(str(scripts))
    import joint_studio_ingress as ingress

    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): pass

    event = tmp_path / 'gateway-started'
    u = SimpleNamespace(WORK=tmp_path, run=lambda *args, **kwargs: '', contexts=lambda: {}, safe=lambda path: None)
    real_gate_state = ingress.paths.gate_state
    monkeypatch.setattr(ingress.paths, 'gate_state', lambda adapter, name: real_gate_state(adapter, name, gates))
    monkeypatch.setattr(ingress.urllib.request, 'urlopen', lambda *args, **kwargs: Response())

    def app_command(action, names, **kwargs):
        if action == 'up' and names == ('domestic-web',):
            event.write_text('started')
            os.kill(os.getpid(), signal.SIGSTOP)

    gateway = ingress.PrivateIngress(u, app_command, lambda *args, **kwargs: None, lambda state: None)
    monkeypatch.setattr(gateway, 'state', lambda: {'ctx': {}, 'sockets': []})
    monkeypatch.setattr(gateway, 'socket_modes', lambda *args, **kwargs: None)
    monkeypatch.setattr(gateway, 'assert_api', lambda *args, **kwargs: None)
    child = os.fork()
    if child == 0:
        try:
            gateway.open_public({})
        finally:
            os._exit(1)
    try:
        deadline = time.monotonic() + 10
        while not event.exists() and time.monotonic() < deadline:
            time.sleep(.05)
        assert event.exists()
        os.kill(child, signal.SIGKILL)
        _, status = os.waitpid(child, 0)
        child = None
        assert os.WIFSIGNALED(status) and os.WTERMSIG(status) == signal.SIGKILL
        assert (gates / 'workers').read_bytes() == b'closed\n'
        assert (gates / 'ingress').read_bytes() == b'closed\n'
        app = FastAPI()
        app.add_middleware(release_gate.ReleaseGateMiddleware)
        app.get('/api/private')(lambda: {'ok': True})
        with TestClient(app) as client:
            assert client.get('/api/private').status_code == 503
    finally:
        if child is not None:
            os.kill(child, signal.SIGKILL)
            os.waitpid(child, 0)
