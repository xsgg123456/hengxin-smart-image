"""Real Linux orphan races; never launch models or touch existing services."""
import importlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time

import pytest

pytestmark = pytest.mark.skipif(sys.platform != 'linux', reason='Linux subreaper/pidfd')


def wait_for(check, timeout=5):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        value = check()
        if value:
            return value
        time.sleep(.01)
    raise AssertionError('Process fixture did not reach expected state')


@pytest.fixture
def owner(monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / 'infra'))
    module = importlib.import_module('phase11a_processes')
    env = module.Processes()
    env.root = Path(tempfile.mkdtemp(prefix='hengxin-phase11a-', dir='/tmp')).resolve()
    env._root_identity = (env.root.stat().st_dev, env.root.stat().st_ino)
    env.python, env.env = Path(sys.executable), {'PATH': '/usr/bin:/bin'}
    env.report, env.containers, env.volumes = {}, [], []
    # Disable discovery entirely: tests must prove kernel adoption alone suffices.
    env.capture_descendants = lambda: None
    env.init_processes()
    yield env, module
    env.cleanup()


@pytest.fixture
def foreign():
    process = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'],
                               start_new_session=True)
    yield process
    process.terminate()
    process.wait(timeout=5)


def orphan_code(root, *, code=0, late=False):
    # Parent exits immediately, before its child even creates the new session.
    return f'''import os,signal,time
from pathlib import Path
root=Path({str(root)!r})
def detached():
    os.setsid()
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    (root/'child').write_text(str(os.getpid()))
    while True: time.sleep(.1)
def spawn(signum=None, frame=None):
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    if os.fork()==0: detached()
    os._exit({code})
if {late!r}:
    signal.signal(signal.SIGTERM, spawn)
    (root/'parent').write_text(str(os.getpid()))
    while True: time.sleep(.1)
else:
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    if os.fork()==0:
        detached()
    (root/'parent').write_text(str(os.getpid()))
    os._exit({code})
'''


def child_identity(owner):
    env, module = owner
    child = int(wait_for(lambda: (env.root / 'child').read_text()
                        if (env.root / 'child').exists() else ''))
    stat = module.process_stat(child)
    assert stat and stat[1] == child  # setsid really ran.
    return child, stat[2]


def assert_reaped(module, pid, birth):
    stat = module.process_stat(pid)
    assert stat is None or stat[2] != birth  # A zombie is not sufficient.


def test_fast_parent_exit_setsid_child_cleanup_without_capture(owner, foreign):
    env, module = owner
    process = env.start('worker', ['-c', orphan_code(env.root)])
    child, birth = child_identity(owner)
    parent = int((env.root / 'parent').read_text())
    wait_for(lambda: module.process_stat(child)[0] == process.pid)
    wait_for(lambda: module.process_stat(parent) is None)  # Parent also reaped.
    assert env.owned[process.pid] == {process.pid: process._birth}
    assert process.poll() is None  # Supervisor remains while orphan is alive.
    env.cleanup()
    assert_reaped(module, child, birth)
    assert env.report['cleanupComplete'] and not env.root.exists()
    assert foreign.poll() is None


@pytest.mark.parametrize('app', [True, False])
def test_command_orphan_timeout_cleanup(owner, foreign, app):
    env, module = owner
    argv = ['-c', orphan_code(env.root)]
    if not app:
        argv.insert(0, sys.executable)
    with pytest.raises(TimeoutError, match='output suppressed'):
        env.command(argv, app=app, timeout=1)
    child = int((env.root / 'child').read_text())
    assert module.process_stat(child) is None
    assert not env.owned and foreign.poll() is None


def test_term_handler_forks_new_setsid_child(owner, foreign):
    env, module = owner
    process = env.start('worker', ['-c', orphan_code(env.root, late=True)])
    wait_for(lambda: (env.root / 'parent').exists())
    env._stop(process)  # TERM creates a child after cleanup has already started.
    child = int((env.root / 'child').read_text())
    assert module.process_stat(child) is None
    assert process._cleaned and foreign.poll() is None


def test_repeated_term_does_not_abort_supervisor(owner, foreign):
    env, module = owner
    process = env.start('worker', ['-c', orphan_code(env.root)])
    child, birth = child_identity(owner)
    for _ in range(5):
        module.signal_owned(process.pid, process._birth, signal.SIGTERM)
        time.sleep(.02)
    assert process.poll() is None
    env._stop(process)
    assert_reaped(module, child, birth)
    assert foreign.poll() is None


def test_missing_supervisor_proof_cannot_claim_cleanup(owner):
    env, module = owner
    # No remaining children, but absent completion proof must still fail closed.
    process = env.start('worker', ['-c', 'pass'])
    process.wait(timeout=5)
    os.read(process._status_fd, 1)  # Discard completion to simulate lost proof.
    with pytest.raises(RuntimeError, match='cleanup incomplete'):
        env.cleanup()
    assert not env.report['cleanupComplete'] and env.root.exists()
    # Restore only this deliberately discarded proof for fixture teardown.
    process._cleaned = True


def test_wrong_birth_never_signals_foreign(owner, foreign):
    env, module = owner
    module.signal_owned(foreign.pid, 'wrong-birth', signal.SIGKILL)
    assert foreign.poll() is None


def test_root_exit_status_and_stdout_preserved(owner):
    env, module = owner
    assert env.command(['-c', 'print("fixture-output")'], app=True) == 'fixture-output'
    process = env.start('worker', ['-c', 'raise SystemExit(7)'])
    assert process.wait(timeout=5) == 7
    env._stop(process)
    assert process._cleaned
