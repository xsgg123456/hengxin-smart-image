"""Real Phase 7 API/Worker checks in disposable Linux Compose volumes."""
import base64
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
PROJECT = 'hx-phase7-test-' + uuid4().hex[:10]
PIXEL = base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAIAAAACCAIAAAD91JpzAAAAE0lEQVR4nGL5//8/AwMDEwMYAAAAAP//aYxtrAAAAAZJREFUAwAkMAMEkRkhTQAAAABJRU5ErkJggg==')


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


def main():
    ports = [free_port() for _ in range(4)]
    docker = shutil.which('docker') or 'C:/Program Files/Docker/Docker/resources/bin/docker.exe'
    env = dict(os.environ, POSTGRES_PASSWORD=secrets.token_hex(24),
               MINIO_ACCESS_KEY='p7-' + secrets.token_hex(8), MINIO_SECRET_KEY=secrets.token_hex(24),
               APP_ENV='test', ENABLE_TEST_JOBS='true', ENABLE_DEV_IDENTITY='true', ENABLE_FIXTURE_EXECUTOR='false',
               DEV_USER_ID=str(uuid4()), DEV_USER_NAME='Phase7 isolated admin', DEV_USER_ROLE='super_admin',
               MINIO_BUCKET='phase7-test', API_PORT=str(ports[0]), POSTGRES_PORT=str(ports[1]),
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

    def package(version, missing=False):
        data = io.BytesIO()
        with zipfile.ZipFile(data, 'w') as archive:
            archive.writestr('sample/SKILL.md', '---\nname: phase7-verification\ndescription: isolated integration fixture\n---\nControlled test package.\n')
            archive.writestr('sample/hengxin-skill.json', json.dumps({'mode': 'wallpaper', 'version': version,
                'requires': {'executables': ['hx_missing_dependency_72981'] if missing else ['python'],
                             'pythonModules': ['json']}}))
        return data.getvalue()

    def skill(version, missing=False):
        code, result = upload('/management/skills', package(version, missing), 'test.zip',
                              'application/zip', {'mode': 'wallpaper', 'version': version})
        assert code == 201 and result['status'] == 'uploaded', (code, result)
        id = str(UUID(result['id']))
        assert api(f'/management/skills/{id}/install', {})[1]['status'] == 'installing'
        wait(lambda: next(s for s in api('/management/skills')[1] if s['id'] == id)['status'] ==
             ('failed' if missing else 'available'), 'real Worker install ' + version)
        return id

    def defaults(id):
        code, result = api('/management/skills/defaults', {'wallpaper': id, 'product': None, 'text': None}, 'PUT')
        assert code == 200 and result['wallpaper'] == id, (code, result)

    def template(images, id=None, **changes):
        body = dict(name='phase7-template', mode='wallpaper', images=images, skillVersionId=None,
                    active=True, notes='integration')
        body.update(changes)
        code, result = api('/templates' + ('/' + id if id else ''), body, 'PUT' if id else 'POST')
        assert code == 200, (code, result)
        return result

    try:
        compose('up', '-d', '--no-build', 'api', 'worker', 'outbox')
        wait(lambda: api('/auth/me')[0] == 200, 'fresh Linux PG/Redis/MinIO/API/Worker')
        compose('run', '--rm', '--no-deps', 'migrate')
        print('PASS fresh and repeated migration', flush=True)
        compose('exec', '-T', 'postgres', 'createdb', '-U', 'hengxin', 'hengxin_test')
        test_url = 'postgresql+psycopg://hengxin:' + env['POSTGRES_PASSWORD'] + '@postgres:5432/hengxin_test'
        tests = compose('run', '--rm', '--no-deps', '-e', 'TEST_DATABASE_URL=' + test_url,
                        '-v', str(ROOT / 'frontend/src/types') + ':/contracts-types:ro', 'api', 'pytest', '-q')
        print(tests.stdout, flush=True)
        compose('exec', '-T', 'api', 'python', '-m', 'compileall', '-q', 'app', 'migrations')
        images = []
        for name in ('first.png', 'second.png'):
            code, image = upload('/files', PIXEL, name, 'image/png')
            assert code == 200, (code, image)
            images.append(image)
        draft = template(images)
        assert not draft['active'] and draft['skillVersionId'] is None
        old = skill('1.0.0')
        defaults(old)
        first = template(images)
        assert first['active'] and first['skillVersionId'] == old
        failed = skill('1.0.1', missing=True)
        states = {s['id']: s for s in api('/management/skills')[1]}
        assert states[old]['status'] == 'available' and 'hx_missing_dependency' in states[failed]['error']
        compose('stop', 'redis')
        code, queued = upload('/management/skills', package('1.1.0'), 'recovery.zip', 'application/zip',
                              {'mode': 'wallpaper', 'version': '1.1.0'})
        assert code == 201
        recovery = queued['id']
        assert api('/management/skills/' + recovery + '/install', {})[1]['status'] == 'installing'
        compose('start', 'redis')
        wait(lambda: next(s for s in api('/management/skills')[1] if s['id'] == recovery)['status'] == 'available',
             'real Redis outage install recovery')
        newer = skill('2.0.0')
        dispatches = sql('SELECT sum(dispatch_count) FROM job_outbox')
        defaults(newer)
        assert api('/templates/' + first['id'])[1]['skillVersionId'] == old
        second = template(list(reversed(images)), first['id'], expectedVersion=1)
        assert second['version'] == 2 and second['skillVersionId'] == newer
        history = api('/templates/' + first['id'] + '/versions')[1]
        assert history[1]['skillVersionId'] == old and history[1]['images'] == first['images']
        assert history[0]['images'] == list(reversed(first['images']))
        explicit = template(images, skillVersionId=old)
        assert explicit['skillVersionId'] == old and explicit['skillBinding'] == 'specific'
        assert api('/templates/' + first['id'], dict(name='stale', mode='wallpaper', images=images,
                   skillVersionId=None, active=True, notes='', expectedVersion=1), 'PUT')[0] == 409
        assert api('/templates', dict(name='mismatch', mode='product', images=images,
                   skillVersionId=old, active=True, notes=''), 'POST')[0] == 422
        assert api('/templates?search=phase7-template&sort=images&pageSize=1')[1]['total'] >= 3
        print('PASS draft, explicit precedence, defaults freeze, image order, conflict and type validation', flush=True)
        paths = {id: sql(f"SELECT installed_path FROM skill_versions WHERE id='{id}'") for id in (old, newer)}
        for path in paths.values():
            compose('exec', '-T', 'worker', 'test', '-r', path + '/SKILL.md')
        compose('restart', 'worker', 'api', 'postgres', 'minio')
        wait(lambda: api('/templates/' + explicit['id'])[0] == 200, 'restart persistence')
        for id, path in paths.items():
            assert sql(f"SELECT installed_path FROM skill_versions WHERE id='{id}'") == path
            compose('exec', '-T', 'worker', 'test', '-r', path + '/SKILL.md')
        assert api('/templates/' + explicit['id'])[1]['skillVersionId'] == old
        assert sql('SELECT sum(dispatch_count) FROM job_outbox') == dispatches
        assert sql('SELECT count(*) FROM job_outbox WHERE completed_at IS NULL') == '0'
        assert api('/management/skills/' + old + '/status', {'status': 'disabled'}, 'PUT')[0] == 200
        disabled = api('/templates/' + explicit['id'])[1]
        assert not disabled['active'] and disabled['skillVersionId'] == old
        assert old not in [s['id'] for s in api('/skills')[1]]
        assert template(images, skillVersionId=old)['active'] is False
        print('PASS installed files and frozen bindings survive restart; disabled explicit never falls back', flush=True)
        admin = env['DEV_USER_ID']
        for role in ('design_manager', 'designer', 'operator'):
            sql(f"UPDATE users SET role='{role}' WHERE id='{admin}'")
            assert api('/management/skills')[0] == 403
            assert upload('/management/skills', package('9.0.0'), 'test.zip', 'application/zip',
                          {'mode': 'wallpaper', 'version': '9.0.0'})[0] == 403
            assert api('/management/skills/' + old + '/install', {})[0] == 403
            assert api('/management/skills/' + old + '/status', {'status': 'available'}, 'PUT')[0] == 403
            assert api('/management/skills/defaults', {'wallpaper': old, 'product': None, 'text': None}, 'PUT')[0] == 403
            assert api('/templates')[0] == 200 and template(images)['version'] == 1
        env['DEV_USER_ID'] = str(uuid4())
        env['DEV_USER_ROLE'] = 'designer'
        compose('up', '-d', '--no-build', 'api')
        wait(lambda: api('/auth/me')[0] == 200, 'second isolated user')
        assert api('/auth/me')[1]['id'] == env['DEV_USER_ID']
        shared = template(images, first['id'], expectedVersion=2, active=False)
        assert shared['ownerId'] == admin and not shared['active']
        assert api('/templates/' + first['id'], method='DELETE')[0] == 204
        assert api('/templates/' + first['id'])[0] == 404
        assert sql(f"SELECT operator_id FROM deletion_records WHERE resource_id='{first['id']}'") == env['DEV_USER_ID']
        assert sql(f"SELECT count(*) FROM template_versions WHERE template_id='{first['id']}'") == '3'
        assert sql(f"SELECT count(*) FROM files WHERE status='ready'") == '2'
        runnable = template(images)
        assert api('/tasks', {'mode': 'wallpaper', 'name': 'executor unavailable', 'sources': images,
            'templateId': runnable['id'], 'templateVersion': runnable['version'], 'note': ''}, 'POST',
            headers={'Content-Type': 'application/json', 'Idempotency-Key': str(uuid4())})[0] == 503
        print('PASS non-admin 403, shared edit/disable/delete, actual operator audit and retained history', flush=True)
        containers = compose('ps', '-q').stdout.split()
        inspected = json.loads(subprocess.check_output([docker, 'inspect', *containers], **creation))
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
            (output / 'phase7-skill.zip').write_bytes(package('3.0.0'))
            (output / 'phase7-pixel.png').write_bytes(PIXEL)
            browser_open = True
            browser('open', origin, '--browser', 'chrome')
            browser('snapshot')
            result = browser('run-code', '--filename', 'scripts/phase7/catalog-flow.js', '--raw')
            assert 'PHASE7 BROWSER PASS' in result, result
            print(result, flush=True)
        print('PHASE7 INTEGRATION PASS (four isolated volumes)', flush=True)
    finally:
        if browser_open:
            browser('close', check=False)
            browser('delete-data', check=False)
        if frontend:
            frontend.terminate()
            frontend.wait(timeout=15)
        if vite_log:
            vite_log.close()
        if browser_dir:
            browser_dir.cleanup()
        assert PROJECT.startswith('hx-phase7-test-') and len(PROJECT) == 25
        compose('down', '--volumes', '--remove-orphans', check=False)
        remaining = subprocess.check_output([docker, 'volume', 'ls', '-q', '--filter', 'label=com.docker.compose.project=' + PROJECT], **creation)
        assert not remaining.strip(), 'Isolated volumes were not cleaned'
        print('PASS isolated Compose volumes cleaned', flush=True)


if __name__ == '__main__':
    main()
