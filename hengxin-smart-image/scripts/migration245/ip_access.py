"""Prepare/apply the reviewed LAN-only HTTP entry; never contact production."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
import urllib.request

from build_edge import NGINX, protected

ROOT = Path('/opt/hengxin-lan')
WORK = ROOT / 'ip-access-20261111'
ORIGIN = 'http://192.168.1.245:8080'
SERVICES = ['domestic-api', 'overseas-api', 'identity-api', 'domestic-web']
BASE = {'app/core/config.py': '0d3dae78237f385c412c3d8168466b57ee7eed76187dd50501fbacdff9595658',
        'app/core/browser_auth.py': 'ca198955bc70e5075dbd1576007cce7cb8f34b882f7c03ca1f515b33d74f95a8'}


def run(args):
    return subprocess.check_output(args, stderr=subprocess.STDOUT, timeout=180)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write(path, data):
    with path.open('xb') as stream:
        os.chmod(path, 0o600)
        stream.write(data)


def compose(*args):
    return run(['docker', 'compose', '-f', str(ROOT / 'compose.json'), *args])


def check():
    if socket.gethostname() != 'hengxin-ai-245' or os.geteuid() != 0:
        raise RuntimeError('wrong host or user')
    protected(ROOT, directory=True)
    protected(WORK, directory=True)
    protected(ROOT / 'compose.json')
    protected(ROOT / 'edge-nginx.conf')


def http_nginx():
    block = NGINX[NGINX.index('    server {'):NGINX.rindex('\n}')]
    block = '\n'.join(line for line in block.splitlines() if 'ssl_' not in line)
    block = block.replace('192.168.1.245:443 ssl', '192.168.1.245:8080')
    block = block.replace('zhitu.qhhengxin.top', '192.168.1.245')
    block = block.replace('X-Forwarded-Proto https', 'X-Forwarded-Proto http')
    block = block.replace('X-Forwarded-Port 443', 'X-Forwarded-Port 8080')
    block = block.replace('Host $host', 'Host $http_host')
    block = block.replace('server_name 192.168.1.245;', 'server_name 192.168.1.245;\n        access_log off;')
    # Retire the temporary same-domain test entry without serving a mismatched origin.
    redirect = '''    server {
        listen 192.168.1.245:443 ssl;
        server_name zhitu.qhhengxin.top;
        ssl_certificate /etc/nginx/tls/fullchain.pem;
        ssl_certificate_key /etc/nginx/tls/privkey.pem;
        ssl_protocols TLSv1.2 TLSv1.3;
        access_log off;
        allow 192.168.1.0/24;
        allow 192.168.2.0/23;
        deny all;
        if ($host != zhitu.qhhengxin.top) { return 444; }
        location / { return 302 http://192.168.1.245:8080$request_uri; }
    }
'''
    return NGINX[:NGINX.index('    server {')] + redirect + block + '\n}\n'


def prepare():
    check()
    original = (ROOT / 'compose.json').read_bytes()
    old_edge = (ROOT / 'edge-nginx.conf').read_bytes()
    if old_edge.decode() != NGINX:
        raise RuntimeError('edge configuration drift')
    candidate = json.loads(original)
    manifest = json.loads((WORK / 'manifest.json').read_text())
    expected_backend = set(BASE)
    if set(manifest['backend']) != expected_backend:
        raise RuntimeError('unexpected backend payload')
    for section in ('backend', 'frontend'):
        actual_files = {str(p.relative_to(WORK / section)).replace('\\', '/')
                        for p in (WORK / section).rglob('*') if p.is_file()}
        if actual_files != set(manifest[section]):
            raise RuntimeError('payload file inventory mismatch')
        for name, sha in manifest[section].items():
            path = WORK / section / name
            if path.is_symlink() or path.resolve() != path or not path.is_relative_to(WORK / section):
                raise RuntimeError('unsafe payload path')
            if digest(path.read_bytes()) != sha:
                raise RuntimeError('payload checksum mismatch')
            os.chmod(path, 0o644)
    if 'index.html' not in manifest['frontend']:
        raise RuntimeError('missing frontend entry')
    for name in ('domestic-api', 'overseas-api'):
        svc = candidate['services'][name]
        for path, sha in BASE.items():
            actual = run(['docker', 'exec', svc['container_name'], 'cat', '/app/' + path])
            if digest(actual) != sha:
                raise RuntimeError('API source drift')
            svc['volumes'].append({'type': 'bind', 'source': str(WORK / 'backend' / path),
                                   'target': '/app/' + path, 'read_only': True,
                                   'bind': {'create_host_path': False}})
        prefix = 'OVERSEAS_' if name.startswith('overseas') else ''
        svc['environment'][prefix + 'ALLOW_INTRANET_HTTP'] = 'true'
        svc['environment'][prefix + 'IDENTITY_PUBLIC_ORIGIN'] = ORIGIN
    candidate['services']['identity-api']['environment']['IDENTITY_PUBLIC_ORIGIN'] = ORIGIN
    web = candidate['services']['domestic-web']
    targets = [v for v in web['volumes'] if v['target'] == '/usr/share/nginx/html']
    if len(targets) != 1:
        raise RuntimeError('unexpected web mount')
    targets[0]['source'] = str(WORK / 'frontend')
    write(WORK / 'compose.before.json', original)
    write(WORK / 'edge.before.conf', old_edge)
    write(WORK / 'compose.candidate.json', (json.dumps(candidate, indent=2) + '\n').encode())
    write(WORK / 'edge.candidate.conf', http_nginx().encode())
    run(['docker', 'compose', '-f', str(WORK / 'compose.candidate.json'), 'config', '--quiet'])
    image = web['image']
    run(['docker', 'run', '--rm', '--network', 'host', '--entrypoint', 'nginx',
         '-v', str(WORK / 'edge.candidate.conf') + ':/etc/nginx/nginx.conf:ro',
         '-v', '/opt/1panel/www/sites/zhitu/ssl:/etc/nginx/tls:ro', image, '-t'])
    write(WORK / 'prepared.json', json.dumps({
        'compose': digest(original), 'edge': digest(old_edge),
        'candidate': digest((WORK / 'compose.candidate.json').read_bytes()),
        'edge_candidate': digest((WORK / 'edge.candidate.conf').read_bytes()),
        'manifest': digest((WORK / 'manifest.json').read_bytes()),
    }).encode())
    print('PREPARED: payload hashes, source baseline, compose and nginx validated')


def reload_nginx(container):
    # Compose reports "started" before the nginx entrypoint has written its PID.
    deadline = time.monotonic() + 30
    while True:
        try:
            run(['docker', 'exec', container, 'nginx', '-t'])
            run(['docker', 'exec', container, 'nginx', '-s', 'reload'])
            return
        except subprocess.CalledProcessError:
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)


def restore():
    shutil.copyfile(WORK / 'compose.before.json', ROOT / 'compose.json')
    shutil.copyfile(WORK / 'edge.before.conf', ROOT / 'edge-nginx.conf')
    try:
        compose('up', '-d', '--no-deps', *SERVICES)
        reload_nginx('hengxin-lan-domestic-web')
    finally:
        reload_nginx('hengxin-lan-https')


def healthy():
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    urls = ['http://127.0.0.1:18008/api/v1/health/ready',
            'http://127.0.0.1:18018/api/overseas/v1/health/ready',
            ORIGIN + '/api/identity/v1/config', ORIGIN + '/']
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        try:
            for url in urls:
                with client.open(url, timeout=3) as response:
                    if response.status != 200:
                        raise RuntimeError('endpoint not ready')
            return
        except Exception:
            time.sleep(2)
    raise RuntimeError('HTTP readiness deadline exceeded')


def apply():
    check()
    before = json.loads((WORK / 'prepared.json').read_text())
    if digest((ROOT / 'compose.json').read_bytes()) != before['compose']:
        raise RuntimeError('compose changed since prepare')
    if digest((ROOT / 'edge-nginx.conf').read_bytes()) != before['edge']:
        raise RuntimeError('edge changed since prepare')
    for name, key in [('compose.candidate.json', 'candidate'),
                      ('edge.candidate.conf', 'edge_candidate'), ('manifest.json', 'manifest')]:
        if digest((WORK / name).read_bytes()) != before[key]:
            raise RuntimeError('candidate changed since prepare')
    manifest = json.loads((WORK / 'manifest.json').read_text())
    for section in ('backend', 'frontend'):
        for name, sha in manifest[section].items():
            if digest((WORK / section / name).read_bytes()) != sha:
                raise RuntimeError('payload changed since prepare')
    if (WORK / 'applied.json').exists():
        raise RuntimeError('already applied')
    with socket.socket() as probe:
        probe.bind(('192.168.1.245', 8080))
    try:
        shutil.copyfile(WORK / 'compose.candidate.json', ROOT / 'compose.json')
        compose('up', '-d', '--no-deps', *SERVICES)
        # Embedded nginx resolves service names at startup; refresh changed API addresses.
        reload_nginx('hengxin-lan-domestic-web')
        shutil.copyfile(WORK / 'edge.candidate.conf', ROOT / 'edge-nginx.conf')
        reload_nginx('hengxin-lan-https')
        healthy()
        write(WORK / 'applied.json', b'{"applied": true}\n')
    except Exception:
        restore()
        raise
    print('APPLIED: verify HTTP, cookies, origin controls, login and business independently')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['prepare', 'apply', 'rollback'])
    action = parser.parse_args().action
    try:
        check()
        {'prepare': prepare, 'apply': apply, 'rollback': restore}[action]()
    except Exception as error:
        # Docker output/configuration may contain secrets. Keep failure output private.
        raise SystemExit('IP access operation failed: ' + type(error).__name__)
