"""Real Phase 8 API/Worker checks in disposable Linux Compose volumes."""
import base64
import re
import io
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import UUID, uuid4
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PROJECT = 'hx-phase8-test-' + uuid4().hex[:10]
PIXEL = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGL5//8/AwMDEwMYAAAAAP//aYxtrAAAAAZJREFUAwAkMAMEkRkhTQAAAABJRU5ErkJggg==')


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    ports = [free_port() for _ in range(4)]
    docker = shutil.which('docker') or 'C:/Program Files/Docker/Docker/resources/bin/docker.exe'
    env = dict(os.environ, POSTGRES_PASSWORD=secrets.token_hex(24),
               MINIO_ACCESS_KEY='p8-' + secrets.token_hex(8), MINIO_SECRET_KEY=secrets.token_hex(24),
               APP_ENV='test', ENABLE_FIXTURE_EXECUTOR='true', GENERATION_CONCURRENCY='1',
               FIXTURE_DELAY_SECONDS='8', ENABLE_TEST_JOBS='true', ENABLE_DEV_IDENTITY='true',
               DEV_USER_ID=str(uuid4()), DEV_USER_NAME='Phase7 isolated admin', DEV_USER_ROLE='super_admin',
               MINIO_BUCKET='phase8-test', API_PORT=str(ports[0]), POSTGRES_PORT=str(ports[1]),
               MINIO_PORT=str(ports[2]), MINIO_CONSOLE_PORT=str(ports[3]))
    base = [docker, 'compose', '-p', PROJECT, '-f', str(ROOT / 'infra/compose.yaml')]
    creation = {'creationflags': subprocess.CREATE_NO_WINDOW} if os.name == 'nt' else {}
    frontend, browser_open, browser_dir, vite_log = None, False, None, None
    browser_env = dict(os.environ, PATH='D:/Apps/nodejs' + os.pathsep + os.environ.get('PATH', ''))
    npx = shutil.which('npx.cmd' if os.name == 'nt' else 'npx') or 'D:/Apps/nodejs/npx.cmd'

    def browser(*args, check=True):
        result = subprocess.run([npx, '--yes', '--package', '@playwright/cli', 'playwright-cli',
            '-s=' + PROJECT, *args], cwd=ROOT.parent, env=browser_env, text=True, encoding='utf-8',
            errors='replace', capture_output=True, timeout=180, **creation)
        if check and (result.returncode or '### Error' in result.stdout):
            raise AssertionError(result.stdout + result.stderr)
        return result.stdout

    def compose(*args, check=True):
        result = subprocess.run([*base, *args], env=env, text=True, encoding='utf-8',
                                errors='replace', capture_output=True, timeout=180, **creation)
        if check and result.returncode:
            output = result.stdout + result.stderr
            for key in ('POSTGRES_PASSWORD', 'MINIO_ACCESS_KEY', 'MINIO_SECRET_KEY'):
                output = output.replace(env[key], '[redacted]')
            raise AssertionError(output)
        return result

    def api(path, payload=None, method=None, raw=False, headers=None):
        data = payload if raw else None if payload is None else json.dumps(payload).encode()
        req = Request(f'http://127.0.0.1:{ports[0]}/api/v1' + path, data=data,
                      headers=headers or {'Content-Type': 'application/json'}, method=method)
        try:
            response = urlopen(req, timeout=20)
        except HTTPError as error:
            response = error
        with response:
            data = response.read()
            return response.status, json.loads(data) if data else None

    def sql(statement):
        return compose('exec', '-T', 'postgres', 'psql', '-U', 'hengxin', '-d', 'hengxin',
                       '-tA', '-v', 'ON_ERROR_STOP=1', '-c', statement).stdout.strip()

    def wait(check, label):
        deadline = time.monotonic() + 100
        while time.monotonic() < deadline:
            try:
                if check():
                    print('PASS', label, flush=True)
                    return
            except (URLError, ConnectionError, TimeoutError):
                pass
            time.sleep(1)
        raise AssertionError(label + ' timed out')

    def upload(path, data, name, mime, fields=None):
        boundary = 'hx-' + uuid4().hex
        body = b''
        for key, value in (fields or {}).items():
            body += (f'--{boundary}\r\nContent-Disposition: form-data; name="{key}"\r\n\r\n{value}\r\n').encode()
        body += (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="{name}"\r\n'
                 f'Content-Type: {mime}\r\n\r\n').encode() + data + f'\r\n--{boundary}--\r\n'.encode()
        return api(path, body, raw=True, headers={'Content-Type': 'multipart/form-data; boundary=' + boundary})

    def package(version, missing=False, mode='wallpaper'):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('sample/SKILL.md', '---\nname: phase8-verification\ndescription: isolated integration fixture\n---\nControlled test package.\n')
            archive.writestr('sample/hengxin-skill.json', json.dumps({'mode': mode, 'version': version,
                'requires': {'executables': ['hx_missing_dependency_72981'] if missing else ['python'],
                             'pythonModules': ['json']}}))
        return data.getvalue()

    try:
        if '--build' in sys.argv:
            compose('build', 'api')
        compose('up', '-d', '--no-build', '--scale', 'worker=2', 'api', 'worker', 'outbox')
        wait(lambda: api('/auth/me')[0] == 200, 'fresh Linux PG/Redis/MinIO/API/Worker')
        compose('run', '--rm', '--no-deps', 'migrate')
        print('PASS fresh and repeated migration', flush=True)
        test_database = 'phase8_' + uuid4().hex[:10] + '_test'
        compose('exec', '-T', 'postgres', 'createdb', '-U', 'hengxin', test_database)
        test_url = 'postgresql+psycopg://hengxin:' + env['POSTGRES_PASSWORD'] + '@postgres:5432/' + test_database
        tests = compose('run', '--rm', '--no-deps', '-e', 'TEST_DATABASE_URL=' + test_url,
                        '-e', 'ENABLE_FIXTURE_EXECUTOR=false',
                        '-v', str(ROOT / 'frontend/src/types') + ':/contracts-types:ro', 'api', 'pytest', '-q')
        print(tests.stdout, flush=True)
        assert re.search(r'\b[1-9][0-9]* passed\b', tests.stdout) and 'skipped' not in tests.stdout, tests.stdout
        compose('exec', '-T', 'api', 'python', '-m', 'compileall', '-q', 'app', 'migrations')
        sys.path.insert(0, str(ROOT.parent / 'scripts/phase8'))
        from api_checks import verify
        verify_uncertain = verify(api, upload, package, wait, compose, sql, env, PIXEL)
        if '--phase10' in sys.argv:
            sys.path.insert(0, str(ROOT.parent / 'scripts/phase10'))
            from revision_checks import verify_revisions
            verify_revisions(api, wait, compose, sql, env)
        containers = compose('ps', '-q').stdout.split()
        inspected = json.loads(subprocess.check_output([docker, 'inspect', *containers], **creation))
        workers = [item for item in inspected if item['Config']['Labels'].get('com.docker.compose.service') == 'worker']
        assert len(workers) == 2 and len({item['Id'] for item in workers}) == 2
        volumes = {m['Name'] for item in inspected for m in item['Mounts'] if m['Type'] == 'volume'}
        assert len(volumes) == 4 and all(v.startswith(PROJECT + '_') for v in volumes)
        if '--browser' in sys.argv:
            sql(f"UPDATE users SET role='super_admin' WHERE id='{env['DEV_USER_ID']}'")
            browser_dir = tempfile.TemporaryDirectory(prefix=PROJECT)
            vite_log = open(Path(browser_dir.name) / 'vite.log', 'w', encoding='utf-8')
            port = free_port()
            vite_env = dict(browser_env, VITE_API_PROXY_URL=f'http://127.0.0.1:{ports[0]}')
            node = shutil.which('node') or 'D:/Apps/nodejs/node.exe'
            frontend = subprocess.Popen([node, 'node_modules/vite/bin/vite.js', '--mode', 'development',
                '--port', str(port), '--strictPort'], cwd=ROOT / 'frontend', env=vite_env,
                stdout=vite_log, stderr=vite_log, **creation)
            origin = f'http://127.0.0.1:{port}'
            def vite_ready():
                with urlopen(origin, timeout=5) as response:
                    return response.status == 200
            wait(vite_ready, 'isolated Vite browser frontend')
            output = ROOT.parent / 'output/playwright'
            output.mkdir(parents=True, exist_ok=True)
            (output / 'phase8-skill.zip').write_bytes(package('3.0.0'))
            (output / 'phase8-pixel.png').write_bytes(PIXEL)
            browser_open = True
            browser('open', origin, '--browser', 'chrome')
            browser('snapshot')
            result = browser('run-code', '--filename', 'scripts/phase8/task-flow.js', '--raw')
            assert 'PHASE8 BROWSER PASS' in result, result
            print(result, flush=True)
            with zipfile.ZipFile(output / 'phase8-results.zip') as downloaded:
                assert len(downloaded.namelist()) == 1
                assert downloaded.read(downloaded.namelist()[0]) == PIXEL
            print('PASS browser ZIP contains exact readable fixture image', flush=True)
            result = browser('run-code', '--filename', 'scripts/phase8/auth-recovery.js', '--raw')
            assert 'PHASE8 AUTH RECOVERY PASS' in result, result
            print(result, flush=True)
            result = browser('run-code', '--filename', 'scripts/phase8/recovery-screenshots.js', '--raw')
            assert 'PHASE8 RECOVERY VISUAL PASS' in result, result
            print(result, flush=True)
            if '--phase10' in sys.argv:
                result = browser('run-code', '--filename', 'scripts/phase10/revisions.js', '--raw')
                assert 'PHASE10 BROWSER PASS' in result, result
                print(result, flush=True)
        verify_uncertain()
        print('PHASE8 INTEGRATION PASS (four isolated volumes)', flush=True)
    finally:
        try:
            try:
                if browser_open:
                    try:
                        browser('close', check=False)
                    finally:
                        browser('delete-data', check=False)
            finally:
                if frontend:
                    frontend.terminate()
                    try:
                        frontend.wait(timeout=15)
                    except subprocess.TimeoutExpired:
                        frontend.kill()
                        frontend.wait(timeout=10)
                if vite_log:
                    vite_log.close()
                if browser_dir:
                    browser_dir.cleanup()
        finally:
            assert PROJECT.startswith('hx-phase8-test-') and len(PROJECT) == 25
            compose('down', '--volumes', '--remove-orphans')
            remaining = subprocess.check_output([docker, 'volume', 'ls', '-q', '--filter', 'label=com.docker.compose.project=' + PROJECT], **creation)
            assert not remaining.strip(), 'Isolated volumes were not cleaned'
            print('PASS isolated Compose volumes cleaned', flush=True)


if __name__ == '__main__':
    main()
