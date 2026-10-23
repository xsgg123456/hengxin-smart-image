"""Secret-safe, worker-only release primitives; no API/container mutation."""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time

WORK = Path('/opt/hengxin-releases/studio-delivery-20261023')
TARGET = Path('/opt/hengxin-overseas-releases/studio-delivery-20261023/backend')
UNIT = 'hengxin-overseas-worker.service'
API = 'hengxin-overseas-api-1'
PG = 'hengxin-overseas-overseas-postgres-1'
DROP = Path('/etc/systemd/system') / (UNIT + '.d') / 'zzzzzzzzz-studio-delivery-20261023.conf'
ALLOWED = frozenset('app/overseas/studio/' + name + '.py' for name in (
    'delivery', 'execution', 'delivery_evidence', 'native_images', 'native_rollout',
    'image_recovery', 'image_recovery_evidence'))
IGNORED = {'.venv', '__pycache__', '.pytest_cache'}


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def safe(path):
    path = Path(path).absolute()
    require(all(not part.is_symlink() for part in (path, *path.parents)), 'Symlink refused')
    return path


def run(*args, timeout=30, **kwargs):
    try:
        result = subprocess.run(args, capture_output=True, text=True, timeout=timeout, **kwargs)
        require(result.returncode == 0, 'Host command failed; inspect recorded phase')
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        raise RuntimeError('Host command timed out; inspect recorded phase') from None


def digest(path):
    return hashlib.sha256(safe(path).read_bytes()).hexdigest()


def private(path, value):
    path = safe(path)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    os.chmod(path, 0o600)
    with os.fdopen(fd, 'w') as out:
        out.write(value if isinstance(value, str) else json.dumps(value, indent=2))


def read(path):
    return json.loads(safe(path).read_text())


def patch(work):
    data = read(work / 'patch.json')
    require(isinstance(data, dict) and set(data) == {'files'}, 'Unexpected manifest fields')
    files = data['files']
    require(isinstance(files, dict) and files and set(files) <= ALLOWED, 'Patch outside allowlist')
    for name, entry in files.items():
        require(isinstance(entry, dict) and set(entry) == {'baseline', 'sha256'}, 'Invalid file manifest')
        for key, value in entry.items():
            require((key == 'baseline' and value is None) or
                    isinstance(value, str) and re.fullmatch('[a-f0-9]{64}', value), 'Invalid hash')
        require(digest(work / 'src/backend' / name) == entry['sha256'], 'Patch checksum mismatch')
    return files


def baseline(root, files):
    for name, entry in files.items():
        path = safe(root / name)
        require((digest(path) if path.is_file() else None) == entry['baseline'], 'Live baseline differs')


def tree(root):
    """Bind every retained file, not only Python files; never follow application links."""
    result = {}
    for directory, dirs, files in os.walk(safe(root), followlinks=False):
        dirs[:] = sorted(name for name in dirs if name not in IGNORED)
        for name in dirs:
            safe(Path(directory) / name)
        for name in sorted(files):
            if name in IGNORED:
                continue
            path = safe(Path(directory) / name)
            require(path.is_file(), 'Nonregular source refused')
            result[path.relative_to(root).as_posix()] = digest(path)
    return result


def arguments(root, argv):
    expected = [str(root / '.venv/bin/python'), str(root / '.venv/bin/celery'),
                '-A', 'app.overseas.execution.worker:celery_app', 'worker', '--pool=prefork',
                '--concurrency=5', '--loglevel=INFO']
    require(argv[:8] == expected and len(argv) == 10 and
            re.fullmatch(r'--hostname=[A-Za-z0-9_.@-]+', argv[8]) and
            argv[9] == '--queues=overseas.cli', 'Unexpected actual worker command')
    return argv


