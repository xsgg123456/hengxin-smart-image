"""Installed-source, configuration, queue, Skills and public asset checks."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess

spec = importlib.util.spec_from_file_location('member_runtime', Path(__file__).with_name('member-release-runtime.py'))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
HEALTH = {'domestic': (18008, '/api/v1/health/ready'),
          'overseas': (18018, '/api/overseas/v1/health/ready'),
          'identity': (18012, '/api/identity/v1/config')}
AUTH = ('/api/v1/auth/me', '/api/overseas/v1/auth/me', '/api/identity/v1/me',
        '/api/v1/management/users/applications', '/api/overseas/v1/members/applications')


def api_sources(manifest, identity, data):
    expected = {n.removeprefix('backend/'): h for n, h in manifest['files'].items() if n.startswith('backend/')}
    assert expected
    probe = ('import hashlib,json,sys; from pathlib import Path; '
             'm=json.loads(sys.argv[1]); assert all(hashlib.sha256((Path("/app")/n).read_bytes()).hexdigest()==h for n,h in m.items())')
    for group, config in m.GROUPS.items():
        for service in config['services']:
            name = m.container(group, service)
            actual = m.live(name)
            assert actual['State']['Running'] and actual['Image'] == identity
            assert actual['Mounts'] == data[group]['mounts'][name], 'Runtime mount drift: ' + name
            m.run('docker', 'exec', name, 'python', '-c', probe, json.dumps(expected))


def resources_unchanged(data):
    for group, config in m.GROUPS.items():
        replaced = {m.container(group, s) for s in config['services']}
        for name, identity in data[group]['ids'].items():
            if name not in replaced:
                actual = m.live(name)
                assert actual['Id'] == identity and actual['State']['Running'], 'Unrelated resource recreated/stopped'


def native_sources(manifest, targets):
    for unit in m.UNITS:
        target = Path(targets['domestic' if unit == m.UNITS[0] else 'overseas'])
        m.run('systemctl', 'is-active', unit)
        actual = m.run('systemctl', 'show', unit, '-p', 'WorkingDirectory', '--value', capture=True)
        assert Path(actual) == target
        pid = int(m.run('systemctl', 'show', unit, '-p', 'MainPID', '--value', capture=True))
        assert pid > 0 and Path(os.readlink(f'/proc/{pid}/cwd')) == target
        m.r.hashes(target.parent, {'files': {n: h for n, h in manifest['files'].items() if n.startswith('backend/')}})


def get(url):
    return subprocess.run(['curl', '--retry', '5', '--retry-delay', '2', '--retry-connrefused',
        '--connect-timeout', '10', '--max-time', '30', '-fsS', '-H', 'Accept-Encoding: identity', url],
        stdout=subprocess.PIPE, check=True).stdout


def status(url):
    return m.run('curl', '--connect-timeout', '10', '--max-time', '30', '-sS', '-o', '/dev/null',
                 '-w', '%{http_code}', url, capture=True)


def anonymous(base):
    for path in AUTH:
        assert status(base + path) in ('401', '403'), 'Anonymous authorization failed: ' + path


def installed(work, source, manifest, identity, data, targets):
    assert m.r.sql('SELECT version_num FROM alembic_version') == '0028'
    assert m.u.sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0014'
    api_sources(manifest, identity, data)
    native_sources(manifest, targets)
    resources_unchanged(data)
    helper = source / 'scripts/release/image-inputs-worker.py'
    m.r.worker(helper, 'native-verify')
    m.r.worker(helper, 'api-verify')
    m.u.wait_worker_ready()
    for port, path in HEALTH.values():
        get(f'http://127.0.0.1:{port}' + path)
    m.skills.verify(m.u, work, Path(targets['overseas']))
    m.private(work / 'INSTALLED_VERIFIED', 'All 7 containers and 3 native runtimes match tested backend source')


def frontend(source, manifest, public=True):
    m.r.hashes(m.APP, {'files': {n: h for n, h in manifest['files'].items() if n.startswith('frontend/')}})
    base = m.r.ORIGIN if public else 'http://127.0.0.1:18080'
    raw = get(base + '/')
    assert raw == (source / 'frontend/dist/index.html').read_bytes(), 'Public frontend index mismatch'
    refs = re.findall(r'(?:src|href)=["\']/?(assets/[^"\'?#]+)', raw.decode())
    assert any(name.endswith('.js') for name in refs)
    for name in refs:
        expected = manifest['files']['frontend/dist/' + name]
        assert hashlib.sha256(get(base + '/' + name)).hexdigest() == expected, 'Public frontend asset mismatch'


def closed():
    for path in ('/api/v1/auth/me', '/api/overseas/v1/auth/me', '/api/identity/v1/me',
                 '/api/v1/api-image-edits/tasks/0/items/0/conversation/events/'):
        assert status(m.r.ORIGIN + path) == '503', 'Public intake is not closed: ' + path


def proxy():
    for _, path in HEALTH.values():
        get('http://127.0.0.1:18080' + path)
    anonymous('http://127.0.0.1:18080')


def public():
    for _, path in HEALTH.values():
        get(m.r.ORIGIN + path)
    anonymous(m.r.ORIGIN)
