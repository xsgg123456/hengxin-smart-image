"""Linux integration checks in a fresh Compose project; never use development volumes."""
import hashlib
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'hx-phase5-test-' + uuid4().hex[:10]


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    ports = [free_port() for _ in range(4)]
    env = dict(os.environ, POSTGRES_PASSWORD=secrets.token_hex(24),
               MINIO_ACCESS_KEY='phase5-test', MINIO_SECRET_KEY=secrets.token_hex(24),
               APP_ENV='test', ENABLE_TEST_JOBS='true', API_PORT=str(ports[0]),
               POSTGRES_PORT=str(ports[1]), MINIO_PORT=str(ports[2]),
               MINIO_CONSOLE_PORT=str(ports[3]))
    base = ['docker', 'compose', '-p', PROJECT, '-f', str(ROOT / 'infra/compose.yaml')]

    def compose(*args, check=True):
        result = subprocess.run([*base, *args], env=env, text=True,
                                capture_output=True, timeout=180)
        if check and result.returncode:
            raise AssertionError(result.stdout + result.stderr)
        return result

    def api(path, payload=None, key=None):
        headers = {'Content-Type': 'application/json'}
        if key:
            headers['Idempotency-Key'] = key
        request = Request(f'http://127.0.0.1:{ports[0]}/api/v1' + path,
                          data=None if payload is None else json.dumps(payload).encode(),
                          headers=headers)
        try:
            response = urlopen(request, timeout=15)
        except HTTPError as error:
            response = error
        with response:
            return response.status, json.load(response)

    def wait_for(check, label, timeout=90):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                if check():
                    print('PASS', label, flush=True)
                    return
            except (URLError, ConnectionError):
                pass
            time.sleep(1)
        raise AssertionError(label + ' timed out')

    def submit(value, delay=0):
        key = uuid4().hex
        payload = {'value': value, 'delaySeconds': delay}
        code, result = api('/internal/test-jobs', payload, key)
        assert code == 202 and result['status'] == 'queued', (code, result)
        return result['jobId'], key, payload

    def completed(job, value):
        code, result = api('/internal/test-jobs/' + job)
        if code != 200 or result['status'] != 'succeeded':
            return False
        assert result['executionCount'] == 1
        assert result['result'] == hashlib.sha256(value.encode()).hexdigest()
        return True

    try:
        compose('up', '-d', '--no-build', 'api', 'outbox')
        wait_for(lambda: api('/health/ready')[0] == 200, 'PG/Redis/MinIO ready')
        compose('run', '--rm', '--no-deps', 'migrate')
        print('PASS repeat migration', flush=True)
        job, key, payload = submit('durable')
        code, duplicate = api('/internal/test-jobs', payload, key)
        assert code == 202 and duplicate['jobId'] == job
        assert api('/internal/test-jobs', {'value': 'changed'}, key)[0] == 409
        assert api('/internal/test-jobs', {'value': ''}, uuid4().hex)[0] == 422
        assert api('/internal/test-jobs', {'value': 'missing-key'})[0] == 422
        compose('restart', 'api', 'outbox')
        wait_for(lambda: api('/internal/test-jobs/' + job)[0] == 200,
                 'accepted job survives API/outbox restart without Worker')
        assert api('/internal/test-jobs/' + job)[1]['status'] == 'queued'
        compose('up', '-d', '--no-build', 'worker')
        wait_for(lambda: completed(job, 'durable'), 'real Celery execution')
        code = ("from app.worker.celery_app import celery_app; "
                f"[celery_app.send_task('hengxin.test_job',args=['{job}']) for _ in range(3)]")
        compose('exec', '-T', 'api', 'python', '-c', code)
        time.sleep(4)
        assert completed(job, 'durable')
        print('PASS duplicate messages preserve single completion', flush=True)

        compose('stop', 'redis')
        assert api('/health/ready')[0] == 503
        job, _, _ = submit('redis-recovery')
        assert api('/internal/test-jobs/' + job)[1]['status'] == 'queued'
        compose('start', 'redis')
        wait_for(lambda: completed(job, 'redis-recovery'), 'Redis outage durable recovery')

        job, _, _ = submit('worker-recovery', 12)
        # Observe the Worker actually receiving the delayed job before killing it.
        wait_for(lambda: job in compose('logs', '--tail', '100', 'worker').stdout,
                 'Worker received delayed job')
        compose('kill', '-s', 'SIGKILL', 'worker')
        compose('start', 'worker')
        wait_for(lambda: completed(job, 'worker-recovery'), 'Worker crash rollback and recovery')

        compose('exec', '-T', 'postgres', 'createdb', '-U', 'hengxin', 'hengxin_test')
        test_url = 'postgresql+psycopg://hengxin:' + env['POSTGRES_PASSWORD'] + '@postgres:5432/hengxin_test'
        result = compose('run', '--rm', '--no-deps', '-e', 'TEST_DATABASE_URL=' + test_url,
                         '-v', str(ROOT / 'frontend/src/types') + ':/contracts-types:ro',
                         'api', 'pytest', '-q')
        print(result.stdout, flush=True)
        containers = compose('ps', '-q').stdout.split()
        inspected = json.loads(subprocess.check_output(['docker', 'inspect', *containers]))
        volumes = {mount['Name'] for item in inspected for mount in item['Mounts']
                   if mount['Type'] == 'volume'}
        assert len(volumes) == 3 and all(v.startswith(PROJECT + '_') for v in volumes)
        print('PASS only three isolated test volumes mounted', flush=True)
        print('PHASE5 INTEGRATION PASS', flush=True)
    finally:
        # The generated project prefix is the boundary for destructive cleanup.
        assert PROJECT.startswith('hx-phase5-test-') and len(PROJECT) == 25
        compose('down', '--volumes', '--remove-orphans', check=False)


if __name__ == '__main__':
    main()
