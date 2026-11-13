""".245-only immutable source release. prepare is read-only to running applications.

Upload a Git archive to RELEASE/backend and the LAN build to RELEASE/frontend.
release-manifest.json contains {commit: <40 hex>, files: {relative_path: sha256}}.
Run prepare, review its private transaction directory, then explicitly run apply.
No images are built, no migrations run, no data containers are stopped/recreated.
"""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import stat
import subprocess
import tempfile
import time
import urllib.request

ROOT = Path('/opt/hengxin-lan')
RELEASE = Path('/opt/hengxin-unified-releases/unified-20261111')
WORK = ROOT / 'unify-20261111'
REUSABLE = False
COMPOSE = ROOT / 'compose.json'
SYSTEMD = Path('/etc/systemd/system')
PYTHON_SERVICES = {
    'domestic-api': 'app.main', 'overseas-api': 'app.overseas.main',
    'identity-api': 'app.identity.main',
    'domestic-api-image-worker': 'app.modules.api_image_edits.celery_app',
    'domestic-api-image-outbox': 'app.modules.api_image_edits.outbox',
    'domestic-image-variants': 'app.modules.files.variant_worker',
    'domestic-outbox': 'app.worker.outbox',
    'overseas-skill-publisher': 'app.overseas.management.skill_publisher',
}
NATIVE = {
    'hengxin-codex-accounts': 'app.account_management.service',
    'hengxin-codex-auth': 'app.execution.credential_broker',
    'hengxin-domestic-deletions': 'app.retention.worker',
    'hengxin-retention': 'app.retention.worker',
    'hengxin-vps-codex-worker': 'app.worker.celery_app',
    'hengxin-overseas-worker': 'app.overseas.execution.worker',
    'hengxin-overseas-outbox': 'app.overseas.execution.outbox',
}
WORKERS = ('hengxin-vps-codex-worker', 'hengxin-overseas-worker', 'domestic-api-image-worker')
ENTRIES = ('domestic-web', 'domestic-api', 'overseas-api', 'identity-api')
ACCOUNT_SOCKETS = ('/run/hengxin-codex-accounts/domestic/control.sock',
                   '/run/hengxin-codex-accounts/overseas/control.sock',
                   '/run/hengxin-codex-accounts/worker.sock', '/run/hengxin-codex-auth/broker.sock')
APPS = (*PYTHON_SERVICES, 'domestic-web')
DATA = {'domestic-postgres', 'domestic-redis', 'domestic-minio',
        'overseas-postgres', 'overseas-redis', 'overseas-minio', 'identity-redis'}
NATIVE_AUX = ('hengxin-retention', 'hengxin-domestic-deletions', 'hengxin-overseas-outbox')
DROPIN = '90-unified-source.conf'
STOP_OVERRIDE = b'[Service]\nRestart=no\nSendSIGKILL=no\nTimeoutStopSec=90s\n'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def run(argv, **kwargs):
    # Capture but never print command output: exceptions/SQL errors can contain secrets.
    try:
        return subprocess.run(argv, check=True, capture_output=True, text=True,
                              timeout=kwargs.pop('timeout', 60), **kwargs).stdout
    except (subprocess.SubprocessError, OSError):
        raise RuntimeError('Command failed: ' + str(argv[0])) from None


def safe(path, missing=False):
    path = Path(path)
    if not path.is_absolute() or '..' in path.parts:
        raise RuntimeError('Unsafe absolute path')
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            if missing and item == path:
                continue
            raise
        if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise RuntimeError('Unsafe deployment path: ' + str(item))
        if item == path and stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise RuntimeError('Hardlinked deployment file')


