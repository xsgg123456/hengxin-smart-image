"""Reviewed .245-only repair; no account/configuration edits.
Review dependencies/manifest first; existing transaction directory forbids reruns."""
import hashlib
import json
import os
from pathlib import Path
import socket
import stat
import tempfile
import time
import types

BASE = Path('/opt/hengxin-runtime/runtime-fix-20261111')
HELPER = Path('/opt/hengxin-runtime/codex-upgrade-20261111/upgrade_codex.py')
HELPER_SHA = 'd6e34d3911ba8772021ea7254557bb90f7efb62376df2eca84e76f8ecd6e5b01'
BASELINE_SHA = '823f0d636da8fa0418da0acae02d8e5439ed6c6fcbd1de1ebf7f9068f095d72a'
BACKENDS = (
    Path('/opt/hengxin-native-releases/domestic-record-filters-20261022-2f08f8f/backend'),
    Path('/opt/hengxin-overseas-releases/overseas-20261024-b6289eb/backend'),
)
ACCOUNT_ROOT = Path('/opt/hengxin-account-releases/account-management-20261026-ce4baf4/daemon')
NAMES = ('candidate-workspace.py', 'runtime_check.py', 'office_render.py')
SYSTEMD = Path('/etc/systemd/system')
ACCOUNT_ENV = Path('/etc/hengxin-lan/hengxin-codex-accounts.env')

def digest(data):
    return hashlib.sha256(data).hexdigest()

