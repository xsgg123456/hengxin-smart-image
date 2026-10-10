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
NATIVE_RESOURCES = {
    'modules/api_image_edits/image_edit_prompt.txt',
    'modules/api_image_edits/text_edit_prompt.txt',
    'modules/api_image_edits/text_repair_prompt.txt',
}
SERVICES = ('api', 'outbox', 'api-image-worker', 'api-image-outbox', 'image-variants')


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


def native_policy():
    pid = int(run('systemctl', 'show', 'hengxin-vps-codex-worker', '-p', 'MainPID', '--value', capture=True))
    assert pid > 0, 'Native worker PID unavailable'
    env = dict(item.split(b'=', 1) for item in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0') if item)
    assert env.get(b'CLI_RETENTION_ENABLED', b'false').lower() in (b'false', b'0', b'no', b'off')
    assert env.get(b'GENERATION_CONCURRENCY') == b'5'
    assert env.get(b'CODEX_TIMEOUT_SECONDS') == b'7200'


def prepare(work, manifest):
    source = work / 'src'
    hashes(source, manifest)
    native_policy()
    paths = inspect('api')['Config']['Labels']['com.docker.compose.project.config_files'].split(',')
    assert all(Path(p).is_file() and p.startswith('/opt/') for p in paths)
    config = json.loads(compose(paths, 'config', '--format', 'json', capture=True))
    for name in SERVICES:
        live, spec = inspect(name), config['services'][name]
        assert live['State']['Running'] and live['Config']['Image'] == spec['image'], name
        assert spec['image'] == 'hengxin-smart-image-backend:api-edit-20261006-15fdeb3', name
        env = dict(item.split('=', 1) for item in live['Config']['Env'])
        assert all(env.get(k) == str(v) for k, v in spec.get('environment', {}).items()), name
        assert env.get('CLI_RETENTION_ENABLED', 'false').lower() in ('false', '0', 'no', 'off'), name
        assert not spec.get('command') or spec['command'] == live['Config']['Cmd'], name
    (work / 'old-compose.private.json').write_text(json.dumps(config))
    (work / 'old-paths.json').write_text(json.dumps(paths))
    image = 'hengxin-smart-image-backend:' + manifest['release']
    changed = {name: {'image': image, 'build': {'context': str(source), 'dockerfile': 'infra/Dockerfile.backend'}}
               for name in (*SERVICES, 'migrate')}
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
    for name in ('API_RELEASE.json', 'API_IMAGE_RELEASE.json', 'FRONTEND_RELEASE.json', 'API_TEXT_RELEASE.json', 'API_EDIT_RELEASE.json', 'MANAGEMENT_RELEASE.json'):
        if (APP / name).exists(): shutil.copy2(APP / name, backup / name)
    shutil.copy2(APP / 'frontend/package.json', backup / 'frontend-package.json')
    for name in ('nginx.vps.conf', 'nginx.media.conf'):
        if (APP / 'infra' / name).exists():
            shutil.copy2(APP / 'infra' / name, backup / name)
    shutil.copy2(work / 'old-compose.private.json', backup / 'old-compose.private.json')
    shutil.copy2(work / 'old-paths.json', backup / 'old-paths.json')
    for index, name in enumerate(json.loads((work / 'old-paths.json').read_text())):
        shutil.copy2(name, backup / ('compose-' + str(index) + '.yaml'))
    (backup / 'COMPLETE').write_text('backup verified')


def install_native(source):
    uid, gid = (NATIVE / 'app').stat().st_uid, (NATIVE / 'app').stat().st_gid
    app_source = source / 'backend/app'
    assert all((app_source / name).is_file() for name in NATIVE_RESOURCES)
    files = set(app_source.rglob('*.py')) | {app_source / name for name in NATIVE_RESOURCES}
    for path in sorted(files):
        assert not path.is_symlink() and not any(p.is_symlink() for p in path.parents)
        dest = NATIVE / 'app' / path.relative_to(source / 'backend/app')
        assert not any(p.is_symlink() for p in (dest, *dest.parents))
        dest.parent.mkdir(parents=True, exist_ok=True)
        for directory in (dest.parent, *dest.parent.parents):
            if directory == NATIVE: break
            directory.chmod(0o755); os.chown(directory, uid, gid)
        shutil.copyfile(path, dest); dest.chmod(0o644); os.chown(dest, uid, gid)


def publish_frontend(source, work, manifest, paths):
    # The frontend service is stopped by the controller; preserve bind-mount inode.
    for name in ('nginx.vps.conf', 'nginx.media.conf'):
        shutil.copyfile(source / 'infra' / name, APP / 'infra' / name)
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
    for name in ('API_RELEASE.json', 'API_IMAGE_RELEASE.json', 'FRONTEND_RELEASE.json', 'API_TEXT_RELEASE.json', 'API_EDIT_RELEASE.json', 'MANAGEMENT_RELEASE.json'):
        tmp = APP / (name + '.new'); tmp.write_text(json.dumps(value)); os.replace(tmp, APP / name)
