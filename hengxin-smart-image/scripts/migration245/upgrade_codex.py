"""Explicit .245-only runtime switch; run as root after side-by-side installation."""
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import time

OLD = '/opt/hengxin-runtime/codex-0.162.1/codex'
NEW = '/opt/hengxin-runtime/codex-0.167.1/bin/codex'
ROOT = Path('/opt/hengxin-runtime/codex-upgrade-20261111/switch')
WORKERS = ('hengxin-vps-codex-worker', 'hengxin-overseas-worker')
AUX = ('hengxin-retention', 'hengxin-domestic-deletions', 'hengxin-overseas-outbox')
ACCOUNT = 'hengxin-codex-accounts'
SERVICES = (*WORKERS, *AUX, ACCOUNT)
FILES = [Path('/etc/hengxin-lan') / (s + '.env') for s in (*WORKERS, *AUX)] + [
    Path('/etc/systemd/system/hengxin-codex-accounts.service'),
    Path('/etc/hengxin-lan/hengxin-codex-accounts.service'),
    Path('/opt/hengxin-lan/native-env.json')]

CONTROL = r'''
import json,sys
from sqlalchemy import func,select
side,action,node=sys.argv[1:]
if side=='domestic':
 from app.worker.celery_app import celery_app
 from app.db.session import session_factory
 from app.models import Job
else:
 from app.overseas.execution.worker import celery_app
 from app.overseas.db import session_factory
 from app.overseas.execution.models import Job
c=celery_app.control
def inspect(method):
 x=getattr(c.inspect(destination=[node],timeout=4),method)()
 if not isinstance(x,dict) or node not in x or not isinstance(x[node],list):
  raise RuntimeError('Worker inspection unavailable')
 return x[node]
queue='celery' if side=='domestic' else 'overseas.cli'
if action in ('pause','resume'):
 result=getattr(c,'cancel_consumer' if action=='pause' else 'add_consumer')(
  queue,destination=[node],reply=True,timeout=4)
 if not result or not any(isinstance(r.get(node),dict) and 'ok' in r[node] for r in result):
  raise RuntimeError('Consumer control unconfirmed')
queues=[r['name'] for r in inspect('active_queues')]
if action=='resume' and queues != [queue]:
 raise RuntimeError('Consumer restoration unconfirmed')
counts={k:len(inspect(k)) for k in ('active','reserved','scheduled')}
with session_factory()() as db:
 counts['database']=db.scalar(select(func.count()).select_from(Job).where(
  Job.status.in_(['running','collecting','cancelling','uncertain'])))
print(json.dumps({'queues':queues,**counts}))
'''


def run(args, **kwargs):
    return subprocess.run(args, check=True, capture_output=True, text=True,
                          timeout=kwargs.pop('timeout', 40), **kwargs)


def prop(service, key):
    return run(['systemctl', 'show', service, '-p', key, '--value']).stdout.strip()


def context(service):
    pid = int(prop(service, 'MainPID'))
    if pid <= 1 or prop(service, 'ActiveState') != 'active':
        raise RuntimeError('Expected active service: ' + service)
    env = dict(x.split('=', 1) for x in Path(f'/proc/{pid}/environ').read_bytes().decode().split('\0')
               if '=' in x)
    return prop(service, 'WorkingDirectory'), env


def control(service, action, contexts, deadline=None):
    cwd, env = contexts[service]
    side, node = (('domestic', 'hx-vps-codex@hengxin-ai-245') if service == WORKERS[0]
                  else ('overseas', 'overseas@hengxin-ai-245'))
    remaining = 35 if deadline is None else min(35, deadline - time.monotonic())
    if remaining <= 0:
        raise TimeoutError('Maintenance deadline exceeded')
    result = run([cwd + '/.venv/bin/python', '-B', '-c', CONTROL, side, action, node],
                 env=env, cwd=cwd, timeout=remaining)
    return json.loads(result.stdout)


def drain(contexts, paused):
    deadline = time.monotonic() + 180
    for service in WORKERS:
        if service not in paused:
            paused.append(service)  # Restore even if acknowledgment is lost.
        control(service, 'pause', contexts, deadline)
    while True:
        states = {s: control(s, 'inspect', contexts, deadline) for s in WORKERS}
        print('DRAIN', json.dumps(states), flush=True)
        if any(v['queues'] for v in states.values()):
            raise RuntimeError('Consumer still active')
        if all(not any(v[k] for k in ('active', 'reserved', 'scheduled', 'database'))
               for v in states.values()):
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Jobs remain; switch refused')
        time.sleep(min(3, max(0, deadline - time.monotonic())))


def gate_account(sockets):
    for name in ('domestic/control.sock', 'overseas/control.sock', 'worker.sock'):
        path = Path('/run/hengxin-codex-accounts') / name
        info = path.stat()
        if not any(p == path and inode == info.st_ino for p, inode, _ in sockets):
            sockets.append((path, info.st_ino, info.st_mode & 0o777))
        path.chmod(0)
    time.sleep(6)  # Existing bounded request readers finish before checking threads.
    account_idle()


