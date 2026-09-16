"""Non-root, PID-birth-owned processes for the disposable Phase11A environment."""
import os
from pathlib import Path
import re
import select
import signal
import subprocess
import threading
import time


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def process_stat(pid):
    try:
        path = Path('/proc') / str(pid)
        fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
        return (int(fields[1]), int(fields[3]), fields[19], fields[0], path.stat().st_uid)
    except (OSError, ValueError, IndexError):
        return None


def signal_owned(pid, birth, sig):
    """The pidfd closes the check-to-signal PID reuse race."""
    try:
        fd = os.pidfd_open(pid)
    except ProcessLookupError:
        return
    try:
        stat = process_stat(pid)
        if stat and stat[2] == birth and stat[4] == os.getuid():
            try:
                signal.pidfd_send_signal(fd, sig)
            except ProcessLookupError:
                pass
    finally:
        os.close(fd)


class Processes:
    def init_processes(self):
        self.processes, self.owned, self.named = [], {}, {}
        self._lock, self._done = threading.RLock(), threading.Event()
        self._watcher = threading.Thread(target=self._watch, daemon=True)
        self._watcher.start()

    def _watch(self):
        while not self._done.wait(0.1):
            self.capture_descendants()

    def capture_descendants(self):
        with self._lock:
            table = {int(p.name): process_stat(int(p.name))
                     for p in Path('/proc').iterdir() if p.name.isdigit()}
            for owner, births in self.owned.items():
                live = {pid for pid, birth in births.items()
                        if table.get(pid) and table[pid][2] == birth}
                while True:
                    found = {pid for pid, s in table.items() if s and s[4] == os.getuid()
                             and s[0] in live}
                    if found.issubset(live):
                        break
                    live |= found
                for pid in live:
                    births[pid] = table[pid][2]

    def _launch(self, args, *, app, pipes=False):
        read_fd, write_fd = os.pipe()
        try:
            process = subprocess.Popen(
                [str(self.python), str(Path(__file__).with_name('phase11a_supervisor.py')),
                 str(write_fd), *args], cwd=self.root, env=self.env if app else None,
                stdout=subprocess.PIPE if pipes else subprocess.DEVNULL,
                stderr=subprocess.PIPE if pipes else subprocess.DEVNULL,
                text=True, start_new_session=True, pass_fds=(write_fd,))
        except BaseException:
            os.close(read_fd)
            raise
        finally:
            os.close(write_fd)
        process._status_fd, process._cleaned = read_fd, False
        stat = process_stat(process.pid)
        process._birth = stat[2] if stat else None
        with self._lock:
            self.owned[process.pid] = {process.pid: process._birth} if stat else {}
            self.processes.append(process)  # Commands also survive failed cleanup for retry.
        try:
            require(select.select([read_fd], [], [], 10)[0]
                    and os.read(read_fd, 1) == b'R', 'Process supervisor did not become ready')
        except BaseException:
            self._stop(process)
            raise
        return process

    def command(self, argv, *, app=False, timeout=120):
        args = [str(self.python), *map(str, argv)] if app else list(map(str, argv))
        process = self._launch(args, app=app, pipes=True)
        try:
            stdout, _ = process.communicate(timeout=timeout)
            require(process.returncode == 0, 'Isolated command failed (output suppressed)')
            return stdout.strip()
        except subprocess.TimeoutExpired:
            raise TimeoutError('Isolated command timed out (arguments/output suppressed)') from None
        finally:
            self._stop(process)
            if process.stdout:
                process.stdout.close()
            if process.stderr:
                process.stderr.close()

    def start(self, name, argv):
        require(re.fullmatch(r'[a-z][a-z0-9_-]*', name), 'Invalid process name')
        require(name not in self.named or self.named[name].poll() is not None,
                'Named process is already running')
        process = self._launch([str(self.python), *map(str, argv)], app=True)
        with self._lock:
            self.named[name] = process
        return process

    def _stop(self, process):
        if process._cleaned:
            return
        # Never KILL the subreaper: it must live until every adopted child is reaped.
        # Discovery is diagnostic only; the supervisor owns and signals children.
        if process.poll() is None:
            signal_owned(process.pid, process._birth, signal.SIGTERM)
        try:
            process.wait(timeout=12)
        except subprocess.TimeoutExpired:
            raise RuntimeError('Owned process supervisor did not finish cleanup') from None
        marker = os.read(process._status_fd, 1) if process._status_fd is not None else b''
        if process._status_fd is not None:
            os.close(process._status_fd)
            process._status_fd = None
        require(marker == b'D', 'Process supervisor did not confirm descendant cleanup')
        process._cleaned = True
        with self._lock:
            self.owned.pop(process.pid, None)

    def stop_worker(self):
        if self.worker_process is not None:
            self._stop(self.worker_process)

    def stop_services(self):
        # Close ingress before stopping dispatch and consumers.
        for name in ('api', 'outbox', 'worker'):
            if name in self.named:
                self._stop(self.named[name])

    def wait(self, check, seconds, label):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            require(all(p.poll() is None for p in self.named.values()),
                    'Service exited while waiting for ' + label)
            try:
                if value := check():
                    return value
            except (ConnectionError, OSError):
                pass
            time.sleep(0.5)
        raise TimeoutError(label + ' timeout')

    def remove_resource(self, kind, name):
        require(name.startswith(self.tag + '-'), 'Resource name is outside this run')
        listing = [self.docker, kind, 'ls', *(['-a'] if kind == 'container' else []),
                   '--filter', 'name=' + name, '--format', '{{.Name}}' if kind == 'volume' else '{{.Names}}']
        if name not in self.command(listing).splitlines():
            return  # A failed create may never have allocated this tracked name.
        info = self.command([self.docker, kind, 'inspect', name, '--format', '{{json .}}'])
        import json
        data = json.loads(info)
        labels = data.get('Labels') if kind == 'volume' else data.get('Config', {}).get('Labels')
        require((labels or {}).get('hengxin.phase11a') == self.tag, 'Resource label mismatch')
        args = [self.docker, kind, 'rm']
        self.command([*args, *(['-f'] if kind == 'container' else []), name])

    def cleanup(self):
        if self.report.get('cleanupComplete'):
            return
        errors = []
        for process in reversed(self.processes):
            try:
                self._stop(process)
            except Exception:
                errors.append('owned-process-cleanup-failed')
        if not errors:
            self._done.set()
            self._watcher.join(timeout=2)
        for kind, names in (('container', self.containers), ('volume', self.volumes)):
            for name in list(names):
                try:
                    self.remove_resource(kind, name)
                    names.remove(name)
                except Exception:
                    errors.append(kind + '-cleanup-failed: ' + name)
        self.env['GENERATION_CONCURRENCY'] = '1'
        self.report.update(defaultConcurrencyRestored=True, concurrency=1)
        try:
            import shutil
            if getattr(self, '_root_removed', False):
                self.report.update(cleanupErrors=errors, cleanupComplete=not errors)
                require(not errors, 'Resource cleanup incomplete')
                return
            require(self.root.parent == Path('/tmp') and self.root.name.startswith('hengxin-phase11a-')
                    and not self.root.is_symlink() and self.root.resolve() == self.root
                    and self.root.stat().st_uid == os.getuid()
                    and (self.root.stat().st_dev, self.root.stat().st_ino) == self._root_identity,
                    'Unsafe temporary directory cleanup')
            require('owned-process-cleanup-failed' not in errors, 'Processes still running')
            shutil.rmtree(self.root)
            self._root_removed = True
        except Exception:
            errors.append('temporary-directory-cleanup-failed')
        self.report.update(cleanupErrors=errors, cleanupComplete=not errors)
        require(not errors, 'Phase11A cleanup incomplete; see report')
