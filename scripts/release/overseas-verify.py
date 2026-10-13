"""Installed artifact and anonymous production checks. No fabricated login or AI calls."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import urllib.error
import urllib.request

spec = importlib.util.spec_from_file_location('runtime', Path(__file__).with_name('overseas-runtime.py'))
r = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r)


def request(url, expected):
    try:
        with urllib.request.urlopen(url, timeout=30) as response:
            code, body = response.status, response.read()
    except urllib.error.HTTPError as error:
        code, body = error.code, error.read()
    assert code == expected, (url, code, expected)
    return body


def installed(work, manifest):
    desired = {k[len('backend/'):]:v for k,v in manifest['files'].items() if k.startswith('backend/')}
    code = "import hashlib,json,pathlib; names=json.loads(input()); print(json.dumps({n:hashlib.sha256((pathlib.Path('/app')/n).read_bytes()).hexdigest() for n in names}))"
    containers = [r.PREFIX + n + '-1' for n in r.SERVICES] + ['hengxin-overseas-api-1', 'hengxin-identity-identity-api-1']
    for name in containers:
        actual = r.run('docker', 'exec', '-i', name, 'python', '-c', code, input=json.dumps(list(desired)), capture=True)
        assert json.loads(actual) == desired, name + ' installed file mismatch'
    for root in (Path((work / 'native-target').read_text()), Path('/opt/hengxin-overseas/backend')):
        for name, digest in desired.items():
            assert hashlib.sha256((root / name).read_bytes()).hexdigest() == digest, str(root / name)
    r.ready()
    assert r.sql('SELECT version_num FROM alembic_version') == '0027'
    for unit in ('hengxin-vps-codex-worker', 'hengxin-overseas-worker', 'hengxin-overseas-outbox'):
        assert r.run('systemctl', 'is-active', unit, capture=True) == 'active'
    # Credentials stay scoped to each service; no root credentials in overseas app.
    live = json.loads(r.run('docker', 'inspect', 'hengxin-overseas-api-1', capture=True))[0]
    env = dict(v.split('=',1) for v in live['Config']['Env'])
    assert 'DATABASE_URL' not in env and 'MINIO_ROOT_PASSWORD' not in env
    assert 'overseas_app:' in env['OVERSEAS_DATABASE_URL']
    identity = json.loads(r.run('docker', 'inspect', 'hengxin-identity-identity-api-1', capture=True))[0]
    assert not any(k.split('=',1)[0].endswith(('DATABASE_URL','MINIO_SECRET_KEY')) for k in identity['Config']['Env'])
    for suffix in ('postgres', 'redis', 'minio'):
        resource = json.loads(r.run('docker', 'inspect', 'hengxin-overseas-overseas-' + suffix + '-1', capture=True))[0]
        assert set(resource['NetworkSettings']['Networks']) == {'hengxin-overseas_overseas'}
    for path in ('/api/overseas/v1/tasks', '/api/overseas/v1/management/settings'):
        request('http://127.0.0.1:18018' + path, 401)
    print('INSTALLED_HASHES_HEALTH_AND_ISOLATION_PASS', flush=True)


def public(work, manifest):
    for path, status in (('/',200), ('/api/v1/health/ready',200), ('/api/overseas/v1/health/ready',200),
                         ('/api/identity/v1/config',200), ('/api/identity/v1/me',401),
                         ('/api/overseas/v1/auth/me',401), ('/api/overseas/v1/tasks',401),
                         ('/api/v1/auth/me',401), ('/internal/',404)):
        body = request(r.ORIGIN + path, status)
        if path == '/api/identity/v1/config':
            assert json.loads(body)['configured'] is True
    html = request(r.ORIGIN + '/', 200)
    assert hashlib.sha256(html).hexdigest() == manifest['files']['frontend/dist/index.html']
    for path in re.findall(r'(?:src|href)="(/[^"?#]+\.(?:js|css))"', html.decode()):
        raw = request(r.ORIGIN + path, 200)
        assert hashlib.sha256(raw).hexdigest() == manifest['files']['frontend/dist' + path], path
    for name, digest in manifest['files'].items():
        if name.startswith('frontend/dist/'):
            target = r.APP / name
            assert hashlib.sha256(target.read_bytes()).hexdigest() == digest, name
    print('PUBLIC_HASHES_AUTHENTICATION_BOUNDARIES_PASS', flush=True)


def main():
    release = sys.argv[1]
    assert re.fullmatch(r'overseas-20261013-[0-9a-f]{7}', release)
    work = Path('/opt/hengxin-releases') / release
    manifest = json.loads((work / 'src/release.json').read_text())
    installed(work, manifest)
    if '--installed-only' not in sys.argv:
        public(work, manifest)
        r.private(work / 'verification.json', {'release':release,'installed':'PASS','public':'PASS','realDingTalkLogin':'NOT_TESTED','paidModel':'NOT_RUN'})


if __name__ == '__main__':
    main()