def account_idle():
    pid = int(prop(ACCOUNT, 'MainPID'))
    # Main + three socket acceptors; request/check/login threads must have ended.
    if len(list(Path(f'/proc/{pid}/task').iterdir())) != 4:
        raise RuntimeError('Account requests still active')
    for side in ('domestic', 'overseas'):
        if any((Path('/home/codex/account-management') / side / 'temporary').iterdir()):
            raise RuntimeError('Account authorization still pending')
    group = Path('/sys/fs/cgroup') / prop(ACCOUNT, 'ControlGroup').lstrip('/')
    if group.joinpath('cgroup.procs').read_text().split() != [str(pid)]:
        raise RuntimeError('Account child process still active')


def atomic(path, data, mode):
    temporary = path.with_name(path.name + '.codex-upgrade')
    with temporary.open('xb') as f:
        os.fchmod(f.fileno(), mode)
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporary, path)


def verify(contexts):
    for service in SERVICES:
        if prop(service, 'ActiveState') != 'active':
            raise RuntimeError('Service inactive: ' + service)
    for service in (*WORKERS, *AUX):
        _, env = context(service)
        prefix = 'OVERSEAS_' if 'overseas' in service else ''
        if env[prefix + 'CODEX_BINARY'] != NEW or env[prefix + 'CODEX_VERSION'] != '0.167.1':
            raise RuntimeError('Running environment mismatch')
    pid = prop(ACCOUNT, 'MainPID')
    if NEW.encode() not in Path(f'/proc/{pid}/cmdline').read_bytes().split(b'\0'):
        raise RuntimeError('Account runtime mismatch')
    deadline = time.monotonic() + 60
    while True:
        try:
            states = {s: control(s, 'inspect', contexts, deadline) for s in WORKERS}
            if states[WORKERS[0]]['queues'] == ['celery'] and states[WORKERS[1]]['queues'] == ['overseas.cli']:
                return states
        except (subprocess.SubprocessError, ValueError):
            pass
        if time.monotonic() >= deadline:
            raise RuntimeError('Worker queue restoration unconfirmed')
        time.sleep(min(2, max(0, deadline - time.monotonic())))


def main():
    if socket.gethostname() != 'hengxin-ai-245' or os.geteuid() != 0:
        raise RuntimeError('Only the authorized intranet host is permitted')
    if run([NEW, '--version']).stdout.strip() != 'codex-cli 0.167.1':
        raise RuntimeError('Unexpected installed version')
    ROOT.mkdir(mode=0o700)  # Deliberately refuse rerunning an existing transaction.
    contexts = {s: context(s) for s in WORKERS}
    before, candidates = {}, {}
    for index, path in enumerate(FILES):
        if path.is_symlink() or path.stat().st_uid != 0:
            raise RuntimeError('Unsafe configuration path')
        data = path.read_bytes()
        if OLD.encode() not in data:
            raise RuntimeError('Configuration baseline drift: ' + str(path))
        before[path] = (data, path.stat().st_mode & 0o777)
        candidates[path] = data.replace(OLD.encode(), NEW.encode()).replace(b'0.162.1', b'0.167.1')
        atomic(ROOT / str(index), data, 0o600)
    (ROOT / 'paths.json').write_text(json.dumps([str(p) for p in FILES]))
    paused, sockets, changed, stopped = [], [], False, False
    try:
        drain(contexts, paused)
        gate_account(sockets)
        for service in AUX:
            context(service)
        stopped = True  # Partial stop failures also need restoration.
        run(['systemctl', 'stop', *SERVICES], timeout=120)
        for service in SERVICES:
            if prop(service, 'MainPID') != '0':
                raise RuntimeError('Service not fully stopped')
        for path, (data, mode) in before.items():
            if path.read_bytes() != data:
                raise RuntimeError('Configuration changed during drain')
        changed = True
        for path, (_, mode) in before.items():
            atomic(path, candidates[path], mode)
        run(['systemctl', 'daemon-reload'])
        run(['systemctl', 'start', ACCOUNT, *AUX], timeout=120)
        run(['systemctl', 'start', *WORKERS], timeout=120)
        states = verify(contexts)
        (ROOT / 'applied.json').write_text(json.dumps({'version': '0.167.1', 'queues': states}))
        paused.clear()
        print('APPLIED 0.167.1', flush=True)
    except Exception:
        if stopped:
            # If new workers became live, drain them again before any rollback stop.
            if changed and all(prop(s, 'ActiveState') == 'active' for s in WORKERS):
                drain(contexts, paused)
            elif changed and any(prop(s, 'ActiveState') == 'active' for s in WORKERS):
                raise RuntimeError('Partial worker start; preserved state for manual safe recovery') from None
            if prop(ACCOUNT, 'ActiveState') == 'active':
                gate_account(sockets)  # New authorization may have arrived after startup.
            run(['systemctl', 'stop', *SERVICES], timeout=120)
            for path, (data, mode) in before.items():
                atomic(path, data, mode)
            run(['systemctl', 'daemon-reload'])
            run(['systemctl', 'start', ACCOUNT, *AUX, *WORKERS], timeout=120)
            print('ROLLED_BACK', flush=True)
        raise
    finally:
        errors = []
        for path, inode, mode in sockets:
            try:
                if path.exists() and path.stat().st_ino == inode:
                    path.chmod(mode)
            except OSError:
                errors.append('socket ' + str(path))
        for service in paused:
            try:
                control(service, 'resume', contexts)
            except Exception:
                errors.append('consumer ' + service)
        if errors:
            print('RESTORE_UNCONFIRMED', json.dumps(errors), flush=True)
            if sys.exc_info()[0] is None:
                raise RuntimeError('Maintenance restoration incomplete')


if __name__ == '__main__':
    main()
