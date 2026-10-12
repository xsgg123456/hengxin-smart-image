"""Create two disposable stacks, prove isolation, then remove only owned resources."""
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import tempfile
import time
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[2]
INFRA = ROOT / 'infra'
PREFIX = 'hx-overseas-p16-' + secrets.token_hex(5)
IMAGE = os.environ.get('OVERSEAS_VERIFY_IMAGE', 'hengxin-smart-image-backend:overseas-local')
SECRETS = []


def run(args, *, data=None, check=True):
    environment = {key: value for key, value in os.environ.items()
                   if not key.startswith('OVERSEAS_') and key != 'HX_BUSINESS_CONTEXT'}
    result = subprocess.run(args, input=data, text=True, capture_output=True, env=environment)
    if check and result.returncode:
        diagnostic = result.stderr
        for secret in SECRETS:
            diagnostic = diagnostic.replace(secret, '[REDACTED]')
        raise RuntimeError('Verification command failed: ' + ' '.join(args[:3]) + '\n' + diagnostic)
    return result


def free_port():
    with socket.socket() as server:
        server.bind(('127.0.0.1', 0))
        return server.getsockname()[1]


def compose(stack, *args, **kwargs):
    return run(stack['command'] + list(args), **kwargs)


def make_stack(folder, kind):
    name = PREFIX + '-' + kind
    values = {key: secrets.token_hex(24) for key in (
        'POSTGRES_PASSWORD', 'OWNER_PASSWORD', 'APP_PASSWORD', 'REDIS_PASSWORD',
        'MINIO_ROOT_PASSWORD', 'MINIO_SECRET_KEY')}
    values.update(POSTGRES_DB=kind + '_test', MINIO_ROOT_USER='root' + secrets.token_hex(8),
                  MINIO_ACCESS_KEY='app' + secrets.token_hex(8), MINIO_BUCKET=kind + '-test',
                  APP_IMAGE=IMAGE, API_PORT=str(free_port()))
    SECRETS.extend(value for key, value in values.items() if 'PASSWORD' in key or 'KEY' in key or 'USER' in key)
    envfile = folder / (kind + '.env')
    envfile.write_text(''.join(f'OVERSEAS_{k}={v}\n' for k, v in values.items()))
    return {'name': name, 'values': values, 'command': ['docker', 'compose',
            '--project-name', name, '--env-file', str(envfile),
            '-f', str(INFRA / 'compose.overseas.yaml')]}


def address(stack, service):
    container = compose(stack, 'ps', '-q', service).stdout.strip()
    info = json.loads(run(['docker', 'inspect', container]).stdout)[0]
    return next(iter(info['NetworkSettings']['Networks'].values()))['IPAddress']


def facts(stack):
    values = stack['values']
    return dict(postgres=address(stack, 'overseas-postgres'),
                minio=address(stack, 'overseas-minio'), redis=address(stack, 'overseas-redis'),
                database=values['POSTGRES_DB'], app_password=values['APP_PASSWORD'],
                owner_password=values['OWNER_PASSWORD'], access_key=values['MINIO_ACCESS_KEY'],
                secret_key=values['MINIO_SECRET_KEY'], bucket=values['MINIO_BUCKET'],
                root_user=values['MINIO_ROOT_USER'], root_password=values['MINIO_ROOT_PASSWORD'],
                redis_password=values['REDIS_PASSWORD'])


def check_application_boundary(stack):
    identifier = compose(stack, 'ps', '-q', 'api').stdout.strip()
    info = json.loads(run(['docker', 'inspect', identifier]).stdout)[0]
    environment = '\n'.join(info['Config']['Env'])
    for key in ('POSTGRES_PASSWORD', 'OWNER_PASSWORD', 'MINIO_ROOT_PASSWORD'):
        assert stack['values'][key] not in environment
    assert info['Config']['User'] in ('app', '10001', '10001:10001')
    assert set(info['NetworkSettings']['Networks']) == {stack['name'] + '_overseas'}
    assert all(mount['Type'] == 'volume' and mount['Name'].startswith(stack['name'] + '_')
               for mount in info['Mounts'])


def health(stack, expected, path='ready'):
    url = f'http://127.0.0.1:{stack["values"]["API_PORT"]}/api/overseas/v1/health/{path}'
    for _ in range(30):
        try:
            with urllib.request.urlopen(url, timeout=12) as response:
                status, body = response.status, json.load(response)
        except urllib.error.HTTPError as error:
            status, body = error.code, json.load(error)
        except (urllib.error.URLError, TimeoutError):
            time.sleep(1)
            continue
        if status == expected:
            return body
        time.sleep(1)
    raise AssertionError(f'Health {path}: expected {expected}')


def main():
    stacks, probe = [], PREFIX + '-probe'
    with tempfile.TemporaryDirectory(prefix=PREFIX) as temporary:
        try:
            for kind in ('overseas', 'domestic'):
                stack = make_stack(Path(temporary), kind)
                stacks.append(stack)
                compose(stack, 'up', '-d', '--no-build', '--wait', '--wait-timeout', '120')
                check_application_boundary(stack)
                assert health(stack, 200)['status'] == 'ready'
                compose(stack, 'exec', '-T', '--user', '10001:10001', 'api', 'python', '-c',
                        'from pathlib import Path; '
                        'roots=[Path("/var/lib/hengxin-overseas")/n for n in ("execution","skills","local-skills")]; '
                        '[(p.joinpath(".probe").write_text("ok"), p.joinpath(".probe").unlink()) for p in roots]')
                # Repeat both bootstrap and migration using the same credentials/volumes.
                for service in ('pg-bootstrap', 'minio-bootstrap', 'migrate'):
                    compose(stack, 'run', '--rm', '--no-deps', service)
                print(f'PASS: {kind} non-root API, private mounts/network, no admin secrets, writable roots; '
                      'bootstrap/migration idempotency and readiness', flush=True)
            run(['docker', 'run', '-d', '--name', probe, '--network', stacks[0]['name'] + '_overseas',
                 '-v', f'{INFRA / "overseas"}:/checks:ro', '--entrypoint', 'sleep', IMAGE, 'infinity'])
            run(['docker', 'network', 'connect', stacks[1]['name'] + '_overseas', probe])
            result = run(['docker', 'exec', '-i', probe, 'python', '/checks/probe_resources.py'],
                         data=json.dumps([facts(stack) for stack in stacks]))
            print(result.stdout.strip(), flush=True)
            overseas = stacks[0]
            for service, check in (('overseas-redis', 'redis'), ('overseas-minio', 'minio'),
                                   ('overseas-postgres', 'postgresql')):
                compose(overseas, 'stop', service)
                try:
                    assert health(overseas, 503)['checks'][check] == 'down'
                    assert health(overseas, 200, 'live')['status'] == 'ok'
                finally:
                    compose(overseas, 'start', service)
                health(overseas, 200)
                print(f'PASS: {check} failure => ready 503, live 200; recovery => ready 200', flush=True)
            print('PASS: Phase 16 disposable real-resource verification', flush=True)
        finally:
            run(['docker', 'rm', '-f', probe], check=False)
            for stack in reversed(stacks):
                compose(stack, 'down', '-v', '--remove-orphans')
            print('Cleaned disposable projects: ' + PREFIX, flush=True)


if __name__ == '__main__':
    main()