def secure(path, missing=False):
    """Reject symlink ancestors and writable/unowned deployment paths."""
    for part in (path, *path.parents):
        try:
            info = part.lstat()
        except FileNotFoundError:
            if missing and part == path:
                continue
            raise
        if stat.S_ISLNK(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o022:
            raise RuntimeError('Unsafe ownership/path: ' + str(part))
        if part == path and stat.S_ISREG(info.st_mode) and info.st_nlink != 1:
            raise RuntimeError('Hardlinked deployment file: ' + str(path))
        if part != path and not stat.S_ISDIR(info.st_mode):
            raise RuntimeError('Non-directory ancestor: ' + str(part))

def snapshot(path, missing=False):
    secure(path, missing)
    try:
        info = path.stat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise RuntimeError('Expected regular file: ' + str(path))
    return (path.read_bytes(), stat.S_IMODE(info.st_mode), info.st_gid,
            info.st_dev, info.st_ino)

def unchanged(path, before):
    if snapshot(path, missing=before is None) != before:
        raise RuntimeError('Source/configuration drift: ' + str(path))

def read_candidates():
    manifest = snapshot(BASE / 'candidate-sha256.json')[0]
    hashes = json.loads(manifest)
    if not isinstance(hashes, dict) or set(hashes) != set(NAMES):
        raise RuntimeError('Manifest must contain exactly the reviewed source filenames')
    result = {}
    for name in NAMES:
        data = snapshot(BASE / name)[0]
        if digest(data) != hashes[name]:
            raise RuntimeError('Candidate hash mismatch: ' + name)
        compile(data, name, 'exec')
        result[name] = data
    return manifest, result

def install(path, data, mode, group, exclusive=False, journal=None):
    """Publish a complete inode; an absent target must still be absent."""
    secure(path, missing=exclusive)
    fd, name = tempfile.mkstemp(prefix='.runtime-fix-', dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, 'wb') as stream:
            os.fchown(stream.fileno(), 0, group)
            os.fchmod(stream.fileno(), mode)
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
            info = os.fstat(stream.fileno())
            owned = (data, mode, group, info.st_dev, info.st_ino)
        if exclusive:
            os.link(temporary, path)  # Refuse concurrent creation; never overwrite it.
        else:
            os.replace(temporary, path)
        if journal is not None:
            journal[path] = owned  # Record publication before cleanup can fail.
    finally:
        temporary.unlink(missing_ok=True)
    return snapshot(path)

def drain_live(m, contexts, paused, live):
    """Rollback must also drain the one worker in a partial startup."""
    deadline = time.monotonic() + 180
    for service in live:
        if service not in paused:
            paused.append(service)
        m.control(service, 'pause', contexts, deadline)
    while live:
        states = [m.control(s, 'inspect', contexts, deadline) for s in live]
        if any(s['queues'] for s in states):
            raise RuntimeError('Rollback consumers remain active')
        if all(not any(s[k] for k in ('active', 'reserved', 'scheduled', 'database'))
               for s in states):
            return
        if time.monotonic() >= deadline:
            raise RuntimeError('Rollback jobs remain; services were not stopped')
        time.sleep(min(2, max(0, deadline - time.monotonic())))

def stop_all(m):
    m.run(['systemctl', 'stop', *m.SERVICES], timeout=120)
    for service in m.SERVICES:
        if m.prop(service, 'MainPID') != '0' or m.prop(service, 'ActiveState') not in ('inactive', 'failed'):
            raise RuntimeError('Service not fully stopped: ' + service)

def identity(m, service):
    pid = int(m.prop(service, 'MainPID'))
    fields = dict(line.split(':', 1) for line in Path(f'/proc/{pid}/status').read_text().splitlines()
                  if ':' in line)
    uids, gids = [int(x) for x in fields['Uid'].split()], [int(x) for x in fields['Gid'].split()]
    if len(set(uids)) != 1 or len(set(gids)) != 1 or uids[0] == 0:
        raise RuntimeError('Unexpected execution identity: ' + service)
    return {'user': uids[0], 'group': gids[0],
            'extra_groups': [int(x) for x in fields['Groups'].split()]}

def probes(m, contexts, identities):
    for service, backend in zip(m.WORKERS, BACKENDS):
        cwd, env = contexts[service]
        if cwd != str(backend):
            raise RuntimeError('Unexpected worker working directory: ' + service)
        m.run([str(backend / '.venv/bin/python'), '-B', '-m', 'app.execution.runtime_check'],
              cwd=cwd, env=env, timeout=120, **identities[service])
        print('RUNTIME_PROBE_PASS', service, flush=True)

def restore_files(before, installed):
    for path, owned in reversed(list(installed.items())):
        unchanged(path, owned)  # Never remove or overwrite somebody else's later file.
        old = before[path]
        if old is None:
            path.unlink()
        else:
            install(path, old[0], old[1], old[2])

def restore_access(m, contexts, paused, sockets):
    errors = []
    for path, inode, mode in sockets:
        try:
            if path.exists() and path.stat().st_ino == inode:
                path.chmod(mode)
        except Exception as exc:
            errors.append('socket ' + str(path) + ': ' + str(exc))
    for service in paused:
        try:
            m.control(service, 'resume', contexts)
        except Exception as exc:
            errors.append('consumer ' + service + ': ' + str(exc))
    return errors

def transact(m):
    manifest, sources = read_candidates()
    candidates = {root / 'app/execution' / name: sources[source]
                  for root in (*BACKENDS, ACCOUNT_ROOT)
                  for name, source in (('workspace.py', NAMES[0]), ('office_render.py', NAMES[2]))}
    for service, backend in zip(m.WORKERS, BACKENDS):
        candidates[backend / 'app/execution/runtime_check.py'] = sources[NAMES[1]]
        candidates[SYSTEMD / (service + '.service.d') / '30-runtime-check.conf'] = (
            '[Service]\nExecStartPre=' + str(backend) + '/.venv/bin/python -B -m app.execution.runtime_check\n').encode()
    # No configurable destination paths: manifest entries are hashes only.
    before, directories = {}, []
    for path in candidates:
        if not path.parent.exists():
            # Only our fixed drop-in directory may be absent; creation is deferred until drain.
            if path.name != '30-runtime-check.conf':
                raise RuntimeError('Missing source directory: ' + str(path.parent))
            secure(path.parent.parent)
            directories.append(path.parent)
            before[path] = None
        else:
            before[path] = snapshot(path, missing=True)
        if path.name == 'workspace.py':
            if before[path] is None or digest(before[path][0]) != BASELINE_SHA:
                raise RuntimeError('Workspace source baseline drift: ' + str(path))
            compile(before[path][0], str(path), 'exec')
        elif before[path] is not None:
            raise RuntimeError('Runtime fix already exists; inspect instead of overwriting: ' + str(path))
    configs = {p: snapshot(p) for p in (*m.FILES, ACCOUNT_ENV)}
    contexts = {s: m.context(s) for s in m.WORKERS}
    identities = {s: identity(m, s) for s in m.WORKERS}
    for service in (*m.AUX, m.ACCOUNT):
        m.context(service)
    for service, root in zip(m.WORKERS, BACKENDS):
        if contexts[service][0] != str(root):
            raise RuntimeError('Unexpected active release: ' + service)
    transaction = BASE / 'transaction'
    secure(BASE)
    transaction.mkdir(mode=0o700)
    records = []
    for index, (path, old) in enumerate({**before, **configs}.items()):
        if old is not None:
            install(transaction / str(index), old[0], 0o600, 0, exclusive=True)
        records.append({'path': str(path), 'backup': str(index) if old else None,
                        'sha256': digest(old[0]) if old else None,
                        'mode': old[1] if old else None, 'gid': old[2] if old else None})
    install(transaction / 'paths.json', json.dumps(records).encode(), 0o600, 0, exclusive=True)
    paused, sockets, installed, made_dirs = [], [], {}, []
    stop_attempted = False
    recovered = False
    error = None
    try:
        m.drain(contexts, paused)
        m.gate_account(sockets)
        stop_attempted = True
        stop_all(m)
        if read_candidates() != (manifest, sources):
            raise RuntimeError('Candidate changed during drain')
        for path, old in configs.items():
            unchanged(path, old)
        for directory in directories:
            directory.mkdir(mode=0o755)  # Existing/concurrent directory creation is a failure.
            made_dirs.append(directory)
        for path, old in before.items():
            unchanged(path, old)
        for path, data in candidates.items():
            old = before[path]
            install(path, data, old[1] if old else (0o755 if path.name == 'office_render.py' else 0o644),
                    old[2] if old else 0, exclusive=old is None, journal=installed)
        m.run(['systemctl', 'daemon-reload'])
        probes(m, contexts, identities)
        m.run(['systemctl', 'start', m.ACCOUNT, *m.AUX], timeout=120)
        m.run(['systemctl', 'start', *m.WORKERS], timeout=120)
        states = m.verify(contexts)
        for path, old in configs.items():
            unchanged(path, old)
        for path, own in installed.items():
            unchanged(path, own)
        install(transaction / 'applied.json', json.dumps({'queues': states, 'candidates': json.loads(manifest)}).encode(),
                0o600, 0, exclusive=True)
        paused.clear()
        recovered = True
    except Exception as exc:
        error = exc
        if stop_attempted:
            try:
                # MainPID/activating checks prevent stopping a live but not yet healthy worker.
                live = []
                for service in m.WORKERS:
                    state, pid = m.prop(service, 'ActiveState'), m.prop(service, 'MainPID')
                    if state == 'active':
                        live.append(service)
                    elif pid != '0' or state not in ('inactive', 'failed'):
                        raise RuntimeError('Worker state uncertain; preserving service: ' + service)
                drain_live(m, contexts, paused, live)
                if m.prop(m.ACCOUNT, 'ActiveState') == 'active':
                    m.gate_account(sockets)
                elif m.prop(m.ACCOUNT, 'MainPID') != '0':
                    raise RuntimeError('Account state uncertain; preserving service')
                stop_all(m)
                restore_files(before, installed)
                for directory in reversed(made_dirs):
                    directory.rmdir()  # Empty directories only; never recursive removal.
                m.run(['systemctl', 'daemon-reload'])
                m.run(['systemctl', 'start', m.ACCOUNT, *m.AUX, *m.WORKERS], timeout=120)
                m.verify(contexts)
                paused.clear()
                recovered = True
                print('ROLLED_BACK_RUNTIME', flush=True)
            except Exception as recovery:
                error = RuntimeError('Runtime repair failed: ' + str(exc) + '; RECOVERY_UNCONFIRMED: ' + str(recovery))
        else:
            recovered = True
    if recovered:
        errors = restore_access(m, contexts, paused, sockets)
        if errors:
            error = RuntimeError((str(error) + '; ' if error else '') + 'RESTORE_UNCONFIRMED: ' + '; '.join(errors))
    if error is not None:
        raise error
    print('APPLIED_RUNTIME_FIX', flush=True)

def main():
    if socket.gethostname() != 'hengxin-ai-245' or os.geteuid() != 0:
        raise RuntimeError('Authorized intranet host/root required')
    helper = snapshot(HELPER)[0]
    if digest(helper) != HELPER_SHA:
        raise RuntimeError('Reviewed maintenance helper changed')
    m = types.ModuleType('reviewed_upgrade_codex')
    exec(compile(helper, str(HELPER), 'exec'), m.__dict__)
    if m.run([m.NEW, '--version']).stdout.strip() != 'codex-cli 0.167.1':
        raise RuntimeError('Unexpected Codex runtime version')
    transact(m)

if __name__ == '__main__':
    main()