def live(timeout=30):
    deadline = time.monotonic() + timeout
    def query(*args):
        left = deadline - time.monotonic()
        require(left > 0, 'Worker identity deadline exceeded')
        return run('systemctl', *args, timeout=left)
    require(query('is-active', UNIT) == 'active', 'Worker not active')
    pid = int(query('show', UNIT, '-p', 'MainPID', '--value'))
    require(pid > 0, 'Worker PID absent')
    cwd = safe(Path(os.readlink(f'/proc/{pid}/cwd')))
    require(str(cwd) == query('show', UNIT, '-p', 'WorkingDirectory', '--value'),
            'Configured and actual directories differ')
    argv = [os.fsdecode(arg) for arg in Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0') if arg]
    arguments(cwd, argv)
    require(Path(os.readlink(f'/proc/{pid}/exe')).resolve() == (cwd / '.venv/bin/python').resolve(strict=True),
            'Actual Python executable differs from installed dependencies')
    return dict(old=str(cwd), pid=pid, argv=argv)


def ready(live_worker, timeout=15):
    node = live_worker['argv'][8].split('=', 1)[1]
    code = '''import json, sys
import app.overseas.main
from app.overseas.execution.worker import celery_app
node, pid = sys.argv[1], int(sys.argv[2])
inspector = celery_app.control.inspect(destination=[node], timeout=3)
stats = (inspector.stats() or {}).get(node, {})
queues = (inspector.active_queues() or {}).get(node, [])
assert stats.get('pid') == pid
assert stats.get('pool', {}).get('max-concurrency') == 5
assert [q.get('name') for q in queues] == ['overseas.cli']
print('READY')
'''
    require(run('docker', 'exec', '-i', API, 'python', '-', node, str(live_worker['pid']),
                input=code, timeout=timeout) == 'READY', 'Worker readiness unconfirmed')


def dropin(saved):
    old = Path(saved['old'])
    argv = arguments(old, saved['argv'])[:]
    argv[:2] = [str(TARGET / '.venv/bin/python'), str(TARGET / '.venv/bin/celery')]
    require(all(re.fullmatch(r'[A-Za-z0-9_./:@=-]+', arg) for arg in argv), 'Unsafe systemd argument')
    return '[Service]\nWorkingDirectory=' + str(TARGET) + '\nExecStart=\nExecStart=' + ' '.join(argv) + '\n'


def topology():
    ids = run('docker', 'ps', '-aq', '--no-trunc').split()
    containers = json.loads(run('docker', 'inspect', *ids)) if ids else []
    names = sorted(line.split()[0] for line in run('systemctl', 'list-units', '--all',
        '--type=service', '--no-legend', '--plain').splitlines()
        if line.split()[0].startswith('hengxin') and line.split()[0] != UNIT)
    services = {}
    for name in names:
        pid = int(run('systemctl', 'show', name, '-p', 'MainPID', '--value'))
        services[name] = dict(pid=pid, cwd=os.readlink(f'/proc/{pid}/cwd') if pid else None)
    return dict(containers={row['Name']: [row['Id'], row['Image'], row['State']['StartedAt']]
                           for row in containers}, services=services)


def unit():
    return run('systemctl', 'cat', UNIT)


def last_override(original_unit):
    # Include vendor and /run drop-ins shown by systemctl, not only /etc entries.
    names = [Path(line[2:]).name for line in original_unit.splitlines()
             if line.startswith('# /') and line.endswith('.conf')]
    names += [p.name for p in DROP.parent.glob('*.conf')]
    require(all(name < DROP.name for name in names), 'Later override exists')


def gate(action='inspect', paused=None, timeout=30):
    require(action in ('inspect', 'pause', 'resume'), 'Invalid gate action')
    require(action != 'resume' or type(paused) is bool, 'Invalid prior pause state')
    code = '''import json
import app.overseas.main
from sqlalchemy import select, func, text
from app.db.session import session_factory
from app.overseas.execution.queue import lock_gate
from app.overseas.execution.models import Job, ACTIVE
with session_factory().begin() as s:
 s.execute(text("SET LOCAL lock_timeout = '5s'"))
 s.execute(text("SET LOCAL statement_timeout = '10s'"))
 g = lock_gate(s)
 before = bool(g.paused)
 active = s.scalar(select(func.count()).select_from(Job).where(Job.status.in_(ACTIVE)))
 ACTION
 result = dict(before=before, paused=bool(g.paused), active=active)
print(json.dumps(result))
'''
    action_code = {'inspect': 'pass', 'pause': 'g.paused = True',
                   'resume': 'assert before and active == 0; g.paused = ' + repr(paused)}[action]
    return json.loads(run('docker', 'exec', '-i', API, 'python', '-',
                          input=code.replace('ACTION', action_code), timeout=timeout))


def backup(work):
    path = safe(work / 'overseas-before.dump')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'wb') as out:
        result = subprocess.run(['docker', 'exec', PG, 'pg_dump', '-U', 'postgres',
            '-d', 'hengxin_overseas', '-Fc'], stdout=out, stderr=subprocess.PIPE, timeout=300)
    require(result.returncode == 0 and path.stat().st_size > 1000, 'Database backup failed')
    with path.open('rb') as source:
        result = subprocess.run(['docker', 'exec', '-i', PG, 'pg_restore', '--list'],
                                stdin=source, capture_output=True, timeout=60)
    require(result.returncode == 0 and bool(result.stdout), 'Backup archive verification failed')
    private(work / 'backup.json', dict(sha256=digest(path), bytes=path.stat().st_size))
