"""Overseas-only update primitives. Never print environment values or mutate domestic data."""
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time


def module(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + '.py'))
    value = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(value)
    return value


r = module('overseas-runtime')
run, private = r.run, r.private
APP, EDGE = r.APP, r.EDGE
API = 'hengxin-overseas-api-1'
PG = 'hengxin-overseas-overseas-postgres-1'
UNITS = ('hengxin-overseas-worker', 'hengxin-overseas-outbox')
DROP = '90-overseas-update.conf'


def sql(query):
    return run('docker', 'exec', PG, 'psql', '-v', 'ON_ERROR_STOP=1', '-U', 'postgres',
               '-d', 'hengxin_overseas', '-Atc', query, capture=True)


def roles_migratable():
    invalid = int(sql("""SELECT count(*) FROM overseas_members m WHERE
      ((SELECT count(*) FROM overseas_member_roles r WHERE r.user_id=m.id)>1
       AND NOT EXISTS (SELECT 1 FROM overseas_member_roles r WHERE r.user_id=m.id AND r.role='super_admin'))
      OR (m.status='active' AND NOT EXISTS (SELECT 1 FROM overseas_member_roles r WHERE r.user_id=m.id))"""))
    assert invalid == 0, 'Resolve ambiguous or missing member roles before migration'


def topology():
    live = json.loads(run('docker', 'inspect', API, capture=True))[0]
    labels = live['Config']['Labels']
    assert labels['com.docker.compose.project'] == 'hengxin-overseas'
    paths = labels['com.docker.compose.project.config_files'].split(',')
    env = labels['com.docker.compose.project.environment_file']
    assert all(Path(p).is_file() and p.startswith('/opt/') for p in [*paths, env])
    return dict(paths=paths, env=env, image=live['Image'])


def compose(data, *args, overlay=None):
    command = ['docker', 'compose', '--env-file', data['env']]
    for path in [*data['paths'], *([str(overlay)] if overlay else [])]:
        command += ['-f', path]
    return run(*command, *args)


def reload_edge():
    run('docker', 'exec', '1Panel-openresty-w177', 'nginx', '-t')
    run('docker', 'exec', '1Panel-openresty-w177', 'nginx', '-s', 'reload')


def close_edge():
    body = EDGE.read_text()
    pattern = r'location \^~ /api/overseas/v1/ \{[^{}]*\}'
    replacement = 'location ^~ /api/overseas/v1/ { return 503; }'
    changed, count = re.subn(pattern, replacement, body)
    assert count == 1, 'Overseas edge location not uniquely identified'
    EDGE.write_text(changed)
    reload_edge()


def pending():
    return int(sql("SELECT count(*) FROM overseas_jobs WHERE status NOT IN "
                   "('succeeded','failed','cancelled') OR (process_id IS NOT NULL AND NOT process_exited)"))


def native_probe(expression):
    # Read the running worker environment in memory; output only the requested JSON evidence.
    pid = run('systemctl', 'show', UNITS[0], '-p', 'MainPID', '--value', capture=True)
    assert int(pid) > 0
    env = dict(os.fsdecode(v).split('=', 1) for v in Path(f'/proc/{pid}/environ').read_bytes().split(b'\0') if v)
    cwd = run('systemctl', 'show', UNITS[0], '-p', 'WorkingDirectory', '--value', capture=True)
    code = 'import json; from app.overseas.execution.worker import celery_app as c; ' + expression
    result = subprocess.run([str(Path(cwd) / '.venv/bin/python'), '-c', code], cwd=cwd,
                            env=env, capture_output=True, text=True, timeout=35)
    assert result.returncode == 0, 'Overseas native probe failed (private stderr withheld)'
    return json.loads(result.stdout)


def worker_idle():
    states = native_probe("i=c.control.inspect(timeout=5); print(json.dumps([i.active(),i.reserved(),i.scheduled()]))")
    assert len(states) == 3 and all(isinstance(x, dict) and len(x) == 1 for x in states), 'Worker replies unavailable'
    return all(not tasks for state in states for tasks in state.values())


def drain(timeout=180):
    deadline = time.monotonic() + timeout
    while True:
        if pending() == 0 and worker_idle():
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Overseas work not drained; workers remain running, intake closed')
        time.sleep(3)


def backup(work, destination, data):
    destination.mkdir(mode=0o700, parents=True, exist_ok=False)
    private(destination / 'topology.json', data)
    for index, path in enumerate([*data['paths'], data['env']]):
        shutil.copy2(path, destination / f'config-{index}')
    for name in ('FRONTEND_RELEASE.json', 'OVERSEAS_RELEASE.json', 'frontend/package.json',
                 'frontend/dist/index.html', 'frontend/dist/index.html.gz'):
        if (APP / name).exists():
            target = destination / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(APP / name, target)
    shutil.copy2(EDGE, destination / 'edge.conf')
    for unit in UNITS:
        folder = Path('/etc/systemd/system') / (unit + '.service.d')
        shutil.copytree(folder, destination / (unit + '.service.d'))
        shutil.copy2(folder.with_name(unit + '.service'), destination / (unit + '.service'))
    private(destination / 'native-pointers.json', {unit: run('systemctl', 'show', unit,
            '-p', 'WorkingDirectory', '--value', capture=True) for unit in UNITS})
    with (destination / 'overseas.dump').open('wb') as stream:
        subprocess.run(['docker', 'exec', PG, 'pg_dump', '-U', 'postgres', '-d', 'hengxin_overseas', '-Fc'], stdout=stream, check=True)
    with (destination / 'overseas.dump').open('rb') as stream:
        subprocess.run(['docker', 'exec', '-i', PG, 'pg_restore', '--list'], stdin=stream, stdout=subprocess.DEVNULL, check=True)
    private(destination / 'COMPLETE', 'Verified backup; no automatic database downgrade/restore permitted')


