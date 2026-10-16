"""A real surviving child process must block cleanup after its leader exits."""
import os
import signal
import subprocess
import sys
import time
from types import SimpleNamespace
import pytest
from app.execution.process import process_identity
from app.overseas.tasks.cleanup_process import group_alive
from app.overseas.tasks import cleanup_process
from app.db.timestamps import utcnow
from datetime import timedelta
from pathlib import Path


@pytest.mark.skipif(os.name != 'posix', reason='Native overseas execution requires Linux /proc')
@pytest.mark.parametrize('vanished', [FileNotFoundError, ProcessLookupError])
@pytest.mark.parametrize('survivor', [True, False])
def test_vanished_proc_entry_does_not_skip_remaining_group(monkeypatch, vanished, survivor):
    original_read = Path.read_text

    def read(path, *args, **kwargs):
        if path == Path('/proc/123/stat'):
            raise vanished('Process exited while reading stat')
        if path == Path('/proc/124/stat'):
            return f'124 (child) S 1 {456 if survivor else 999} 0'
        return original_read(path, *args, **kwargs)

    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    monkeypatch.setattr(Path, 'iterdir', lambda _: iter([Path('/proc/123'), Path('/proc/124')]))
    monkeypatch.setattr(Path, 'read_text', read)
    assert group_alive(SimpleNamespace(process_boot=boot, process_id=456)) is survivor


@pytest.mark.skipif(os.name != 'posix', reason='Native overseas execution requires Linux /proc')
def test_proc_permission_error_still_blocks_cleanup(monkeypatch):
    original_read = Path.read_text

    def read(path, *args, **kwargs):
        if path == Path('/proc/123/stat'):
            raise PermissionError('Cannot establish process exit')
        return original_read(path, *args, **kwargs)

    boot = Path('/proc/sys/kernel/random/boot_id').read_text().strip()
    monkeypatch.setattr(Path, 'iterdir', lambda _: iter([Path('/proc/123')]))
    monkeypatch.setattr(Path, 'read_text', read)
    job = SimpleNamespace(worker_node='local', status='succeeded', execution_count=1,
        process_exited=True, process_id=456, process_boot=boot, process_started='birth')
    session = SimpleNamespace(scalars=lambda _: [job])
    monkeypatch.setattr(cleanup_process, 'get_settings', lambda: SimpleNamespace(worker_node_name='local'))
    with pytest.raises(PermissionError):
        group_alive(job)
    from uuid import uuid4
    assert not cleanup_process.confirmed(session, uuid4())


@pytest.mark.skipif(os.name != 'posix', reason='Native overseas execution requires Linux /proc')
def test_surviving_real_child_is_not_mistaken_for_exited_process_group():
    code = ('import subprocess,sys; subprocess.Popen([sys.executable,"-c","import time; time.sleep(30)"]); '
            'print("ready",flush=True); sys.stdin.read(1)')
    process = subprocess.Popen([sys.executable, '-c', code], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        assert process.stdout.readline().strip() == 'ready'
        boot, started = process_identity(process.pid)
        row = SimpleNamespace(process_id=process.pid, process_boot=boot, process_started=started)
        process.stdin.write('x')
        process.stdin.flush()
        assert process.wait(timeout=5) == 0
        assert group_alive(row)
        os.killpg(process.pid, signal.SIGTERM)
        deadline = time.monotonic() + 5
        while group_alive(row) and time.monotonic() < deadline:
            time.sleep(.02)
        assert not group_alive(row)
    finally:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        process.wait(timeout=5)
        for stream in (process.stdin, process.stdout, process.stderr):
            stream.close()


@pytest.mark.skipif(os.name != 'posix', reason='Signals apply only to native Linux worker')
@pytest.mark.parametrize('age,identity,expected', [(1, True, signal.SIGTERM),
    (6, True, getattr(signal, 'SIGKILL', 9)), (6, False, None)])
def test_lost_worker_stop_escalates_only_with_verified_process_identity(monkeypatch, age, identity, expected):
    job = SimpleNamespace(worker_node='local', status='uncertain', cancel_requested=True,
        process_id=123, process_boot='boot', process_started='birth')
    session = SimpleNamespace(scalars=lambda _: [job],
        get=lambda *_: SimpleNamespace(created_at=utcnow() - timedelta(seconds=age)))
    monkeypatch.setattr(cleanup_process, 'get_settings', lambda: SimpleNamespace(worker_node_name='local'))
    monkeypatch.setattr(cleanup_process, 'same_process', lambda *_: identity)
    signals = []
    monkeypatch.setattr(cleanup_process.os, 'killpg', lambda pid, sig: signals.append((pid, sig)))
    from uuid import uuid4
    assert not cleanup_process.confirmed(session, uuid4())
    assert signals == ([(123, expected)] if expected else [])
