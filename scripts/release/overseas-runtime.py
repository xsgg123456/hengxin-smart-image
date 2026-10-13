"""Production release primitives; secrets remain in root-only server files."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


base = module('management-runtime')
run, inspect, sql, compose, hashes = base.run, base.inspect, base.sql, base.compose, base.hashes
APP, PREFIX, SERVICES = base.APP, base.PREFIX, base.SERVICES
ORIGIN = 'https://zhitu.qhhengxin.top'
EDGE = Path('/opt/1panel/www/conf.d/zhitu.qhhengxin.top.conf')


def private(path, value):
    path = Path(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as stream:
        os.fchmod(stream.fileno(), 0o600)
        stream.write(value if isinstance(value, str) else json.dumps(value, indent=2))


def pending():
    return int(sql("SELECT (SELECT count(*) FROM job_records WHERE status NOT IN ('succeeded','partial','failed','cancelled')) + (SELECT count(*) FROM api_image_tasks WHERE state NOT IN ('succeeded','failed','partial_failed')) + (SELECT count(*) FROM api_image_items WHERE state NOT IN ('succeeded','failed')) + (SELECT count(*) FROM api_edit_turns WHERE status IN ('queued','running','cancelling'))"))


def baseline():
    result = {'schema': sql('SELECT version_num FROM alembic_version')}
    for table in ('users', 'files', 'image_versions', 'api_image_tasks', 'api_image_items', 'api_image_versions'):
        result[table] = sql(f"SELECT count(*)||':'||md5(coalesce(string_agg(id::text,',' ORDER BY id),'')) FROM {table}")
    return result


def worker(helper, mode):
    if mode.startswith('native-'):
        run('python3', str(helper), 'run-' + mode, '120')
        return
    for attempt in range(20 if mode == 'api-verify' else 1):
        try:
            with helper.open() as stream:
                run('docker', 'exec', '-i', PREFIX + 'api-image-worker-1', 'python', '-', mode, '120', stdin=stream)
            return
        except subprocess.CalledProcessError:
            if mode != 'api-verify' or attempt == 19:
                raise
            time.sleep(3)


def backup(work, destination, paths):
    destination.mkdir(mode=0o700)
    private(destination / 'paths.json', paths)
    private(destination / 'baseline.json', baseline())
    for index, name in enumerate(paths):
        shutil.copy2(name, destination / f'compose-{index}.yaml')
    with (destination / 'database.dump').open('wb') as stream:
        subprocess.run(['docker', 'exec', PREFIX + 'postgres-1', 'pg_dump', '-U', 'hengxin', '-d', 'hengxin', '-Fc'], stdout=stream, check=True)
    with (destination / 'database.dump').open('rb') as stream:
        subprocess.run(['docker', 'exec', '-i', PREFIX + 'postgres-1', 'pg_restore', '--list'], stdin=stream, stdout=subprocess.DEVNULL, check=True)
    for name in ('index.html', 'index.html.gz'):
        if (APP / 'frontend/dist' / name).exists():
            shutil.copy2(APP / 'frontend/dist' / name, destination / name)
    shutil.copy2(APP / 'frontend/package.json', destination / 'frontend-package.json')
    shutil.copy2(APP / 'infra/nginx.vps.conf', destination / 'nginx.vps.conf')
    shutil.copy2(EDGE, destination / 'edge.conf')
    dropin = Path('/etc/systemd/system/hengxin-vps-codex-worker.service.d/90-overseas-release.conf')
    if dropin.exists():
        shutil.copy2(dropin, destination / dropin.name)
    private(destination / 'COMPLETE', 'backup complete')


def prepare_native(source, release):
    target = Path('/opt/hengxin-native-releases') / release / 'backend'
    assert not target.exists(), 'Native release already exists'
    target.parent.mkdir(parents=True, mode=0o755)
    target.parent.parent.chmod(0o755)
    shutil.copytree(source / 'backend', target)
    for p in (target.parent, target, *target.rglob('*')):
        p.chmod(0o755 if p.is_dir() else 0o644)
    run('uv', 'sync', '--locked', '--no-install-project', '--no-dev', '--python', '/opt/hengxin-smart-image/backend/.venv/bin/python', cwd=target, preexec_fn=lambda: os.umask(0o022))
    run('uv', 'pip', 'check', '--python', str(target / '.venv/bin/python'))
    run('runuser', '-u', 'codex', '--', str(target / '.venv/bin/python'), '-c',
        'import celery,app; print("DOMESTIC_NATIVE_IMPORT_PASS")', cwd=target)
    return target


def switch_native(target):
    dropin = Path('/etc/systemd/system/hengxin-vps-codex-worker.service.d/90-overseas-release.conf')
    private(dropin, '[Service]\nWorkingDirectory=' + str(target) + '\nExecStart=\nExecStart=' + str(target / '.venv/bin/celery') + ' -A app.worker.celery_app:celery_app worker --pool=prefork --concurrency=5 --loglevel=INFO --hostname=hx-vps-codex@%H\n')
    run('systemctl', 'daemon-reload')


def proxy_config():
    original = (APP / 'infra/nginx.vps.conf').read_text()
    assert 'location /api/ {' in original and 'location /api/identity/' not in original
    snippets = []
    for path, host in (('identity', 'identity-api'), ('overseas', 'overseas-api')):
        snippets.append('''    location ^~ /api/''' + path + '''/v1/ {
        proxy_pass http://''' + host + ''':8000;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header Connection '';
        proxy_set_header X-Forwarded-Proto $http_x_forwarded_proto;
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        access_log off;
    }
''')
    snippets.append('    location ^~ /internal/ { return 404; }\n')
    return original.replace('    location /api/ {', '\n'.join(snippets) + '\n    location /api/ {', 1)


def publish(source):
    dist, target = source / 'frontend/dist', APP / 'frontend/dist'
    for p in dist.rglob('*'):
        if not p.is_file() or p.name in ('index.html', 'index.html.gz'):
            continue
        dest = target / p.relative_to(dist)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.parent.chmod(0o755)
        shutil.copyfile(p, dest)
        dest.chmod(0o644)
    for name in ('index.html.gz', 'index.html'):
        if (dist / name).exists():
            tmp = target / (name + '.overseas-new')
            shutil.copyfile(dist / name, tmp)
            tmp.chmod(0o644)
            os.replace(tmp, target / name)
        else:
            (target / name).unlink(missing_ok=True)
    shutil.copy2(source / 'frontend/package.json', APP / 'frontend/package.json')
    (APP / 'frontend/package.json').chmod(0o644)


def ready():
    for port, path in ((18008, '/api/v1/health/ready'), (18018, '/api/overseas/v1/health/ready'), (18012, '/api/identity/v1/config')):
        run('curl', '--retry', '10', '--retry-delay', '2', '--retry-connrefused', '-fsS', '-o', '/dev/null', f'http://127.0.0.1:{port}{path}')


def restore_front(backup_dir):
    for name in ('index.html', 'index.html.gz'):
        target = APP / 'frontend/dist' / name
        if (backup_dir / name).exists():
            shutil.copy2(backup_dir / name, target)
        else:
            target.unlink(missing_ok=True)
    shutil.copy2(backup_dir / 'frontend-package.json', APP / 'frontend/package.json')
    shutil.copyfile(backup_dir / 'nginx.vps.conf', APP / 'infra/nginx.vps.conf')
    shutil.copyfile(backup_dir / 'edge.conf', EDGE)
    run('docker', 'exec', '1Panel-openresty-w177', 'nginx', '-t')
    run('docker', 'exec', '1Panel-openresty-w177', 'nginx', '-s', 'reload')


def install_edge():
    original = EDGE.read_text()
    anchor = '    ssl_prefer_server_ciphers off;\n'
    assert original.count(anchor) == 1 and '/api/identity/v1/' not in original
    blocks = []
    for service in ('identity', 'overseas'):
        blocks.append('''
    location ^~ /api/''' + service + '''/v1/ {
        proxy_pass http://127.0.0.1:18080;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto https;
        proxy_set_header Connection '';
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 300s;
        access_log off;
        error_log /dev/null crit;
    }
''')
    EDGE.write_text(original.replace(anchor, anchor + ''.join(blocks), 1))
    run('docker', 'exec', '1Panel-openresty-w177', 'nginx', '-t')
    run('docker', 'exec', '1Panel-openresty-w177', 'nginx', '-s', 'reload')
