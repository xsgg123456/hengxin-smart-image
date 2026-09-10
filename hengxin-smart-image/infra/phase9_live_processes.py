"""Isolated service lifecycle for the Phase9 live smoke harness."""
import os
from pathlib import Path
import signal
import subprocess
import shutil
import time
import httpx

def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def process_stat(pid):
    try:
        fields = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
        return int(fields[1]), fields[19]
    except (OSError, ValueError, IndexError):
        return None


class Lifecycle:
    def command(self, argv, *, app=False, timeout=120):
        if app:
            argv = ['runuser', '-u', 'codex', '--', str(self.python), *argv]
        process = subprocess.Popen(argv, cwd=self.backend, env=self.env if app else None,
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                                   start_new_session=True)
        try:
            stdout, stderr = process.communicate(timeout=timeout)
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.communicate(timeout=10)
        require(process.returncode == 0, self.redact(stderr[-3000:]) or 'Command failed')
        return stdout.strip()


    def container(self, kind, port, mount, env=None, command=()):
        name = self.tag + '-' + kind
        volume = name + '-data'
        self.volumes.append(volume)
        self.command(['docker', 'volume', 'create', volume])
        self.containers.append(name)
        argv = ['docker', 'run', '-d', '--name', name, '--label', 'hengxin.phase9=' + self.tag,
                '-p', f'127.0.0.1::{port}', '-v', f'{volume}:{mount}']
        if env:
            env_file = self.root / (kind + '.env')
            with open(env_file, 'x', opener=lambda p, f: os.open(p, f, 0o600)) as stream:
                stream.write(''.join(f'{key}={value}\n' for key, value in env.items()))
            argv += ['--env-file', str(env_file)]
        self.command([*argv, self.images[kind], *command], timeout=300)
        binding = self.command(['docker', 'port', name, str(port) + '/tcp'])
        require(binding.startswith('127.0.0.1:') and '\n' not in binding, 'Non-private Docker binding')
        return binding


    def start(self, name, argv):
        handle = (self.root / (name + '.log')).open('wb')
        self.handles.append(handle)
        process = subprocess.Popen(['runuser', '-u', 'codex', '--', str(self.python), *argv],
                                   cwd=self.backend, env=self.env, stdout=handle, stderr=handle,
                                   start_new_session=True)
        self.processes.append(process)
        self.capture_descendants()


    def capture_descendants(self):
        table = {int(p.name): process_stat(int(p.name)) for p in Path('/proc').iterdir() if p.name.isdigit()}
        parents = {p.pid for p in self.processes}
        while True:
            found = {pid for pid, info in table.items() if info and info[0] in parents}
            if found.issubset(parents):
                break
            parents |= found
        for pid in parents:
            if table.get(pid):
                self.descendants[pid] = table[pid][1]


    def wait(self, check, seconds, label):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            self.capture_descendants()
            require(all(p.poll() is None for p in self.processes), 'Service exited while waiting for ' + label)
            try:
                value = check()
                if value:
                    return value
            except (httpx.TransportError, ConnectionError):
                pass
            time.sleep(1)
        raise TimeoutError(label + ' timeout')


    def cleanup(self):
        errors = []
        self.capture_descendants()
        # Snapshot /proc birth times prevents touching an unrelated recycled PID.
        for sig in (signal.SIGTERM, signal.SIGKILL):
            for process in self.processes:
                stat = process_stat(process.pid)
                if stat and stat[1] == self.descendants.get(process.pid):
                    try:
                        os.killpg(process.pid, sig)
                    except ProcessLookupError:
                        pass
            for pid, birth in reversed(list(self.descendants.items())):
                stat = process_stat(pid)
                if stat and stat[1] == birth:
                    try:
                        os.kill(pid, sig)
                    except ProcessLookupError:
                        pass
            for process in self.processes:
                try:
                    process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
        for handle in self.handles:
            handle.close()
        for path in self.root.glob('*.log'):
            (self.args.output_dir / path.name).write_text(self.redact(path.read_text(errors='replace')), encoding='utf-8')
        for path in self.root.glob('execution/*/control/*/*'):
            if path.name in ('events.jsonl', 'stderr.log', 'exit.json') and path.is_file():
                name = path.parent.name + '-' + path.name
                (self.args.output_dir / name).write_text(
                    self.redact(path.read_text(errors='replace')), encoding='utf-8')
        for name in self.containers:
            try:
                self.command(['docker', 'rm', '-f', name])
            except Exception as error:
                errors.append(self.redact(str(error)))
        for name in self.volumes:
            try:
                self.command(['docker', 'volume', 'rm', name])
            except Exception as error:
                errors.append(self.redact(str(error)))
        require(self.root.parent == Path('/tmp') and self.root.name.startswith('hengxin-phase9-live-')
                and not self.root.is_symlink(), 'Refusing unsafe temporary cleanup')
        shutil.rmtree(self.root)
        self.report['cleanupErrors'] = errors
        if errors:
            self.report['status'] = 'failed'