def prepare_native(source, release):
    old = Path(run('systemctl', 'show', UNITS[0], '-p', 'WorkingDirectory', '--value', capture=True))
    for name in ('pyproject.toml', 'uv.lock'):
        assert (source / 'backend' / name).read_bytes() == (old / name).read_bytes(), 'Native dependency drift'
    target = Path('/opt/hengxin-overseas-releases') / release / 'backend'
    assert not target.exists()
    target.parent.mkdir(parents=True, mode=0o755)
    target.parent.parent.chmod(0o755)
    shutil.copytree(source / 'backend', target)
    for path in (target.parent, target, *target.rglob('*')):
        path.chmod(0o755 if path.is_dir() else 0o644)
    (target / '.venv').symlink_to(old / '.venv', target_is_directory=True)
    run('runuser', '-u', 'hengxin-overseas', '--', str(target / '.venv/bin/python'), '-c',
        'import app,celery; print("OVERSEAS_NATIVE_IMPORT_PASS")', cwd=target)
    return target


def switch_native(target):
    for unit in UNITS:
        command = (str(target / '.venv/bin/celery') + ' -A app.overseas.execution.worker:celery_app worker '
                   '--pool=prefork --concurrency=5 --queues=overseas.cli --loglevel=INFO --hostname=overseas@%H'
                   if unit.endswith('worker') else str(target / '.venv/bin/python') + ' -m app.overseas.execution.outbox')
        path = Path('/etc/systemd/system') / (unit + '.service.d') / DROP
        private(path, '[Service]\nWorkingDirectory=' + str(target) + '\nExecStart=\nExecStart=' + command + '\n')
    run('systemctl', 'daemon-reload')


def wait_worker_ready(timeout=90):
    deadline = time.monotonic() + timeout
    while True:
        try:
            evidence = native_probe("i=c.control.inspect(timeout=5); print(json.dumps({'stats':i.stats(),'queues':i.active_queues()}))")
        except (AssertionError, subprocess.SubprocessError, OSError):
            evidence = {}
        stats, queues = evidence.get('stats') or {}, evidence.get('queues') or {}
        if len(stats) == len(queues) == 1 and stats.keys() == queues.keys():
            assert next(iter(stats.values()))['pool']['max-concurrency'] == 5, 'Wrong worker concurrency'
            assert [q['name'] for q in next(iter(queues.values()))] == ['overseas.cli'], 'Wrong worker queues'
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Overseas worker readiness timed out; intake remains closed')
        time.sleep(3)


def verify(source, manifest, image):
    assert sql('SELECT version_num FROM overseas_alembic_version') == 'overseas_0013'
    live = json.loads(run('docker', 'inspect', API, capture=True))[0]
    assert live['Image'] == image and live['State']['Running']
    expected = {n.removeprefix('backend/'): h for n, h in manifest['files'].items() if n.startswith('backend/')}
    probe = ('import hashlib,json,sys; from pathlib import Path; '
             'm=json.loads(sys.argv[1]); assert all(hashlib.sha256(Path(n).read_bytes()).hexdigest()==h for n,h in m.items())')
    run('docker', 'exec', API, 'python', '-c', probe, json.dumps(expected))
    for unit in UNITS:
        run('systemctl', 'is-active', unit)
    wait_worker_ready()
    for port, route in ((18018, '/api/overseas/v1/health/ready'), (18008, '/api/v1/health/ready'), (18012, '/api/identity/v1/config')):
        run('curl', '--retry', '10', '--retry-delay', '2', '--retry-connrefused', '-fsS', '-o', '/dev/null', f'http://127.0.0.1:{port}{route}')
    r.hashes(APP, {'files': {n: h for n, h in manifest['files'].items() if n.startswith('frontend/')}})
    installed = run('systemctl', 'show', UNITS[0], '-p', 'WorkingDirectory', '--value', capture=True)
    assert run('systemctl', 'show', UNITS[1], '-p', 'WorkingDirectory', '--value', capture=True) == installed
    r.hashes(Path(installed).parent, {'files': {n: h for n, h in manifest['files'].items() if n.startswith('backend/')}})
    for route in ('auth/me', 'tasks'):
        status = run('curl', '-sS', '-o', '/dev/null', '-w', '%{http_code}', f'http://127.0.0.1:18018/api/overseas/v1/{route}', capture=True)
        assert status in ('401', '403'), route
