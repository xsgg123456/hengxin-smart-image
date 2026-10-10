"""API-only release operations; executor processes and database stay untouched."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil

spec = importlib.util.spec_from_file_location('management_runtime', Path(__file__).with_name('management-runtime.py'))
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
APP, PREFIX = base.APP, base.PREFIX
run, inspect, sql, compose, hashes = base.run, base.inspect, base.sql, base.compose, base.hashes
WORKERS = ('outbox', 'api-image-worker', 'api-image-outbox', 'image-variants', 'web')
MARKERS = ('API_RELEASE.json', 'FRONTEND_RELEASE.json', 'USAGE_TOTAL_RELEASE.json')
OLD_IMAGE = 'hengxin-smart-image-backend:management-20261010-4a09a59'


def private(path, value):
    with path.open('w', encoding='utf-8') as stream:
        os.chmod(path, 0o600)
        json.dump(value, stream)


def identity():
    result = {}
    for name in WORKERS:
        live = inspect(name)
        assert live['State']['Running'], 'Executor/web is not running: ' + name
        result[name] = [live['Id'], live['State']['StartedAt']]
    result['native'] = [run('systemctl', 'show', 'hengxin-vps-codex-worker', '-p', p,
                            '--value', capture=True) for p in ('MainPID', 'ExecMainStartTimestampMonotonic')]
    assert int(result['native'][0]) > 0 and int(result['native'][1]) > 0
    assert run('systemctl', 'is-active', 'hengxin-vps-codex-worker', capture=True) == 'active'
    result['nginx'] = {name: [p.stat().st_dev, p.stat().st_ino, hashlib.sha256(p.read_bytes()).hexdigest()]
                       for name in ('nginx.vps.conf', 'nginx.media.conf')
                       if (p := APP / 'infra' / name).exists()}
    return result


def unchanged(before):
    assert identity() == before, 'Executor/web identity or nginx configuration changed'


def api_settings(live):
    return {key: live['Config'].get(key) for key in ('Cmd', 'Entrypoint', 'User', 'WorkingDir')} | {
        'Env': sorted(live['Config'].get('Env') or []),
        'Mounts': sorted([{k: m.get(k) for k in ('Type', 'Source', 'Destination', 'RW', 'Propagation')}
                          for m in live['Mounts']], key=lambda m: m['Destination']),
        'Ports': live['HostConfig']['PortBindings'],
    }


def ready():
    assert inspect('api')['State'].get('Health', {}).get('Status') == 'healthy', 'API is not healthy'
    run('curl', '--retry', '8', '--retry-delay', '2', '-fsS', '-o', '/dev/null',
        'http://127.0.0.1:18008/api/v1/health/ready')


def prepare(work, manifest):
    hashes(work / 'src', manifest)
    assert sql('SELECT version_num FROM alembic_version') == '0026'
    live = inspect('api')
    assert live['Config']['Image'] == OLD_IMAGE, 'Unexpected existing API image'
    paths = live['Config']['Labels']['com.docker.compose.project.config_files'].split(',')
    assert all(Path(p).is_file() and Path(p).is_absolute() for p in paths)
    config = json.loads(compose(paths, 'config', '--format', 'json', capture=True))
    service = config['services']['api']
    assert service['image'] == live['Config']['Image']
    env = dict(item.split('=', 1) for item in live['Config']['Env'])
    assert all(env.get(k) == str(v) for k, v in service.get('environment', {}).items())
    assert not service.get('command') or service['command'] == live['Config']['Cmd']
    ready()
    private(work / 'old-compose.private.json', config)
    private(work / 'old-paths.json', paths)
    private(work / 'old-api.private.json', live)
    image = 'hengxin-smart-image-backend:' + manifest['release']
    override = {'services': {'api': {'image': image, 'build': {
        'context': str(work / 'src'), 'dockerfile': 'infra/Dockerfile.backend'}}}}
    private(work / 'api-override.yaml', override)
    merged = json.loads(compose([*paths, work / 'api-override.yaml'], 'config', '--format', 'json', capture=True))
    expected = json.loads(json.dumps(config))
    expected['services']['api']['image'] = image
    expected['services']['api']['build'] = merged['services']['api']['build']
    assert expected == merged, 'Override changed non-image API or other service configuration'
    return paths, image, live


def backup(work, target, before):
    target.mkdir(mode=0o700)  # Never reuse an old backup.
    private(target / 'before.json', before)
    for name in ('old-compose.private.json', 'old-paths.json', 'old-api.private.json'):
        shutil.copy2(work / name, target / name)
    for i, path in enumerate(json.loads((work / 'old-paths.json').read_text())):
        shutil.copyfile(path, target / ('compose-' + str(i) + '.yaml'))
        (target / ('compose-' + str(i) + '.yaml')).chmod(0o600)
    for name in ('index.html', 'index.html.gz'):
        source = APP / 'frontend/dist' / name
        if source.exists(): shutil.copy2(source, target / name)
    shutil.copy2(APP / 'frontend/package.json', target / 'frontend-package.json')
    for name in MARKERS:
        if (APP / name).exists(): shutil.copy2(APP / name, target / name)
    (target / 'COMPLETE').write_text('complete')


def atomic_copy(source, target):
    tmp = target.with_name(target.name + '.usage-total-new')
    shutil.copyfile(source, tmp)
    tmp.chmod(0o644)
    os.replace(tmp, target)


def publish(source, work, manifest, paths):
    dist, target = source / 'frontend/dist', APP / 'frontend/dist'
    for source_file in dist.rglob('*'):
        if not source_file.is_file() or source_file.name in ('index.html', 'index.html.gz'): continue
        dest = target / source_file.relative_to(dist)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.parent.chmod(0o755)
        if dest.exists():
            assert dest.read_bytes() == source_file.read_bytes(), 'Existing asset collision'
        else: atomic_copy(source_file, dest)
    for name in ('index.html.gz', 'index.html'):
        if (dist / name).exists(): atomic_copy(dist / name, target / name)
        else: (target / name).unlink(missing_ok=True)
    atomic_copy(source / 'frontend/package.json', APP / 'frontend/package.json')
    value = dict(manifest, composeBaseOverlays=paths, composeOverride=str(work / 'api-override.yaml'))
    for name in MARKERS:
        tmp = APP / (name + '.usage-total-new')
        private(tmp, value)
        os.replace(tmp, APP / name)


def restore(target):
    assert (target / 'COMPLETE').is_file()
    for name in ('index.html.gz', 'index.html'):
        dest = APP / 'frontend/dist' / name
        if (target / name).exists(): atomic_copy(target / name, dest)
        else: dest.unlink(missing_ok=True)
    atomic_copy(target / 'frontend-package.json', APP / 'frontend/package.json')
    for name in MARKERS:
        if (target / name).exists(): atomic_copy(target / name, APP / name)
        else: (APP / name).unlink(missing_ok=True)


def reload_nginx():
    run('docker', 'exec', PREFIX + 'web-1', 'nginx', '-s', 'reload')
