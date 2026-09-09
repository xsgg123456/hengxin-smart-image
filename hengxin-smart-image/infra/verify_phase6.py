"""Real file/identity checks in disposable Compose volumes and browser profile."""
import base64
import hashlib
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
PROJECT = 'hx-phase6-test-' + uuid4().hex[:10]
PIXEL = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGL5//8/AwMDEwMYAAAAAP//aYxtrAAAAAZJREFUAwAkMAMEkRkhTQAAAABJRU5ErkJggg==')


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    ports = [free_port() for _ in range(5)]
    env = dict(os.environ, POSTGRES_PASSWORD=secrets.token_hex(24),
               MINIO_ACCESS_KEY='phase6-test', MINIO_SECRET_KEY=secrets.token_hex(24),
               APP_ENV='test', ENABLE_TEST_JOBS='false', ENABLE_DEV_IDENTITY='true',
               DEV_USER_ID='00000000-0000-4000-8000-000000000001',
               DEV_USER_NAME='本地联调用户', DEV_USER_ROLE='operator',
               MINIO_BUCKET='phase6-test', API_PORT=str(ports[0]),
               POSTGRES_PORT=str(ports[1]), MINIO_PORT=str(ports[2]),
               MINIO_CONSOLE_PORT=str(ports[3]),
               VITE_API_PROXY_URL=f'http://127.0.0.1:{ports[0]}')
    base = ['docker', 'compose', '-p', PROJECT, '-f', str(ROOT / 'infra/compose.yaml')]
    frontend = None
    browser_open = False
    npx = shutil.which('npx.cmd' if os.name == 'nt' else 'npx')
    cli = [npx, '--yes', '--package', '@playwright/cli', 'playwright-cli', '-s=' + PROJECT]
    creation = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}

    def compose(*args, check=True):
        result = subprocess.run([*base, *args], env=env, text=True, encoding='utf-8',
                                errors='replace', capture_output=True, timeout=180, **creation)
        if check and result.returncode:
            # Do not echo commands/env: they can contain disposable credentials.
            raise AssertionError(result.stdout + result.stderr)
        return result

    def request(path, body=None, headers=None, origin=None):
        req = Request((origin or f'http://127.0.0.1:{ports[0]}') + path,
                      data=body, headers=headers or {})
        try:
            response = urlopen(req, timeout=65)
        except HTTPError as error:
            response = error
        with response:
            return response.status, response.read(), response.headers

    def api(path):
        status, data, _ = request('/api/v1' + path)
        return status, json.loads(data)

    def upload(data=PIXEL, name='pixel.png', mime='image/png'):
        boundary = 'hx-' + uuid4().hex
        body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
                f'filename="{name}"\r\nContent-Type: {mime}\r\n\r\n').encode()
        body += data + f'\r\n--{boundary}--\r\n'.encode()
        return request('/api/v1/files', body, {'Content-Type': 'multipart/form-data; boundary=' + boundary})

    def wait_for(check, label):
        deadline = time.monotonic() + 90
        while time.monotonic() < deadline:
            try:
                if check():
                    print('PASS', label, flush=True)
                    return
            except (URLError, ConnectionError, TimeoutError):
                pass
            time.sleep(1)
        raise AssertionError(label + ' timed out')

    def sql(statement):
        return compose('exec', '-T', 'postgres', 'psql', '-U', 'hengxin', '-d',
                       'hengxin', '-tA', '-v', 'ON_ERROR_STOP=1', '-c', statement).stdout.strip()

    def browser(*args):
        result = subprocess.run([*cli, *args], cwd=REPO, text=True, encoding='utf-8',
                                errors='replace', capture_output=True, timeout=180, **creation)
        if result.returncode or '### Error' in result.stdout:
            raise AssertionError(result.stdout + result.stderr)
        return result.stdout

    with tempfile.TemporaryDirectory(prefix=PROJECT) as temporary:
        try:
            compose('up', '-d', '--no-build', 'api')
            wait_for(lambda: api('/auth/me')[0] == 200, 'explicit development identity')
            compose('run', '--rm', '--no-deps', 'migrate')
            assert api('/auth/me')[1]['role'] == 'operator'
            forged = request('/api/v1/auth/me?role=super_admin&userId=attacker', headers={
                'X-User-Id': str(uuid4()), 'X-Role': 'super_admin', 'Authorization': 'Bearer fake'})
            assert json.loads(forged[1])['role'] == 'operator'
            code, data, _ = upload()
            assert code == 200, (code, data)
            picture = json.loads(data)
            file_id = str(__import__('uuid').UUID(picture['fileId']))
            content = picture['url']
            assert request(content)[1] == PIXEL
            download = request(content + '?download=true')
            assert download[1] == PIXEL and 'attachment' in download[2]['Content-Disposition']
            row = json.loads(sql("SELECT row_to_json(f) FROM files f WHERE id='" + file_id + "'"))
            assert row['owner_id'] == env['DEV_USER_ID'] and row['status'] == 'ready'
            assert row['size_bytes'] == len(PIXEL) and row['checksum'] == hashlib.sha256(PIXEL).hexdigest()
            assert row['width'] == 2 and row['height'] == 2 and row['content_type'] == 'image/png'
            private = request('/' + row['bucket'] + '/' + row['object_key'],
                              origin=f'http://127.0.0.1:{ports[2]}')
            assert private[0] == 403
            print('PASS private object, original bytes, metadata and server ownership', flush=True)
            before = sql('SELECT count(*) FROM files')
            for invalid in [b'', b'not an image', PIXEL[:35], b'x' * (10485760 + 1)]:
                assert upload(invalid)[0] in (413, 415, 422)
            assert sql('SELECT count(*) FROM files') == before
            assert api('/files/' + str(uuid4()))[0] == 404
            print('PASS empty/corrupt/truncated/oversized input leaves no file rows', flush=True)
            compose('restart', 'api', 'postgres', 'minio')
            wait_for(lambda: request(content)[0] == 200, 'file persists across API/PG/MinIO restart')
            assert request(content)[1] == PIXEL
            for status in ['disabled', 'pending']:
                sql("UPDATE users SET status='" + status + "' WHERE id='" + env['DEV_USER_ID'] + "'")
                assert request(content)[0] in (401, 403)
                assert upload()[0] in (401, 403)
            sql("UPDATE users SET status='active' WHERE id='" + env['DEV_USER_ID'] + "'")
            env['DEV_USER_ID'] = '00000000-0000-4000-8000-000000000002'
            env['DEV_USER_ROLE'] = 'designer'
            compose('up', '-d', '--no-build', 'api')
            wait_for(lambda: api('/auth/me')[0] == 200, 'second server-owned identity')
            assert api('/auth/me')[1]['id'] == env['DEV_USER_ID']
            assert request(content)[1] == PIXEL
            env['ENABLE_DEV_IDENTITY'] = 'false'
            compose('up', '-d', '--no-build', 'api')
            wait_for(lambda: api('/auth/me')[0] == 401, 'anonymous denied after disabling development identity')
            assert request(content)[0] == 401 and upload()[0] == 401
            env.update(ENABLE_DEV_IDENTITY='true', DEV_USER_ROLE='operator',
                       DEV_USER_ID='00000000-0000-4000-8000-000000000001')
            compose('up', '-d', '--no-build', 'api')
            wait_for(lambda: api('/auth/me')[0] == 200, 'restore isolated operator')
            compose('stop', 'minio')
            assert upload()[0] == 503
            compose('start', 'minio')
            wait_for(lambda: api('/health/ready')[0] == 200, 'storage recovery')
            assert upload()[0] == 200 and request(content)[1] == PIXEL
            print('PASS cross-user sharing, disabled/pending/anonymous denial, storage failure retry', flush=True)
            compose('exec', '-T', 'postgres', 'createdb', '-U', 'hengxin', 'hengxin_test')
            test_url = 'postgresql+psycopg://hengxin:' + env['POSTGRES_PASSWORD'] + '@postgres:5432/hengxin_test'
            result = compose('run', '--rm', '--no-deps', '-e', 'TEST_DATABASE_URL=' + test_url,
                             '-v', str(ROOT / 'frontend/src/types') + ':/contracts-types:ro',
                             'api', 'pytest', '-q')
            print(result.stdout, flush=True)
            print(compose('exec', '-T', 'api', 'python', '-m', 'compileall', '-q', 'app', 'migrations').stdout)
            with open(Path(temporary) / 'vite.log', 'w', encoding='utf-8') as log:
                frontend = subprocess.Popen([shutil.which('node'), 'node_modules/vite/bin/vite.js',
                    '--mode', 'development', '--port', str(ports[4]), '--strictPort'],
                    cwd=ROOT / 'frontend', env=env, stdout=log, stderr=log, **creation)
                origin = f'http://127.0.0.1:{ports[4]}'
                wait_for(lambda: request('/', origin=origin)[0] == 200, 'isolated frontend')
                (REPO / 'output/playwright').mkdir(parents=True, exist_ok=True)
                (REPO / 'output/playwright/phase6-pixel.png').write_bytes(PIXEL)
                browser('open', origin, '--browser', 'chrome')
                browser_open = True
                browser('snapshot')
                result = browser('run-code', '--filename', 'scripts/phase6/files-flow.js', '--raw')
                assert 'PHASE6 BROWSER PASS' in result, result
                assert (REPO / 'output/playwright/phase6-jpeg-download.jpg').read_bytes() == (ROOT / 'frontend/tests/fixtures/jpeg-with-trailer.jpg').read_bytes()
                print(result, flush=True)
            containers = compose('ps', '-q').stdout.split()
            inspected = json.loads(subprocess.check_output(['docker', 'inspect', *containers]))
            volumes = {m['Name'] for item in inspected for m in item['Mounts'] if m['Type'] == 'volume'}
            assert len(volumes) == 3 and all(v.startswith(PROJECT + '_') for v in volumes)
            print('PHASE6 INTEGRATION PASS (isolated volumes)', flush=True)
        finally:
            if browser_open:
                browser('close')
            if frontend:
                frontend.terminate()
                frontend.wait(timeout=15)
            assert PROJECT.startswith('hx-phase6-test-') and len(PROJECT) == 25
            compose('down', '--volumes', '--remove-orphans', check=False)


if __name__ == '__main__':
    main()
