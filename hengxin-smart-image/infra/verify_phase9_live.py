"""Root-only, disposable Ubuntu HTTP -> worker -> real Codex smoke test.

Run with backend/.venv/bin/python; this spends one real image generation.
Only output PNGs, sanitized service logs and a JSON report survive cleanup.
"""
import argparse
import io
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import zipfile

import httpx
from phase9_live_processes import Lifecycle, require
from PIL import Image


IMAGES = {
    'postgres': 'postgres:16.15@sha256:f1c3376c26f2609ab9f29f71f824103fe2fcd8ee0346485cb6122a4f93df6f94',
    'redis': 'redis:8.8-alpine@sha256:8096655e437712b07503796fb64d81359256cfcff0ab29d95a7da72863786efb',
    'minio': 'minio/minio:RELEASE.2025-09-07T16-13-09Z@sha256:14cea493d9a34af32f524e538b8346cf79f3321eff8e708c1e2960462bd8936e',
}
INPUT = Path('/home/codex/image-workspace/wallpaper-swap-02/input')
SKILL = Path('/home/codex/.agents/skills/ecommerce-wallpaper-swap/SKILL.md')






class Smoke(Lifecycle):
    images = IMAGES
    def __init__(self, args):
        import pwd
        self.args = args
        self.account = pwd.getpwnam('codex')
        self.backend = Path(__file__).resolve().parent.parent / 'backend'
        self.python = self.backend / '.venv/bin/python'
        require(self.python.is_file(), 'backend venv missing')
        self.root = Path(tempfile.mkdtemp(prefix='hengxin-phase9-live-', dir='/tmp')).resolve()
        os.chown(self.root, self.account.pw_uid, self.account.pw_gid)
        self.root.chmod(0o700)
        self.tag = 'hx-p9-' + secrets.token_hex(8)
        self.containers, self.volumes, self.processes, self.handles = [], [], [], []
        self.descendants = {}
        self.secrets = [secrets.token_hex(24) for _ in range(3)]
        self.env = {'PATH': '/usr/local/bin:/usr/sbin:/usr/bin:/bin', 'HOME': self.account.pw_dir,
                    'LANG': 'C.UTF-8', 'PYTHONUNBUFFERED': '1', 'PYTHONDONTWRITEBYTECODE': '1'}
        self.report = {'status': 'failed', 'run': self.tag}

    def redact(self, value):
        for secret in self.secrets:
            value = value.replace(secret, '[REDACTED]')
        value = re.sub(r'(?i)(bearer\s+)[^\s"\']+', r'\1[REDACTED]', value)
        value = re.sub(r'(?i)((?:access_token|refresh_token|id_token|api_key|authorization)["\s:=]+)[^\s,"}]+',
                       r'\1[REDACTED]', value)
        return value






    def run(self):
        pg = self.container('postgres', 5432, '/var/lib/postgresql/data',
                            {'POSTGRES_DB': 'hengxin', 'POSTGRES_USER': 'hengxin', 'POSTGRES_PASSWORD': self.secrets[0]})
        redis = self.container('redis', 6379, '/data', command=['redis-server', '--appendonly', 'yes'])
        minio = self.container('minio', 9000, '/data',
                              {'MINIO_ROOT_USER': self.secrets[1], 'MINIO_ROOT_PASSWORD': self.secrets[2]},
                              ['server', '/data'])
        for name in ('execution', 'skills'):
            path = self.root / name
            path.mkdir(mode=0o700)
            os.chown(path, self.account.pw_uid, self.account.pw_gid)
        self.env.update(APP_ENV='test', ENABLE_CODEX_EXECUTOR='true', ENABLE_FIXTURE_EXECUTOR='false',
                        ENABLE_DEV_IDENTITY='true', DEV_USER_ROLE='super_admin', ENABLE_TEST_JOBS='false',
                        DATABASE_URL=f'postgresql+psycopg://hengxin:{self.secrets[0]}@{pg}/hengxin',
                        REDIS_URL=f'redis://{redis}/0', MINIO_ENDPOINT=minio,
                        MINIO_ACCESS_KEY=self.secrets[1], MINIO_SECRET_KEY=self.secrets[2],
                        MINIO_BUCKET=self.tag, MINIO_SECURE='false', GENERATION_CONCURRENCY='1',
                        CODEX_TIMEOUT_SECONDS='3600', QUEUE_VISIBILITY_SECONDS='4200',
                        CODEX_BINARY=str(self.args.codex_binary), CODEX_AUTH_FILE=str(self.args.auth_file),
                        CODEX_BWRAP_BINARY=str(self.args.bwrap_binary),
                        CODEX_EXECUTION_ROOT=str(self.root / 'execution'), SKILL_INSTALL_ROOT=str(self.root / 'skills'),
                        WORKER_NODE_NAME=self.tag, OUTBOX_POLL_SECONDS='0.5')
        self.command(['-c', 'from app.core.config import get_settings; get_settings()'], app=True)
        self.wait(lambda: subprocess.run(['docker', 'exec', self.tag + '-postgres', 'pg_isready',
                                         '-U', 'hengxin', '-d', 'hengxin'], capture_output=True).returncode == 0,
                  90, 'Postgres')
        self.wait(lambda: httpx.get(f'http://{minio}/minio/health/ready', timeout=3).status_code == 200,
                  90, 'MinIO')
        self.command(['-m', 'alembic', 'upgrade', 'head'], app=True)
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        self.start('api', ['-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', str(port)])
        worker_args = ['worker', '--pool=prefork', '--concurrency=1', '--loglevel=INFO', '--hostname=' + self.tag]
        if self.args.crash_before_publish:
            # Fault injection stays in this disposable process, never production code.
            script = ('import os\nfrom app.execution import codex_runner\n'
                      'def crash(*args, **kwargs):\n'
                      '    print("PHASE9_INJECTED_EXIT_BEFORE_PUBLISH", flush=True)\n'
                      '    os._exit(71)\n'
                      'codex_runner.publish_results = crash\n'
                      'from app.worker.celery_app import celery_app\n'
                      'celery_app.worker_main(' + repr(worker_args) + ')\n')
            self.start('worker', ['-c', script])
        else:
            self.start('worker', ['-m', 'celery', '-A', 'app.worker.celery_app:celery_app', *worker_args])
        self.start('outbox', ['-m', 'app.worker.outbox'])
        with httpx.Client(base_url=f'http://127.0.0.1:{port}', timeout=30, trust_env=False) as client:
            self.wait(lambda: client.get('/api/v1/health/ready').status_code == 200, 90, 'API ready')

            def request(method, path, **kwargs):
                response = client.request(method, path, **kwargs)
                require(response.is_success, f'{method} {path}: HTTP {response.status_code}: ' + self.redact(response.text[:1500]))
                return response.json()

            uploaded = []
            for filename, mime in [('target-page-02.jpg', 'image/jpeg'), ('wallpaper-reference.png', 'image/png')]:
                with (INPUT / filename).open('rb') as stream:
                    uploaded.append(request('POST', '/api/v1/files', files={'file': (filename, stream, mime)}))
            package = io.BytesIO()
            with zipfile.ZipFile(package, 'w', zipfile.ZIP_DEFLATED) as archive:
                archive.writestr('SKILL.md', SKILL.read_bytes())
            skill = request('POST', '/api/v1/management/skills', data={'mode': 'wallpaper', 'version': '1.0.0'},
                            files={'file': ('ecommerce-wallpaper-swap.zip', package.getvalue(), 'application/zip')})
            request('POST', f"/api/v1/management/skills/{skill['id']}/install")

            def installed():
                rows = request('GET', '/api/v1/management/skills')
                row = next(row for row in rows if row['id'] == skill['id'])
                require(row['status'] != 'failed', 'Skill installation failed: ' + str(row.get('error')))
                return row['status'] == 'available'

            self.wait(installed, 120, 'Skill install')
            template = request('POST', '/api/v1/templates', json={'name': 'Phase9真实烟测模板', 'mode': 'wallpaper',
                               'images': [uploaded[0]], 'skillVersionId': skill['id'], 'active': True, 'notes': ''})
            body = {'mode': 'wallpaper', 'name': 'Phase9真实壁纸替换', 'sku': self.tag, 'sources': [uploaded[1]],
                    'note': '将模板中手机屏幕内的壁纸替换成来源壁纸，保留其余页面、硬件和文字，只生成一张PNG。',
                    'skillVersionId': skill['id'], 'templateId': template['id'], 'templateVersion': template['version']}
            headers = {'Idempotency-Key': self.tag}
            receipt = request('POST', '/api/v1/tasks', json=body, headers=headers)
            self.report['receipt'] = receipt
            require(request('POST', '/api/v1/tasks', json=body, headers=headers) == receipt, 'Idempotency replay differed')

            def completed():
                detail = request('GET', '/api/v1/tasks/' + receipt['taskId'])
                self.report['detail'] = detail
                if (self.args.crash_before_publish and detail['executionControl']['blockedReason']
                        == '执行状态待核实，禁止返工或重试'):
                    self.report['observedUncertain'] = True
                    return None
                require(detail['task']['state'] != '失败', 'Real generation failed: ' + str(detail['task'].get('error')))
                return detail if detail['task']['state'] == '待查看' else None

            detail = self.wait(completed, 600, 'Single image smoke (business timeout remains 3600s)')
            task = detail['task']
            require(task['sessionId'] and task['executionSource'] == 'cli', 'Missing real CLI session evidence')
            require(len(task['images']) == 1 and len(detail['slots']) == 1, 'Expected one output slot')
            require(request('POST', '/api/v1/tasks', json=body, headers=headers) == receipt, 'Completed replay differed')
            response = client.get(task['images'][0]['url'])
            require(response.is_success, 'Result download failed')
            with Image.open(io.BytesIO(response.content)) as picture:
                require(picture.format == 'PNG', 'Output must be PNG')
                picture.load()
                self.report['imageSize'] = list(picture.size)
            (self.args.output_dir / 'result.png').write_bytes(response.content)
            stats_code = '''import json
from sqlalchemy import create_engine, text
from app.core.config import get_settings
with create_engine(get_settings().database_url).connect() as c:
    values = {name: c.execute(text('SELECT count(*) FROM ' + name)).scalar_one() for name in
              ('task_records', 'task_requests', 'execution_rounds', 'execution_attempts', 'execution_sessions', 'image_versions')}
    values['execution_count'] = c.execute(text("SELECT execution_count FROM job_records WHERE kind = 'generation'")).scalar_one()
    values['config'] = c.execute(text('SELECT execution_config FROM execution_rounds')).scalar_one()
    print(json.dumps(values))
'''
            stats = json.loads(self.command(['-c', stats_code], app=True))
            self.report['database'] = stats
            if self.args.crash_before_publish:
                require('PHASE9_INJECTED_EXIT_BEFORE_PUBLISH' in (self.root / 'worker.log').read_text(),
                        'Worker fault was not injected')
                self.report['recoveredAfterWorkerExit'] = True
            require(all(value == 1 for key, value in stats.items() if key != 'config'), 'Duplicate execution or records')
            require(stats['config']['automaticRetries'] == 0 and stats['config']['timeoutSeconds'] == 3600,
                    'Execution policy mismatch')
            self.report['status'] = 'passed'



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', required=True, type=Path, help='New absolute directory containing test artifacts only')
    parser.add_argument('--codex-binary', required=True, type=Path)
    parser.add_argument('--auth-file', required=True, type=Path, help='Existing codex-readable auth; never exported')
    parser.add_argument('--crash-before-publish', action='store_true', help='Exit worker child after real upload; recover without another CLI call')
    parser.add_argument('--bwrap-binary', type=Path, default=Path('/opt/hengxin-runtime/bwrap'))
    args = parser.parse_args()
    require(os.name == 'posix' and os.geteuid() == 0, 'Run on Ubuntu as root')
    require(args.output_dir.is_absolute(), '--output-dir must be absolute')
    args.output_dir = args.output_dir.resolve()
    require(not args.output_dir.exists(), '--output-dir must be a new dedicated directory')
    for path in (args.codex_binary, args.auth_file, args.bwrap_binary, SKILL,
                 INPUT / 'target-page-02.jpg', INPUT / 'wallpaper-reference.png'):
        require(path.is_absolute() and path.is_file(), 'Missing absolute input: ' + str(path))
    args.output_dir.mkdir(parents=True, mode=0o700)
    smoke = Smoke(args)

    def interrupted(signum, frame):
        raise InterruptedError('Interrupted; cleaning disposable smoke resources')

    signal.signal(signal.SIGTERM, interrupted)
    signal.signal(signal.SIGINT, interrupted)
    try:
        smoke.run()
    except Exception as error:
        smoke.report['error'] = smoke.redact(str(error))
    finally:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
        signal.signal(signal.SIGINT, signal.SIG_IGN)
        try:
            smoke.cleanup()
        except Exception as error:
            smoke.report['status'] = 'failed'
            smoke.report['cleanupFailure'] = smoke.redact(str(error))
        (args.output_dir / 'report.json').write_text(smoke.redact(json.dumps(smoke.report, ensure_ascii=False, indent=2)), encoding='utf-8')
    print(smoke.report['status'] + ': ' + str(args.output_dir / 'report.json'))
    return 0 if smoke.report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
