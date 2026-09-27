"""Disposable local-only real dependency stack; never reads project .env files."""
import json
import os
from pathlib import Path
import secrets
import subprocess
import tempfile
from contextlib import contextmanager
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]


class MediaStack:
    def __init__(self):
        self.project = 'hx-media-test-' + uuid4().hex[:10]
        self.temp = tempfile.TemporaryDirectory(prefix=self.project)
        self.path = Path(self.temp.name)
        password = secrets.token_hex(20)
        self.bucket = 'media-test-' + uuid4().hex[:10]
        common = {'APP_ENV': 'test', 'PYTHONPATH': '/app', 'ENABLE_DEV_IDENTITY': 'false', 'ENABLE_TEST_JOBS': 'false',
                  'ENABLE_CODEX_EXECUTOR': 'false', 'ENABLE_FIXTURE_EXECUTOR': 'false',
                  'DATABASE_URL': f'postgresql+psycopg://media:{password}@postgres:5432/media_test',
                  'REDIS_URL': 'redis://redis:6379/0', 'MINIO_ENDPOINT': 'minio:9000',
                  'MINIO_ACCESS_KEY': 'media-local-test', 'MINIO_SECRET_KEY': password,
                  'MINIO_BUCKET': self.bucket, 'DB_POOL_SIZE': '4', 'DB_MAX_OVERFLOW': '0',
                  'API_IMAGE_ENABLED': 'true'}
        service = {'image': 'hx-perf-media:local', 'environment': common,
                   'volumes': [f'{ROOT / "scripts/performance"}:/checks:ro'],
                   'command': ['uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000', '--no-access-log']}
        # Use the actual production HTTPS server block; only TLS/listen, log
        # paths and the upstream address are adapted to the disposable network.
        outer = (ROOT / 'hengxin-smart-image/infra/nginx.zhitu.qhhengxin.top.conf').read_text(encoding='utf-8')
        outer = outer[outer.index('server {', outer.index('server {') + 1):]
        outer = '\n'.join(line for line in outer.splitlines() if not line.strip().startswith('ssl_'))
        outer = outer.replace('listen 443 ssl;', 'listen 80;')
        outer = outer.replace('access_log /www/sites/zhitu/log/access.log main;', 'access_log off;')
        outer = outer.replace('error_log /www/sites/zhitu/log/error.log;', 'error_log /dev/stderr warn;')
        outer = outer.replace('proxy_pass http://127.0.0.1:18080;', 'proxy_pass http://web;')
        (self.path / 'outer.conf').write_text(outer, encoding='utf-8')
        # Production gateway config is tested verbatim with two worker processes.
        (self.path / 'nginx.conf').write_text('worker_processes 2; events { worker_connections 1024; } http { include /etc/nginx/conf.d/*.conf; }', encoding='utf-8')
        services = {
            'postgres': {'image': 'postgres:16', 'environment': {'POSTGRES_DB': 'media_test', 'POSTGRES_USER': 'media', 'POSTGRES_PASSWORD': password}, 'tmpfs': ['/var/lib/postgresql/data']},
            'redis': {'image': 'redis:8.8-alpine', 'command': ['redis-server', '--save', '', '--appendonly', 'no']},
            'minio': {'image': 'itpc-minio:14cea493d9a3', 'command': ['server', '/data'], 'tmpfs': ['/data'],
                      'environment': {'MINIO_ROOT_USER': 'media-local-test', 'MINIO_ROOT_PASSWORD': password}},
            'api': {**service, 'ports': ['127.0.0.1::8000']},
            'media-api': {**service, 'environment': {**common, 'MEDIA_INTERNAL_DELIVERY_ENABLED': 'true'},
                          'mem_limit': '3g', 'memswap_limit': '3g', 'cpus': 2, 'tmpfs': ['/tmp:size=1280m,mode=1777']},
            'web': {'image': 'nginx:1.27-alpine', 'ports': ['127.0.0.1::80'], 'volumes': [
                f'{ROOT / "hengxin-smart-image/infra/nginx.media.conf"}:/etc/nginx/conf.d/default.conf:ro',
                f'{self.path / "nginx.conf"}:/etc/nginx/nginx.conf:ro']},
            'outer': {'image': 'nginx:1.27-alpine', 'ports': ['127.0.0.1::80'],
                      'volumes': [f'{self.path / "outer.conf"}:/etc/nginx/conf.d/default.conf:ro']},
        }
        self.compose_file = self.path / 'compose.json'
        self.compose_file.write_text(json.dumps({'services': services}), encoding='utf-8')

    def run(self, *args, check=True, timeout=90):
        command = ['docker', 'compose', '-p', self.project, '-f', str(self.compose_file), *args]
        result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=timeout,
                                creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        if check and result.returncode:
            raise RuntimeError(result.stdout + result.stderr)
        return result

    def origin(self, name, port=80):
        value = self.run('port', name, str(port)).stdout.strip()
        assert value.startswith('127.0.0.1:')
        return 'http://' + value

    def seed(self, *args):
        return self.run('exec', '-T', 'api', 'python', '/checks/media_seed.py', *args).stdout.strip()

    @contextmanager
    def slow_images(self, path, cookie):
        command = ['docker', 'compose', '-p', self.project, '-f', str(self.compose_file),
                   'exec', '-T', 'api', 'python', '/checks/media_hold.py']
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, encoding='utf-8',
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        try:
            process.stdin.write(json.dumps({'count': 32, 'path': path, 'cookie': cookie}) + '\n')
            process.stdin.flush()
            assert json.loads(process.stdout.readline()) == [200] * 32
            yield
        finally:
            process.communicate('\n', timeout=50)
            assert process.returncode == 0

    def close(self):
        self.run('down', '--volumes', '--remove-orphans', timeout=120)
        assert self.path.resolve().parent == Path(tempfile.gettempdir()).resolve()
        assert self.path.name.startswith(self.project)
        self.temp.cleanup()
