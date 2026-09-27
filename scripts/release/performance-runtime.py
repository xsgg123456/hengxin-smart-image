"""Server-only release operations. No secret values are printed."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

APP = Path('/opt/hengxin-smart-image')
NATIVE = APP / 'backend'
PREFIX = 'hengxin-vps-staging-'
SERVICES = ('api', 'outbox', 'api-image-worker', 'api-image-outbox')


def run(*args, capture=False, **kwargs):
    result = subprocess.run(args, check=True, text=True, stdout=subprocess.PIPE if capture else None, **kwargs)
    return result.stdout.strip() if capture else ''


def inspect(name):
    return json.loads(run('docker', 'inspect', PREFIX + name + '-1', capture=True))[0]


def sql(query):
    return run('docker', 'exec', PREFIX + 'postgres-1', 'psql', '-v', 'ON_ERROR_STOP=1',
               '-U', 'hengxin', '-d', 'hengxin', '-Atc', query, capture=True)


def compose(paths, *args, capture=False):
    command = ['docker', 'compose']
    for path in paths:
        command.extend(['-f', str(path)])
    return run(*command, *args, capture=capture, cwd=APP / 'infra')


def hashes(root, manifest):
    for name, digest in manifest['files'].items():
        path = root / name
        assert path.resolve().is_relative_to(root.resolve()) and not path.is_symlink(), name
        assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, name


def prepare(work, manifest):
    source = work / 'src'
    hashes(source, manifest)
    paths = inspect('api')['Config']['Labels']['com.docker.compose.project.config_files'].split(',')
    assert all(Path(p).is_file() and p.startswith('/opt/') for p in paths)
    config = json.loads(compose(paths, 'config', '--format', 'json', capture=True))
    for name in SERVICES:
        live, spec = inspect(name), config['services'][name]
        assert live['State']['Running'] and live['Config']['Image'] == spec['image'], name
        assert spec['image'] == 'hengxin-smart-image-backend:delivery-20260927-b1f212b', name
        env = dict(item.split('=', 1) for item in live['Config']['Env'])
        assert all(env.get(k) == str(v) for k, v in spec.get('environment', {}).items()), name
        assert not spec.get('command') or spec['command'] == live['Config']['Cmd'], name
    (work / 'old-compose.private.json').write_text(json.dumps(config))
    (work / 'old-paths.json').write_text(json.dumps(paths))
    image = 'hengxin-smart-image-backend:' + manifest['release']
    changed = {name: {'image': image, 'build': {'context': str(source), 'dockerfile': 'infra/Dockerfile.backend'}}
               for name in (*SERVICES, 'migrate')}
    environment = dict(config['services']['api']['environment'])
    environment.update(DB_POOL_SIZE='1', DB_MAX_OVERFLOW='0', DB_APPLICATION_NAME='hx-image-variants')
    changed['image-variants'] = {'image': image, 'init': True, 'restart': 'unless-stopped',
        'environment': environment, 'command': ['python', '-m', 'app.modules.files.variant_worker', '--backfill'],
        'networks': config['services']['api'].get('networks', {'default': None}),
        'mem_limit': '1g', 'memswap_limit': '1g', 'cpus': 1.0, 'pids_limit': 64}
    (work / 'api-override.yaml').write_text(json.dumps({'services': changed}, indent=2))
    compose([*paths, work / 'api-override.yaml'], 'config', '--quiet')
    # No dependency update is needed; refuse unnoticed native dependency drift.
    for name in ('pyproject.toml', 'uv.lock'):
        assert (source / 'backend' / name).read_bytes() == (NATIVE / name).read_bytes(), name
    return paths, image


def backup(work, backup):
    backup.mkdir(mode=0o700)
    with (backup / 'database.dump').open('wb') as stream:
        subprocess.run(['docker', 'exec', PREFIX + 'postgres-1', 'pg_dump', '-U', 'hengxin', '-d', 'hengxin', '-Fc'], stdout=stream, check=True)
    with (backup / 'database.dump').open('rb') as stream:
        subprocess.run(['docker', 'exec', '-i', PREFIX + 'postgres-1', 'pg_restore', '--list'], stdin=stream, stdout=subprocess.DEVNULL, check=True)
    run('cp', '-a', str(NATIVE / 'app'), str(backup / 'native-app'))
    for name in ('index.html', 'index.html.gz'):
        path = APP / 'frontend/dist' / name
        if path.exists(): shutil.copy2(path, backup / name)
    for name in ('API_RELEASE.json', 'API_IMAGE_RELEASE.json', 'FRONTEND_RELEASE.json', 'PERFORMANCE_RELEASE.json'):
        if (APP / name).exists(): shutil.copy2(APP / name, backup / name)
    shutil.copy2(APP / 'frontend/package.json', backup / 'frontend-package.json')
    shutil.copy2(work / 'old-compose.private.json', backup / 'old-compose.private.json')


def install_native(source):
    uid, gid = (NATIVE / 'app').stat().st_uid, (NATIVE / 'app').stat().st_gid
    for path in (source / 'backend/app').rglob('*.py'):
        dest = NATIVE / 'app' / path.relative_to(source / 'backend/app')
        assert not any(p.is_symlink() for p in (dest, *dest.parents))
        dest.parent.mkdir(parents=True, exist_ok=True)
        for directory in (dest.parent, *dest.parent.parents):
            if directory == NATIVE: break
            directory.chmod(0o755); os.chown(directory, uid, gid)
        shutil.copyfile(path, dest); dest.chmod(0o644); os.chown(dest, uid, gid)


def publish_frontend(source, work, manifest, paths):
    dist, target = source / 'frontend/dist', APP / 'frontend/dist'
    for file in dist.rglob('*'):
        if not file.is_file() or file.name in ('index.html', 'index.html.gz'): continue
        dest = target / file.relative_to(dist)
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(file, dest); dest.chmod(0o644)
    for directory in target.rglob('*'):
        if directory.is_dir(): directory.chmod(0o755)
    for name in ('index.html.gz', 'index.html'):
        if not (dist / name).exists():
            (target / name).unlink(missing_ok=True); continue
        tmp = target / (name + '.new')
        shutil.copyfile(dist / name, tmp); tmp.chmod(0o644); os.replace(tmp, target / name)
    shutil.copyfile(source / 'frontend/package.json', APP / 'frontend/package.json')
    value = dict(manifest, composeBaseOverlays=paths, composeOverride=str(work / 'api-override.yaml'))
    for name in ('API_RELEASE.json', 'API_IMAGE_RELEASE.json', 'FRONTEND_RELEASE.json', 'PERFORMANCE_RELEASE.json'):
        tmp = APP / (name + '.new'); tmp.write_text(json.dumps(value)); os.replace(tmp, APP / name)