def write(path, data, mode=0o600, exclusive=False):
    safe(path, missing=True)
    fd, name = tempfile.mkstemp(prefix='.unify-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            os.link(name, path)
        else:
            os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def compose(*args, candidate=False, config=None):
    config = config or (WORK / 'compose.candidate.json' if candidate else COMPOSE)
    return run(['docker', 'compose', '-p', 'hengxin-lan', '-f', str(config), *args], timeout=180)


def app_command(action, names, candidate=False):
    if not names or not set(names) <= set(APPS):
        raise RuntimeError('Non-application compose action refused')
    if action == 'up':
        return compose('up', '-d', '--no-deps', '--pull', 'never', *names, candidate=candidate)
    if action == 'stop':
        # Wait for graceful TERM only; never let docker stop escalate to SIGKILL.
        return compose('stop', '--timeout', '-1', *names, candidate=candidate)
    raise ValueError('Unsupported application action')


def prop(name, key):
    return run(['systemctl', 'show', name, '-p', key, '--value']).strip()


def containers():
    result = {}
    for name in APPS:
        info = json.loads(run(['docker', 'inspect', 'hengxin-lan-' + name]))[0]
        if info['Config']['Labels'].get('com.docker.compose.project') != 'hengxin-lan':
            raise RuntimeError('Unexpected container project')
        result[name] = info
    return result


def data_identity():
    # Ask only for IDs: full inspect contains credentials in command/env fields.
    return {n: run(['docker', 'inspect', '--format', '{{.Id}}', 'hengxin-lan-' + n]).strip()
            for n in sorted(DATA)}


def contexts():
    result = {}
    for name in NATIVE:
        pid = int(prop(name, 'MainPID'))
        if prop(name, 'ActiveState') != 'active' or pid <= 1:
            raise RuntimeError('Expected active native service: ' + name)
        root = Path('/proc') / str(pid)
        argv = root.joinpath('cmdline').read_bytes().decode().rstrip('\0').split('\0')
        env = dict(x.split('=', 1) for x in root.joinpath('environ').read_bytes().decode().split('\0') if '=' in x)
        fields = dict(x.split(':', 1) for x in root.joinpath('status').read_text().splitlines() if ':' in x)
        uid, gid = [int(x) for x in fields['Uid'].split()], [int(x) for x in fields['Gid'].split()]
        if len(set(uid)) != 1 or len(set(gid)) != 1 or uid[0] == 0:
            raise RuntimeError('Unexpected service identity')
        if not argv[0].startswith(('/usr/bin/python', '/opt/hengxin-')) or 'python' not in Path(argv[0]).name:
            raise RuntimeError('Unexpected native interpreter')
        if env.get('PYTHONPATH'):
            raise RuntimeError('Explicit native PYTHONPATH requires manual review')
        result[name] = {'python': argv[0], 'cwd': prop(name, 'WorkingDirectory'), 'env': env,
                        'user': uid[0], 'group': gid[0], 'extra_groups': [int(x) for x in fields['Groups'].split()]}
    return result


def native_run(ctx, code=None, module=None, cwd=None, args=(), timeout=120, pass_fds=()):
    argv = [ctx['python'], '-B', '-c', code] if code is not None else [ctx['python'], '-B', '-m', module]
    extra = {'pass_fds': pass_fds} if pass_fds else {}
    return run([*argv, *args], cwd=cwd or ctx['cwd'], env=ctx['env'], timeout=timeout,
               **{k: ctx[k] for k in ('user', 'group', 'extra_groups')}, **extra)


def validate_release():
    manifest_path = RELEASE / 'release-manifest.json'
    safe(manifest_path)
    raw = manifest_path.read_bytes()
    manifest = json.loads(raw)
    if not re.fullmatch('[0-9a-f]{40}', manifest.get('commit', '')):
        raise RuntimeError('A full Git commit is required')
    files = manifest.get('files', {})
    if not files or not all(isinstance(k, str) and isinstance(v, str) for k, v in files.items()):
        raise RuntimeError('Invalid release manifest')
    actual = set()
    for root in ('backend', 'frontend'):
        safe(RELEASE / root)
        for path in (RELEASE / root).rglob('*'):
            safe(path)
            if path.is_file():
                actual.add(path.relative_to(RELEASE).as_posix())
    if actual != set(files):
        raise RuntimeError('Release file inventory differs from manifest')
    for name, expected in files.items():
        rel = PurePosixPath(name)
        if rel.is_absolute() or '..' in rel.parts or rel.parts[0] not in ('backend', 'frontend'):
            raise RuntimeError('Unsafe manifest path')
        if digest((RELEASE / name).read_bytes()) != expected:
            raise RuntimeError('Release checksum mismatch: ' + name)
    renderer = RELEASE / 'backend/app/execution/office_render.py'
    if stat.S_IMODE(renderer.stat().st_mode) != 0o755:
        raise RuntimeError('office_render.py requires mode 0755')
    if not (RELEASE / 'frontend/index.html').is_file():
        raise RuntimeError('Missing frontend index')
    return digest(raw)


def candidate_compose(original):
    result = copy.deepcopy(original)
    if result.get('name') != 'hengxin-lan' or set(result['services']) != set(APPS) | DATA:
        raise RuntimeError('Compose inventory changed')
    for name in PYTHON_SERVICES:
        service = result['services'][name]
        mounts = service.get('volumes', [])
        if any(not isinstance(v, dict) or 'target' not in v for v in mounts):
            raise RuntimeError('Only explicit compose mounts supported')
        if any(v['target'] in ('/', '/app') for v in mounts):
            raise RuntimeError('Unexpected parent code mount')
        service['volumes'] = [v for v in mounts if not (
            v['target'] == '/app/app' or v['target'].startswith('/app/app/'))]
        service['volumes'].append({'type': 'bind', 'source': str(RELEASE / 'backend/app'),
                                  'target': '/app/app', 'read_only': True,
                                  'bind': {'create_host_path': False}})
    web = result['services']['domestic-web']['volumes']
    matched = [v for v in web if v['target'] == '/usr/share/nginx/html']
    if len(matched) != 1 or not matched[0].get('read_only'):
        raise RuntimeError('Unexpected frontend mount')
    matched[0]['source'] = str(RELEASE / 'frontend')
    return result


def config_paths():
    paths = [COMPOSE]
    for name in NATIVE:
        fragment = Path(prop(name, 'FragmentPath'))
        expected = SYSTEMD / (name + '.service')
        if fragment != expected:
            raise RuntimeError('Unexpected unit fragment')
        paths.append(fragment)
        for item in prop(name, 'DropInPaths').split():
            path = Path(item)
            if path.parent != SYSTEMD / (name + '.service.d'):
                raise RuntimeError('Unexpected unit drop-in')
            paths.append(path)
        env = Path('/etc/hengxin-lan') / (name + '.env')
        if env.exists():
            paths.append(env)
    return paths


def probe_candidate(ctx, config):
    compose('config', '--quiet', config=config)
    for name, module in PYTHON_SERVICES.items():
        compose('run', '--rm', '--no-deps', '--pull', 'never', '--entrypoint', 'python', name,
                '-B', '-c', 'import importlib; importlib.import_module(' + repr(module) + ')', config=config)
        print('IMPORT_OK', name, flush=True)
    for name, module in NATIVE.items():
        native_run(ctx[name], code='import importlib; importlib.import_module(' + repr(module) + ')',
                   cwd=str(RELEASE / 'backend'))
        print('IMPORT_OK', name, flush=True)
    for name in WORKERS[:2]:
        native_run(ctx[name], module='app.execution.runtime_check', cwd=str(RELEASE / 'backend'))
        print('RUNTIME_OK', name, flush=True)


def preflight():
    """Dependency/identity probes only, before the final Git manifest is fixed."""
    safe(COMPOSE)
    ctx = contexts()
    candidate = candidate_compose(json.loads(COMPOSE.read_bytes()))
    data_before = data_identity()
    fd, name = tempfile.mkstemp(prefix='.unify-preflight-', suffix='.json', dir=ROOT)
    try:
        with os.fdopen(fd, 'w') as stream:
            os.fchmod(stream.fileno(), 0o600)
            json.dump(candidate, stream)
        probe_candidate(ctx, Path(name))
        if data_identity() != data_before:
            raise RuntimeError('Data container identity changed during preflight')
    finally:
        Path(name).unlink(missing_ok=True)
    print('PREFLIGHT_OK; final manifest/prepare still required', flush=True)


def prepare():
    manifest_hash = validate_release()
    ctx = contexts()
    live = containers()
    if any(not v['State']['Running'] for v in live.values()):
        raise RuntimeError('Expected all application containers running')
    original = COMPOSE.read_bytes()
    candidate = candidate_compose(json.loads(original))
    for name in NATIVE:
        for filename in (('91-unify-stop.conf',) if REUSABLE else (DROPIN, '91-unify-stop.conf')):
            target = SYSTEMD / (name + '.service.d') / filename
            if target.exists():
                raise RuntimeError('Existing maintenance drop-in; rerun refused')
    safe(WORK, missing=True)
    if WORK.exists():
        if (WORK / 'prepared.json').exists() or (WORK / 'started.json').exists():
            raise RuntimeError('Existing prepared/applied transaction; rerun refused')
    else:
        WORK.mkdir(mode=0o700)
    def retained(path, data):
        # A failed import preflight may be retried, but its original backups
        # cannot silently follow a subsequently changed production configuration.
        if path.exists():
            safe(path)
            if path.read_bytes() != data:
                raise RuntimeError('Preparation backup/candidate drift')
        else:
            write(path, data, exclusive=True)
    records = []
    paths = config_paths()
    if REUSABLE:
        for name in NATIVE:
            path = SYSTEMD / (name + '.service.d') / DROPIN
            if path.exists() and path not in paths:
                paths.append(path)
    for index, path in enumerate(paths):
        safe(path)
        data = path.read_bytes()
        retained(WORK / ('backup-' + str(index)), data)
        records.append({'path': str(path), 'backup': 'backup-' + str(index),
                        'sha256': digest(data), 'mode': stat.S_IMODE(path.stat().st_mode)})
    retained(WORK / 'compose.candidate.json', (json.dumps(candidate, indent=2) + '\n').encode())
    for name in NATIVE:
        # Existing ExecStart and runtime-check interpreter remain unchanged. Both
        # resolve app modules from this WorkingDirectory, preserving per-side venvs.
        data = ('[Service]\nWorkingDirectory=' + str(RELEASE / 'backend') + '\n').encode()
        retained(WORK / (name + '.conf'), data)
    probe_candidate(ctx, WORK / 'compose.candidate.json')
    if validate_release() != manifest_hash:
        raise RuntimeError('Release drift during prepare')
    baseline = {'release_manifest': manifest_hash, 'configs': records, 'data_containers': data_identity(),
                'candidate': digest((WORK / 'compose.candidate.json').read_bytes()),
                'native': {n: {k: v for k, v in c.items() if k != 'env'} for n, c in ctx.items()},
                'dropins': {n: digest((WORK / (n + '.conf')).read_bytes()) for n in NATIVE}}
    write(WORK / 'prepared.json', json.dumps(baseline, indent=2).encode(), exclusive=True)
    print('PREPARED; no production services switched', flush=True)


CONTROL = r'''
import json,sys
from sqlalchemy import func,select
side,action,node=sys.argv[1:]
if side=='overseas':
 from app.overseas.execution.worker import celery_app
 from app.overseas.db import session_factory
 from app.overseas.execution.models import Job
 queue='overseas.cli'
else:
 from app.db.session import session_factory
 if side=='domestic':
  from app.worker.celery_app import celery_app
  from app.models import Job
  queue='celery'
 else:
  from app.modules.api_image_edits.celery_app import celery_app
  from app.modules.api_image_edits.models import ApiItem
  queue='api_image_edits'
c=celery_app.control
def inspect(method):
 value=getattr(c.inspect(destination=[node],timeout=3),method)()
 if not isinstance(value,dict) or not isinstance(value.get(node),list):
  raise RuntimeError('Inspection unavailable')
 return value[node]
if action in ('pause','resume'):
 value=getattr(c,'cancel_consumer' if action=='pause' else 'add_consumer')(queue,destination=[node],reply=True,timeout=3)
 if not value or not any('ok' in r.get(node,{}) for r in value):
  raise RuntimeError('Consumer acknowledgment absent')
counts={k:len(inspect(k)) for k in ('active','reserved','scheduled')}
counts['queues']=[v['name'] for v in inspect('active_queues')]
with session_factory()() as db:
 if side=='image':
  counts['database']=db.scalar(select(func.count()).select_from(ApiItem).where(ApiItem.state.in_(
   ['queued','retry_wait','running','collecting','uncertain'])))
 else:
  counts['database']=db.scalar(select(func.count()).select_from(Job).where(Job.status.in_(
   ['queued','running','collecting','cancelling','uncertain'])))
with celery_app.connection_for_read() as conn:
 channel=conn.channel()
 counts['broker']=sum(channel.client.llen(queue+suffix) for suffix in ('','\x06\x163','\x06\x166','\x06\x169'))
 channel.close()
print(json.dumps(counts))
'''


def control(name, action, ctx, deadline):
    remaining = min(30, deadline - time.monotonic())
    if remaining <= 0:
        raise RuntimeError('Drain deadline exceeded')
    if name == WORKERS[2]:
        info = json.loads(run(['docker', 'inspect', 'hengxin-lan-' + name]))[0]
        node = 'api-image@' + info['Config']['Hostname']
        out = run(['docker', 'exec', 'hengxin-lan-' + name, 'python', '-B', '-c', CONTROL,
                   'image', action, node], timeout=remaining)
    else:
        side = 'domestic' if name == WORKERS[0] else 'overseas'
        node = ('hx-vps-codex' if side == 'domestic' else 'overseas') + '@hengxin-ai-245'
        out = native_run(ctx[name], code=CONTROL, args=(side, action, node), timeout=remaining)
    return json.loads(out)


def drain(ctx, paused, live=WORKERS):
    # With ingress closed, first let already queued work finish. This ensures
    # rollback/new worker startup cannot immediately consume a hidden backlog.
    deadline = time.monotonic() + 180
    while True:
        states = {n: control(n, 'inspect', ctx, deadline) for n in live}
        if all(not any(v[k] for k in ('active', 'reserved', 'scheduled', 'database', 'broker')) for v in states.values()):
            break
        if time.monotonic() >= deadline:
            raise RuntimeError('Jobs remain; no execution service was stopped')
        time.sleep(2)
    for name in live:
        if name not in paused:
            paused.append(name)
        control(name, 'pause', ctx, deadline)
    for name in live:
        state = control(name, 'inspect', ctx, deadline)
        if state['queues'] or any(state[k] for k in ('active', 'reserved', 'scheduled', 'database', 'broker')):
            raise RuntimeError('Pause/drain race; switch refused')


def gate_accounts(sockets):
    for name in ACCOUNT_SOCKETS:
        path = Path(name)
        info = path.lstat()
        if not stat.S_ISSOCK(info.st_mode):
            raise RuntimeError('Expected credential socket')
        if not any(p == path and inode == info.st_ino for p, inode, _ in sockets):
            sockets.append((path, info.st_ino, stat.S_IMODE(info.st_mode)))
        path.chmod(0)
    deadline = time.monotonic() + 30
    while True:
        idle = True
        for name, expected in (('hengxin-codex-accounts', 4), ('hengxin-codex-auth', 1)):
            pid = int(prop(name, 'MainPID'))
            group = Path('/sys/fs/cgroup') / prop(name, 'ControlGroup').lstrip('/')
            idle &= len(list(Path(f'/proc/{pid}/task').iterdir())) == expected
            idle &= group.joinpath('cgroup.procs').read_text().split() == [str(pid)]
        idle &= all(not any((Path('/home/codex/account-management') / side / 'temporary').iterdir())
                    for side in ('domestic', 'overseas'))
        if idle:
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Authorization still active; switch refused')
        time.sleep(1)


def stop_apps():
    # Runtime masks prohibit automatic restarts while native services are stopped.
    # mask --runtime cannot mask units already defined in /etc, so a temporary
    # drop-in disables Restart and SIGKILL escalation instead.
    for name in NATIVE:
        path = SYSTEMD / (name + '.service.d') / '91-unify-stop.conf'
        write(path, STOP_OVERRIDE, mode=0o644, exclusive=True)
    run(['systemctl', 'daemon-reload'])
    run(['systemctl', 'stop', *NATIVE], timeout=110)
    if any(prop(n, 'MainPID') != '0' for n in NATIVE):
        raise RuntimeError('Native process still active; preserving source')
    app_command('stop', tuple(n for n in APPS if n not in ENTRIES))


def remove_stop_overrides():
    for name in NATIVE:
        path = SYSTEMD / (name + '.service.d') / '91-unify-stop.conf'
        if path.exists():
            if path.read_bytes() != STOP_OVERRIDE:
                raise RuntimeError('Stop override drift')
            path.unlink()
    run(['systemctl', 'daemon-reload'])


def health(ctx, frontend=False):
    deadline = time.monotonic() + 150
    while True:
        try:
            if any(prop(n, 'ActiveState') != 'active' for n in NATIVE):
                raise RuntimeError('Native service not active')
            for n, info in containers().items():
                if n == 'domestic-web' and not frontend:
                    continue
                if not info['State']['Running'] or info['State'].get('Health', {}).get('Status', 'healthy') != 'healthy':
                    raise RuntimeError('Application container not healthy')
            for port, path in ((18008, '/api/v1/health/ready'), (18018, '/api/overseas/v1/health/ready'),
                               (18012, '/api/identity/v1/config')):
                with urllib.request.urlopen(f'http://127.0.0.1:{port}{path}', timeout=min(5, max(.1, deadline-time.monotonic()))) as response:
                    if response.status != 200:
                        raise RuntimeError('HTTP readiness failed')
            states = {n: control(n, 'inspect', ctx, deadline) for n in WORKERS}
            for n, q in zip(WORKERS, ('celery', 'overseas.cli', 'api_image_edits')):
                if states[n]['queues'] != [q]:
                    raise RuntimeError('Consumer queue not restored')
            if frontend:
                with urllib.request.urlopen('http://192.168.1.245:8080/', timeout=5) as response:
                    if response.status != 200:
                        raise RuntimeError('Frontend unavailable')
            return
        except Exception:
            if time.monotonic() >= deadline:
                raise RuntimeError('Application health deadline exceeded') from None
            time.sleep(2)


def start_apps(ctx, after_credentials=None, before_credentials=None):
    remove_stop_overrides()
    if before_credentials is not None:
        before_credentials()
    run(['systemctl', 'start', 'hengxin-codex-accounts', 'hengxin-codex-auth'], timeout=120)
    if after_credentials is not None:
        after_credentials()
    run(['systemctl', 'start', *NATIVE_AUX, *WORKERS[:2]], timeout=180)
    app_command('up', tuple(n for n in APPS if n != 'domestic-web'))
    health(ctx)
    app_command('up', ('domestic-web',))
    health(ctx, frontend=True)


def apply():
    safe(WORK)
    baseline = json.loads((WORK / 'prepared.json').read_bytes())
    if (WORK / 'started.json').exists():
        raise RuntimeError('Existing transaction; inspect recovery state instead of rerunning')
    if validate_release() != baseline['release_manifest']:
        raise RuntimeError('Release differs from prepared candidate')
    if data_identity() != baseline['data_containers']:
        raise RuntimeError('Data container identity drift since prepare')
    for item in baseline['configs']:
        safe(Path(item['path']))
        if digest(Path(item['path']).read_bytes()) != item['sha256']:
            raise RuntimeError('Configuration drift since prepare')
        if digest((WORK / item['backup']).read_bytes()) != item['sha256']:
            raise RuntimeError('Configuration backup drift')
    if digest((WORK / 'compose.candidate.json').read_bytes()) != baseline['candidate']:
        raise RuntimeError('Candidate compose drift')
    for name in NATIVE:
        if digest((WORK / (name + '.conf')).read_bytes()) != baseline['dropins'][name]:
            raise RuntimeError('Candidate drop-in drift')
        for filename in (DROPIN, '91-unify-stop.conf'):
            if (SYSTEMD / (name + '.service.d') / filename).exists():
                raise RuntimeError('Concurrent maintenance drop-in')
    ctx = contexts()
    if {n: {k: v for k, v in c.items() if k != 'env'} for n, c in ctx.items()} != baseline['native']:
        raise RuntimeError('Native execution context drift')
    write(WORK / 'started.json', b'{}\n', exclusive=True)
    paused, sockets, installed, directories = [], [], [], []
    stopped, recovered = False, False
    try:
        # Closing web and all three APIs blocks both edge and loopback writers.
        app_command('stop', ENTRIES)
        drain(ctx, paused)
        gate_accounts(sockets)
        for name in NATIVE:
            directory = SYSTEMD / (name + '.service.d')
            if not directory.exists():
                directory.mkdir(mode=0o755)
                directories.append(directory)
        stopped = True
        stop_apps()
        if validate_release() != baseline['release_manifest']:
            raise RuntimeError('Release drift during drain')
        for item in baseline['configs']:
            if digest(Path(item['path']).read_bytes()) != item['sha256']:
                raise RuntimeError('Configuration drift during drain')
        for name in NATIVE:
            path = SYSTEMD / (name + '.service.d') / DROPIN
            write(path, (WORK / (name + '.conf')).read_bytes(), mode=0o644, exclusive=True)
            installed.append(path)
        write(COMPOSE, (WORK / 'compose.candidate.json').read_bytes())
        start_apps(ctx)
        if validate_release() != baseline['release_manifest']:
            raise RuntimeError('Release drift after start')
        if data_identity() != baseline['data_containers']:
            raise RuntimeError('Data container identity changed')
        write(WORK / 'applied.json', json.dumps({'manifest': baseline['release_manifest']}).encode(), exclusive=True)
        paused.clear()
        recovered = True
        print('APPLIED_UNIFIED_RELEASE', flush=True)
    except BaseException as failure:
        try:
            if stopped:
                # Reclose any partially restored ingress; live workers must drain
                # again before stopping. An uninspectable worker is not force-killed.
                app_command('stop', ENTRIES)
                live = []
                for name in WORKERS[:2]:
                    if prop(name, 'ActiveState') == 'active':
                        live.append(name)
                    elif prop(name, 'MainPID') != '0':
                        raise RuntimeError('Partial native startup is still executing')
                image = json.loads(run(['docker', 'inspect', 'hengxin-lan-' + WORKERS[2]]))[0]
                if image['State']['Running']:
                    live.append(WORKERS[2])
                drain(ctx, paused, live)
                if prop('hengxin-codex-accounts', 'ActiveState') == 'active' and prop('hengxin-codex-auth', 'ActiveState') == 'active':
                    gate_accounts(sockets)
                elif any(prop(n, 'MainPID') != '0' for n in ('hengxin-codex-accounts', 'hengxin-codex-auth')):
                    raise RuntimeError('Partial credential service startup; preserving processes')
                remove_stop_overrides()
                stop_apps()
                for path in installed:
                    if digest(path.read_bytes()) != baseline['dropins'][path.parent.name[:-10]]:
                        raise RuntimeError('Installed drop-in drift')
                    path.unlink()
                record = next(x for x in baseline['configs'] if x['path'] == str(COMPOSE))
                if digest(COMPOSE.read_bytes()) not in (record['sha256'], baseline['candidate']):
                    raise RuntimeError('Concurrent compose modification; preserving configuration')
                write(COMPOSE, (WORK / record['backup']).read_bytes(), record['mode'])
                start_apps(ctx)
                paused.clear()
            else:
                for name in paused:
                    control(name, 'resume', ctx, time.monotonic() + 30)
                paused.clear()
                app_command('up', ENTRIES)
            write(WORK / 'rolled-back.json', b'{}\n', exclusive=True)
            if data_identity() != baseline['data_containers']:
                raise RuntimeError('Data container identity changed during recovery')
            recovered = True
            print('ROLLED_BACK_APPLICATIONS', flush=True)
        except Exception:
            raise RuntimeError('RECOVERY_UNCONFIRMED: ingress remains closed; inspect private transaction') from None
        raise failure
    finally:
        if recovered:
            for path, inode, mode in sockets:
                if path.exists() and path.stat().st_ino == inode:
                    path.chmod(mode)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'prepare', 'apply'))
    args = parser.parse_args()
    if socket.gethostname() != 'hengxin-ai-245' or os.geteuid() != 0:
        raise RuntimeError('Only authorized .245 host/root supported')
    safe(ROOT)
    {'preflight': preflight, 'prepare': prepare, 'apply': apply}[args.action]()


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Deliberately suppress library tracebacks, captured stderr and env data.
        raise SystemExit('UNIFY_REFUSED: ' + (str(exc) if isinstance(exc, RuntimeError) else type(exc).__name__)) from None
