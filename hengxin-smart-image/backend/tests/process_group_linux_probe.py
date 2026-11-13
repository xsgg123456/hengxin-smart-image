"""Real process-group regression, runnable with only the Linux standard library."""
import os
import signal
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from app.execution.process import execute, process_identity, same_process
from app.execution.process_group import group_alive
from app.execution.verified_stop import stopped


def finish_owned_group(pid, boot):
    if group_alive(pid, boot):
        os.killpg(pid, signal.SIGTERM)
    deadline = time.monotonic() + 5
    while group_alive(pid, boot) and time.monotonic() < deadline:
        time.sleep(.05)
    assert not group_alive(pid, boot), 'test-owned process group did not stop'


def run():
    leader_code = ("import subprocess,sys; "
                   "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
                   "print('ready', flush=True); sys.stdin.readline()")
    leader = subprocess.Popen([sys.executable, '-c', leader_code], start_new_session=True,
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True)
    boot, birth = process_identity(leader.pid)
    try:
        assert leader.stdout.readline().strip() == 'ready'
        leader.stdin.write('\n')
        leader.stdin.flush()
        assert leader.wait(timeout=5) == 0
        identity = {'node': 'test', 'pid': leader.pid, 'boot': boot, 'birth': birth}
        assert not same_process(leader.pid, boot, birth)
        assert group_alive(leader.pid, boot)
        assert not stopped(identity, 'test')
        assert group_alive(leader.pid, boot), 'verification must not signal an orphaned group'
    finally:
        finish_owned_group(leader.pid, boot)
        leader.stdin.close()
        leader.stdout.close()
    assert stopped(identity, 'test')

    child_code = ("import subprocess,sys,time; "
                  "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30)']); "
                  "time.sleep(.4)")
    identity = []
    with tempfile.TemporaryDirectory(prefix='hengxin-process-group-') as control:
        try:
            try:
                execute([sys.executable, '-c', child_code], '', control, 5, lambda: False,
                        lambda pid, boot, birth: identity.append((pid, boot, birth)))
            except RuntimeError as exc:
                assert str(exc) == 'Execution process group has not exited'
            else:
                raise AssertionError('a live child must prevent an exit receipt')
            assert identity and not (Path(control) / 'exit.json').exists()
            assert group_alive(identity[0][0], identity[0][1])
        finally:
            if identity:
                finish_owned_group(identity[0][0], identity[0][1])


if __name__ == '__main__':
    run()
    print('Linux process-group verification passed')
