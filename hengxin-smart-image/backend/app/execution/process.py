"""Bounded process execution; control evidence stays outside the model mount."""
import json
import os
import signal
import subprocess
import time
from pathlib import Path


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


def execute(argv, prompt, control, timeout, should_stop, on_start):
    control = Path(control)
    request = control / 'request.txt'
    request.write_text(prompt)
    started = time.monotonic()
    reason = None
    with request.open('rb') as stdin, (control / 'events.jsonl').open('wb') as out, \
            (control / 'stderr.log').open('wb') as err:
        process = subprocess.Popen(argv, stdin=stdin, stdout=out, stderr=err,
                                   start_new_session=True, close_fds=True)
        try:
            boot, birth = process_identity(process.pid)
            on_start(process.pid, boot, birth)
            while process.poll() is None:
                if should_stop():
                    reason = 'cancelled'
                    break
                if time.monotonic() - started >= timeout:
                    reason = 'timeout'
                    break
                # Logs are not permitted to exhaust the server disk.
                if (control / 'events.jsonl').stat().st_size + (control / 'stderr.log').stat().st_size > 64 * 1024 * 1024:
                    reason = 'output_limit'
                    break
                time.sleep(.2)
        finally:
            stop_process(process)
    receipt = {'exit_code': process.returncode, 'reason': reason,
               'elapsed_seconds': round(time.monotonic() - started, 3)}
    temporary = control / 'exit.tmp'
    temporary.write_text(json.dumps(receipt))
    temporary.replace(control / 'exit.json')
    return receipt
