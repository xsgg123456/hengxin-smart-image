"""Linux subreaper: kernel adoption owns descendants, ECHILD proves completion."""
import ctypes
import os
from pathlib import Path
import signal
import sys
import time

from phase11a_processes import process_stat, signal_owned


def supervise(status_fd, argv):
    stopping = False

    def request_stop(signum, frame):
        nonlocal stopping
        stopping = True

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    signal.signal(signal.SIGCHLD, signal.SIG_DFL)
    libc = ctypes.CDLL(None, use_errno=True)
    # Establish adoption before *any* fork. Failure must never run the command.
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER
        raise OSError(ctypes.get_errno(), 'Cannot establish subreaper')
    parent = os.getppid()
    if libc.prctl(1, signal.SIGTERM, 0, 0, 0) != 0:  # PR_SET_PDEATHSIG
        raise OSError(ctypes.get_errno(), 'Cannot establish parent death signal')
    if parent == 1 or os.getppid() != parent:
        stopping = True
    os.write(status_fd, b'R')
    root = os.fork()
    if root == 0:
        os.close(status_fd)
        signal.signal(signal.SIGTERM, signal.SIG_DFL)
        signal.signal(signal.SIGINT, signal.SIG_DFL)
        os.setsid()
        try:
            os.execvpe(argv[0], argv, os.environ)
        except Exception:
            os._exit(127)  # Never export arguments or environment in a traceback.

    root_status, deadline, sent = None, None, set()
    children_path = Path(f'/proc/self/task/{os.getpid()}/children')
    while True:
        while True:
            try:
                pid, status = os.waitpid(-1, os.WNOHANG)
            except ChildProcessError:
                # With a living subreaper, no direct child means no descendants.
                os.write(status_fd, b'D')
                os.close(status_fd)
                code = os.waitstatus_to_exitcode(root_status)
                return code if code >= 0 else 128 - code
            if pid == 0:
                break
            if pid == root:
                root_status, stopping = status, True
        if stopping:
            if deadline is None:
                deadline = time.monotonic() + 8
            sig = signal.SIGKILL if time.monotonic() >= deadline else signal.SIGTERM
            # Only our direct children: each stays our child (possibly zombie)
            # until this single-threaded loop reaps it. No PPID scan/reuse race.
            # Killing a parent adopts its children; repeat until waitpid ECHILD.
            for value in children_path.read_text().split():
                pid = int(value)
                stat = process_stat(pid)
                if stat and stat[0] == os.getpid():
                    identity = (pid, stat[2], sig)
                    if identity not in sent:
                        signal_owned(pid, stat[2], sig)
                        sent.add(identity)
        time.sleep(.02)


if __name__ == '__main__':
    try:
        result = supervise(int(sys.argv[1]), sys.argv[2:])
    except Exception:
        result = 125  # No completion marker: controller must fail cleanup closed.
    sys.exit(result)
