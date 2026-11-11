"""Read-only checks of the actual LAN source, runtime and schema."""
import hashlib
import json
import os
from pathlib import Path
import urllib.request


RELEASES = Path('/opt/hengxin-unified-releases')


def sha(data):
    return hashlib.sha256(data).hexdigest()


def release_path(value):
    path = Path(value)
    if path.parent != RELEASES or not path.name or path.name.startswith('.'):
        raise RuntimeError('Release must be a direct child of ' + str(RELEASES))
    return path


def manifest(u, root):
    root = release_path(root)
    old = u.RELEASE
    try:
        u.RELEASE = root
        u.validate_release()
    finally:
        u.RELEASE = old
    return json.loads((root / 'release-manifest.json').read_bytes())


def backend_inputs(m):
    return {n: h for n, h in m['files'].items()
            if n in ('backend/pyproject.toml', 'backend/uv.lock',
                     'backend/alembic.ini', 'backend/alembic.overseas.ini')
            or n.startswith('backend/migrations/') or n.startswith('backend/requirements')}


def compatible(before, candidate, mode):
    if backend_inputs(before) != backend_inputs(candidate):
        raise RuntimeError('Dependency/schema inputs changed; separate upgrade plan required')
    if before.get('runtime_inputs') and before['runtime_inputs'] != candidate.get('runtime_inputs'):
        raise RuntimeError('Codex runtime inputs changed; separate upgrade plan required')
    if mode == 'frontend' and {n: h for n, h in before['files'].items() if n.startswith('backend/app/')} != {
            n: h for n, h in candidate['files'].items() if n.startswith('backend/app/')}:
        raise RuntimeError('Frontend-only release contains backend changes')


def database(u, side):
    name = 'hengxin-lan-' + side + '-postgres'
    info = json.loads(u.run(['docker', 'inspect', name]))[0]
    env = dict(v.split('=', 1) for v in info['Config']['Env'] if '=' in v)
    return name, env['POSTGRES_USER'], env['POSTGRES_DB']


def schemas(u):
    result = {}
    for side in ('domestic', 'overseas'):
        name, user, db = database(u, side)
        table = 'alembic_version' if side == 'domestic' else 'overseas_alembic_version'
        result[side] = u.run(['docker', 'exec', name, 'psql', '-X', '-A', '-t',
                             '-U', user, '-d', db, '-c',
                             'SELECT version_num FROM ' + table + ' ORDER BY version_num']).strip()
        if not result[side]:
            raise RuntimeError('Missing schema revision')
    return result


def mounted(info, target):
    values = [v for v in info['Mounts'] if v['Destination'] == target and not v.get('RW')]
    if len(values) != 1:
        raise RuntimeError('Expected a single read-only application mount')
    return Path(values[0]['Source'])


def verify_frontend(fm):
    # The existing web port is bound to the LAN address, not loopback.
    with urllib.request.urlopen('http://192.168.1.245:8080/', timeout=10) as response:
        if sha(response.read()) != fm['files']['frontend/index.html']:
            raise RuntimeError('Served frontend differs from release')


def capture(u, runtime=False):
    live = u.containers()
    backends = {mounted(live[n], '/app/app').parent.parent for n in u.PYTHON_SERVICES}
    if len(backends) != 1:
        raise RuntimeError('Application containers run mixed sources')
    backend = release_path(backends.pop())
    frontend = release_path(mounted(live['domestic-web'], '/usr/share/nginx/html').parent)
    bm, fm = manifest(u, backend), manifest(u, frontend)
    expected = {n.removeprefix('backend/'): h for n, h in bm['files'].items()
                if n.startswith('backend/app/')}
    code = ("import pathlib,json,hashlib; r=pathlib.Path('/app'); "
            "print(json.dumps({p.relative_to(r).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() "
            "for p in (r/'app').rglob('*') if p.is_file() and '__pycache__' not in p.parts}))")
    for name in u.PYTHON_SERVICES:
        actual = json.loads(u.run(['docker', 'exec', 'hengxin-lan-' + name, 'python', '-B', '-c', code]))
        if actual != expected:
            raise RuntimeError('Live source mismatch: ' + name)
    ctx = u.contexts()
    identities = {}
    packages = 'import importlib.metadata as m,json; print(json.dumps(sorted((d.metadata["Name"],d.version) for d in m.distributions())))'
    for name, value in ctx.items():
        pid = u.prop(name, 'MainPID')
        if os.readlink('/proc/' + pid + '/cwd') != str(backend / 'backend'):
            raise RuntimeError('Native process source mismatch: ' + name)
        identities[name] = {k: value[k] for k in ('python', 'user', 'group', 'extra_groups')}
        identities[name]['packages'] = sha(u.native_run(value, code=packages).encode())
    u.health(ctx, frontend=True)
    verify_frontend(fm)
    if runtime:
        for name in u.WORKERS[:2]:
            u.native_run(ctx[name], module='app.execution.runtime_check')
            print('RUNTIME_OK', name, flush=True)
    binaries = {}
    inspect_binary = ("from app.core.config import get_settings; import pathlib,hashlib,json; "
                      "s=get_settings(); paths=[pathlib.Path(s.codex_binary).resolve(),pathlib.Path(s.codex_bwrap_binary).resolve()]; "
                      "print(json.dumps({str(p):hashlib.file_digest(p.open('rb'),'sha256').hexdigest() for p in paths}))")
    for name in u.WORKERS[:2]:
        binaries[name] = json.loads(u.native_run(ctx[name], code=inspect_binary))
    return {'backend': str(backend), 'frontend': str(frontend),
            'backend_commit': bm['commit'], 'frontend_commit': fm['commit'],
            'backend_manifest': sha((backend / 'release-manifest.json').read_bytes()),
            'frontend_manifest': sha((frontend / 'release-manifest.json').read_bytes()),
            'images': {n: v['Image'] for n, v in live.items()},
            'native': identities, 'binaries': binaries, 'schema': schemas(u), 'data': u.data_identity(),
            'configs': {str(p): sha(p.read_bytes()) for p in u.config_paths()}}


def same(expected, actual):
    if expected != actual:
        changed = sorted(k for k in set(expected) | set(actual) if expected.get(k) != actual.get(k))
        raise RuntimeError('Live release drift: ' + ', '.join(changed))


def unchanged_runtime(before, after):
    for key in ('native', 'schema', 'data', 'images', 'binaries'):
        if before[key] != after[key]:
            raise RuntimeError('Unexpected runtime change: ' + key)
