"""Disposable Phase11A WSL environment. Starting it never submits a model job."""
import ast
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import time

import httpx
from local_codex_worker import configuration
from phase11a_processes import Processes, require


class Phase11AEnvironment(Processes):
    def __init__(self, output_dir: Path):
        import pwd
        require(os.name == 'posix' and os.getuid() != 0 and pwd.getpwuid(os.getuid()).pw_name == 'hengxin',
                'Run as non-root hengxin in Ubuntu-24.04')
        self.output_dir = Path(output_dir).absolute()
        self.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        require(os.access(self.output_dir, os.W_OK), 'Output directory is not writable')
        self.backend = Path(__file__).resolve().parents[1] / 'backend'
        self.python = Path('/home/hengxin/runtime/venv/bin/python')
        require(self.python.is_file(), 'Existing WSL Python runtime is missing')
        self.tag = 'hx-p11a-' + secrets.token_hex(8)
        self.root = Path(tempfile.mkdtemp(prefix='hengxin-phase11a-', dir='/tmp')).resolve()
        self._root_identity = (self.root.stat().st_dev, self.root.stat().st_ino)
        self.containers, self.volumes = [], []
        self.worker_process, self.base_url = None, ''
        self.env = {'PATH': '/usr/local/bin:/usr/bin:/bin', 'HOME': str(self.root / 'home'),
                    'LANG': 'C.UTF-8', 'PYTHONUNBUFFERED': '1', 'PYTHONDONTWRITEBYTECODE': '1',
                    'PYTHONPATH': str(self.backend), 'GENERATION_CONCURRENCY': '1'}
        self.report = {'run': self.tag, 'status': 'created', 'concurrency': 1,
                       'modelCallsSubmittedByHelper': 0, 'defaultConcurrencyRestored': False}
        self.init_processes()

    def __enter__(self):
        try:
            self._boot()
            self.report['status'] = 'ready'
            return self
        except BaseException:
            self.report['status'] = 'startup-failed'
            self.cleanup()
            raise

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.report['status'] = 'failed'
        self.cleanup()

    def _docker(self):
        for candidate in ('docker', 'docker.exe'):
            path = shutil.which(candidate)
            if path:
                try:
                    result = subprocess.run([path, 'version', '--format', '{{.Server.Version}}'],
                                            capture_output=True, timeout=15, text=True)
                    if result.returncode == 0 and result.stdout.strip():
                        return path
                except (OSError, subprocess.TimeoutExpired):
                    pass
        raise RuntimeError('Neither docker nor docker.exe can reach Docker Desktop')

    def container(self, kind, port, mount, values=None, command=()):
        name, label = self.tag + '-' + kind, 'hengxin.phase11a=' + self.tag
        volume = name + '-data'
        self.volumes.append(volume)
        self.command([self.docker, 'volume', 'create', '--label', label, volume])
        self.containers.append(name)
        args = [self.docker, 'run', '--pull=never', '-d', '--name', name, '--label', label,
                '-p', f'127.0.0.1::{port}', '-v', f'{volume}:{mount}']
        for key, value in (values or {}).items():
            args += ['-e', f'{key}={value}']
        self.command([*args, self.images[kind], *command])
        binding = self.command([self.docker, 'port', name, f'{port}/tcp'])
        import re
        require(re.fullmatch(r'127\.0\.0\.1:\d+', binding), 'Docker port must be private')
        return binding

    def _boot(self):
        infra = Path(__file__).resolve().parent
        configured = configuration(infra / '.env', infra / '.env.local-codex')
        require(configured['CODEX_AUTH_FILE'] == '/home/hengxin/auth/auth.json', 'Unexpected auth reference')
        for key in ('CODEX_BINARY', 'CODEX_BWRAP_BINARY', 'CODEX_AUTH_FILE'):
            require(Path(configured[key]).is_file(), 'Missing required CLI runtime file: ' + key)
            self.env[key] = configured[key]
        self.env['HENGXIN_CODEX_PROXY_URL'] = configured.get('HENGXIN_CODEX_PROXY_URL', '')
        for name in ('execution', 'skills', 'home'):
            (self.root / name).mkdir(mode=0o700)
        self.docker = self._docker()
        # Parse constants only: do not import the historical root/runuser harness.
        tree = ast.parse((infra / 'verify_phase9_live.py').read_text())
        self.images = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                           and any(isinstance(t, ast.Name) and t.id == 'IMAGES' for t in n.targets))
        for image in self.images.values():
            self.command([self.docker, 'image', 'inspect', image, '--format', '{{.Id}}'])
        password, access, secret, redis_password = [secrets.token_hex(24) for _ in range(4)]
        pg = self.container('postgres', 5432, '/var/lib/postgresql/data',
                            {'POSTGRES_DB': 'hengxin', 'POSTGRES_USER': 'hengxin', 'POSTGRES_PASSWORD': password})
        redis = self.container('redis', 6379, '/data',
                               command=['redis-server', '--appendonly', 'yes', '--requirepass', redis_password])
        minio = self.container('minio', 9000, '/data',
                              {'MINIO_ROOT_USER': access, 'MINIO_ROOT_PASSWORD': secret}, ['server', '/data'])
        self.env.update(APP_ENV='test', ENABLE_CODEX_EXECUTOR='true', ENABLE_FIXTURE_EXECUTOR='false',
                        ENABLE_DEV_IDENTITY='true', DEV_USER_ROLE='super_admin', ENABLE_TEST_JOBS='false',
                        DATABASE_URL=f'postgresql+psycopg://hengxin:{password}@{pg}/hengxin',
                        REDIS_URL=f'redis://:{redis_password}@{redis}/0', MINIO_ENDPOINT=minio,
                        MINIO_ACCESS_KEY=access, MINIO_SECRET_KEY=secret, MINIO_BUCKET=self.tag,
                        MINIO_SECURE='false', CODEX_TIMEOUT_SECONDS='3600', QUEUE_VISIBILITY_SECONDS='4200',
                        CODEX_EXECUTION_ROOT=str(self.root / 'execution'), SKILL_INSTALL_ROOT=str(self.root / 'skills'),
                        WORKER_NODE_NAME=self.tag, OUTBOX_POLL_SECONDS='0.5')
        self.wait(lambda: subprocess.run([self.docker, 'exec', self.tag + '-postgres', 'pg_isready',
                                         '-U', 'hengxin', '-d', 'hengxin'], capture_output=True).returncode == 0,
                  60, 'Postgres')
        self.wait(lambda: self._http_ready(f'http://{minio}/minio/health/ready'), 60, 'MinIO')
        # Run from the private cwd so Settings never reads backend/.env implicitly.
        migration = ('from alembic.config import Config\nfrom alembic import command\n'
                     f'c=Config({str(self.backend / "alembic.ini")!r})\n'
                     f'c.set_main_option("script_location", {str(self.backend / "migrations")!r})\n'
                     'command.upgrade(c,"head")')
        self.command(['-c', migration], app=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        self.base_url = f'http://127.0.0.1:{self.port}'
        self._start_services()
        self.report.update(baseUrl=self.base_url, docker=Path(self.docker).name)

    @staticmethod
    def _http_ready(url):
        try:
            return httpx.get(url, timeout=3, trust_env=False).status_code == 200
        except httpx.TransportError:
            return False

    def start_worker(self, startup_code=None):
        args = ['worker', '--pool=prefork', '--concurrency=' + self.env['GENERATION_CONCURRENCY'],
                '--loglevel=WARNING', '--hostname=' + self.tag]
        # Injection runs before importing/starting Celery, inside this process only.
        code = (startup_code or '') + '\nfrom app.worker.celery_app import celery_app\n'
        code += 'celery_app.worker_main(' + repr(args) + ')\n'
        started = time.time()
        self.worker_process = self.start('worker', ['-c', code])
        ready = ('import json\nfrom sqlalchemy import create_engine,text\n'
                 'from app.core.config import get_settings\ns=get_settings()\n'
                 'with create_engine(s.database_url).connect() as c:\n'
                 ' r=c.execute(text("SELECT state,extract(epoch from checked_at) FROM worker_heartbeats '
                 'WHERE node=:node"),{"node":s.worker_node_name}).first()\n'
                 f' print(json.dumps(bool(r and r[0]=="ready" and float(r[1])>={started!r})))')
        self.wait(lambda: self.command(['-c', ready], app=True) == 'true', 60, 'Worker heartbeat')
        return self.worker_process

    def _start_services(self):
        self.start('api', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(self.port)])
        self.start('outbox', ['-m', 'app.worker.outbox'])
        self.start_worker()
        self.wait(lambda: self._http_ready(self.base_url + '/api/v1/health/ready'), 60, 'API dependencies')

    def _assert_idle(self):
        code = '''from sqlalchemy import create_engine,text
from app.core.config import get_settings
with create_engine(get_settings().database_url).connect() as c:
    c.execute(text("SET LOCAL statement_timeout = '5000ms'"))
    c.execute(text("SELECT id FROM execution_gate WHERE id=1 FOR UPDATE"))
    n=c.execute(text("SELECT count(*) FROM job_records WHERE status NOT IN ('succeeded','failed','cancelled','partial')")).scalar_one()
    n+=c.execute(text("SELECT count(*) FROM execution_attempts WHERE status <> 'finished'")).scalar_one()
    print(n)
'''
        require(self.command(['-c', code], app=True) == '0', 'Database is not idle; refusing restart/concurrency change')

    def restart_services(self):
        self._assert_idle()
        self.stop_services()
        self._assert_idle()
        self._start_services()
        self.report['restarts'] = self.report.get('restarts', 0) + 1

    def set_concurrency(self, n):
        require(type(n) is int and n in (1, 2), 'Concurrency must be 1 or 2')
        self._assert_idle()
        self.stop_services()
        self._assert_idle()  # A request accepted during shutdown must block the change.
        self.env['GENERATION_CONCURRENCY'] = str(n)
        self._start_services()
        self.report['concurrency'] = n


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path)
    args = parser.parse_args()
    environment = Phase11AEnvironment(args.output_dir)
    try:
        with environment:
            terminal_jobs = '''from app.db.session import session_factory
from app.models import Job
with session_factory().begin() as s:
    for status in ('succeeded', 'partial', 'failed', 'cancelled'):
        s.add(Job(idempotency_key='environment-smoke-'+status, payload_hash='environment-smoke',
                  value='', kind='test', status=status))
print('4')
'''
            require(environment.command(['-c', terminal_jobs], app=True) == '4', 'Terminal job smoke setup failed')
            environment._assert_idle()
            environment.report['terminalJobsIdleVerified'] = ['succeeded', 'partial', 'failed', 'cancelled']
            environment.set_concurrency(2)
            environment.set_concurrency(1)
            environment.restart_services()
            environment.report['smoke'] = 'passed'
    finally:
        path = args.output_dir / (environment.tag + '-report.json')
        path.write_text(json.dumps(environment.report, indent=2), encoding='utf-8')
        print(str(path))
