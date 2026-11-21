"""Bounded process execution; control evidence stays outside the model mount."""
import errno
import json
import os
import selectors
import signal
import subprocess
import time
from pathlib import Path
from contextlib import ExitStack
from app.execution.log_capture import LogCapture
from app.execution.process_group import group_alive


def process_identity(pid):
    stat = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
    return (Path('/proc/sys/kernel/random/boot_id').read_text().strip(), stat[19])


def same_process(pid, boot, started):
    if not Path('/proc/sys/kernel/random/boot_id').is_file():
        raise OSError('Process identity infrastructure unavailable')
    try:
        return process_identity(pid) == (boot, started)
    except FileNotFoundError:
        return False


def stop_process(process):
    if process.poll() is None:
        os.killpg(process.pid, signal.SIGTERM)
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
    return process.returncode


def _collect(process, capture, deadline, should_stop, boot):
    next_check = 0
    verified_exit = False
    with selectors.DefaultSelector() as pipes:
        for stream, channel in ((process.stdout, 'stdout'), (process.stderr, 'stderr')):
            pipes.register(stream, selectors.EVENT_READ, channel)
        while True:
            exited = process.poll() is not None
            if exited and not verified_exit:
                if group_alive(process.pid, boot):
                    raise RuntimeError('Execution process group has not exited')
                verified_exit = True
            now = time.monotonic()
            if now >= next_check:
                capture.flush_events()
                if not exited:
                    if should_stop():
                        return 'cancelled'
                    if now >= deadline:
                        return 'timeout'
                next_check = now + .2
            if exited and not pipes.get_map():
                break
            ready = pipes.select(0 if exited else max(0, min(next_check, deadline) - now))
            if not ready and exited:
                # The leader is reaped and its pipes have no pending data.
                break
            for key, _ in ready:
                data = os.read(key.fd, 64 * 1024)
                if data:
                    capture.feed(key.data, data)
                else:
                    pipes.unregister(key.fileobj)
    return None


def execute(argv, prompt, control, timeout, should_stop, on_start):
    control = Path(control)
    request = control / 'request.txt'
    (control / 'exit.json').unlink(missing_ok=True)
    request.write_text(prompt, encoding='utf-8')
    started = time.monotonic()
    reason = None
    process = None
    try:
        with ExitStack() as files:
            stdin = files.enter_context(request.open('rb'))
            capture = LogCapture(control, files)
            process = subprocess.Popen(argv, stdin=stdin, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       start_new_session=True, close_fds=True)
            files.enter_context(process.stdout)
            files.enter_context(process.stderr)
            try:
                boot, birth = process_identity(process.pid)
                on_start(process.pid, boot, birth)
                reason = _collect(process, capture, started + timeout, should_stop, boot)
                capture.finish()
            finally:
                stop_process(process)
    except OSError as exc:
        if process is None or exc.errno not in (errno.ENOSPC, errno.EDQUOT, errno.EIO, errno.EFBIG):
            raise
        reason = 'storage_failed'
    # A leader can exit before another process in its group. Never publish an
    # exit receipt or release execution capacity until the group is gone.
    if group_alive(process.pid, boot):
        raise RuntimeError('Execution process group has not exited')
    receipt = {'exit_code': process.returncode, 'reason': reason,
               'elapsed_seconds': round(time.monotonic() - started, 3)}
    temporary = control / 'exit.tmp'
    temporary.write_text(json.dumps(receipt))
    temporary.replace(control / 'exit.json')
    return receipt
