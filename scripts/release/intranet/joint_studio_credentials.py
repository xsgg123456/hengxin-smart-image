"""Recover only dead credential sockets after verified service shutdown."""
import errno
import os
from pathlib import Path
import socket
import stat
import time

import engine

RUNTIME_ROOT = Path('/run')
CGROUP_ROOT = Path('/sys/fs/cgroup')
SERVICES = ('hengxin-codex-accounts', 'hengxin-codex-auth')


def stopped(u, name):
    if u.prop(name, 'ActiveState') not in ('inactive', 'failed') or u.prop(name, 'MainPID') != '0':
        raise RuntimeError('Credential service is not stopped')
    group = u.prop(name, 'ControlGroup')
    if group:
        empty_group(u, group)


def empty_group(u, group):
    if not group.startswith('/') or group == '/' or '..' in Path(group).parts:
        raise RuntimeError('Unexpected service control group')
    path = CGROUP_ROOT / group.lstrip('/')
    if path.exists():
        u.safe(path)
        if (not (path / 'cgroup.procs').is_file()
                or any(item.read_text().split() for item in path.rglob('cgroup.procs'))):
            raise RuntimeError('Service still has live processes')


def parent_fd(path, uid):
    if not path.is_relative_to(RUNTIME_ROOT) or '..' in path.parts:
        raise RuntimeError('Credential socket outside runtime directory')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(RUNTIME_ROOT, flags)
    try:
        info = os.fstat(descriptor)
        if info.st_uid != 0 or stat.S_IMODE(info.st_mode) & 0o022:
            raise RuntimeError('Unsafe credential runtime root')
        for part in path.parent.relative_to(RUNTIME_ROOT).parts:
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            info = os.fstat(descriptor)
            if info.st_uid not in (0, uid) or stat.S_IMODE(info.st_mode) & 0o022:
                raise RuntimeError('Unsafe credential runtime directory')
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def identity(info):
    return info.st_dev, info.st_ino, info.st_uid, info.st_gid, info.st_mode, info.st_nlink


def prepare(u, state):
    original = {name for name, _, mode in state['sockets'] if mode != 0}
    owners = (SERVICES[0],) * 3 + (SERVICES[1],)
    _prepare_owned(u, original, owners, {n: state['ctx'][n]['user'] for n in SERVICES})


def prepare_accounts(u, original, uid):
    """Remove stale account endpoints without touching the independent live broker."""
    if set(original) != set(u.ACCOUNT_SOCKETS[:3]):
        raise RuntimeError('Unexpected original account socket inventory')
    for owner, gid, mode in original.values():
        if owner != uid or type(gid) is not int or gid < 0 or mode != 0o660:
            raise RuntimeError('Unrecognized original account socket identity')
    _prepare_owned(u, original, (SERVICES[0],) * 3, {SERVICES[0]: uid}, account_baseline=original)


def _prepare_owned(u, original, owners, users, account_baseline=None):
    if os.geteuid() != 0 or len(u.ACCOUNT_SOCKETS) != 4:
        raise RuntimeError('Credential recovery requires the known root runtime')
    for name in dict.fromkeys(owners):
        stopped(u, name)
    for name, service in zip(u.ACCOUNT_SOCKETS, owners):
        path = Path(name)
        if name not in original:
            raise RuntimeError('Missing original credential socket record')
        try:
            initial = path.lstat()
        except FileNotFoundError:
            continue  # systemd or the graceful account shutdown removed it.
        uid = users[service]
        modes = (0,)
        if account_baseline is not None:
            _, gid, original_mode = account_baseline[name]
            if initial.st_gid != gid:
                raise RuntimeError('Leftover account socket group differs from baseline')
            modes = (0, original_mode)
        if (not stat.S_ISSOCK(initial.st_mode) or initial.st_uid != uid
                or stat.S_IMODE(initial.st_mode) not in modes or initial.st_nlink != 1):
            raise RuntimeError('Unrecognized leftover credential socket')
        descriptor = parent_fd(path, uid)
        try:
            before = os.stat(path.name, dir_fd=descriptor, follow_symlinks=False)
            if identity(before) != identity(initial):
                raise RuntimeError('Credential socket identity changed')
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as probe:
                probe.settimeout(1)
                try:
                    probe.connect('/proc/self/fd/' + str(descriptor) + '/' + path.name)
                except OSError as error:
                    if error.errno != errno.ECONNREFUSED:
                        raise RuntimeError('Cannot confirm dead credential socket') from None
                else:
                    raise RuntimeError('Credential socket still has a listener')
            stopped(u, service)
            if identity(os.stat(path.name, dir_fd=descriptor, follow_symlinks=False)) != identity(before):
                raise RuntimeError('Credential socket changed during recovery')
            os.unlink(path.name, dir_fd=descriptor)
            os.fsync(descriptor)
        finally:
            os.close(descriptor)


def gate_started(u, state):
    records = engine._JournalList(state, 'sockets')
    deadline = time.monotonic() + 30
    while not all(Path(name).exists() for name in u.ACCOUNT_SOCKETS):
        if time.monotonic() >= deadline:
            raise RuntimeError('Credential sockets did not start')
        time.sleep(.1)
    for name in u.ACCOUNT_SOCKETS:
        path = Path(name)
        info = path.lstat()
        if not stat.S_ISSOCK(info.st_mode) or stat.S_IMODE(info.st_mode) != 0:
            raise RuntimeError('Credential socket was not born gated')
        if not any(p == path and inode == info.st_ino for p, inode, _ in records):
            modes = {mode for p, _, mode in records if p == path and mode != 0}
            if len(modes) != 1:
                raise RuntimeError('Original credential socket mode is ambiguous')
            records.append((path, info.st_ino, modes.pop()))
    u.gate_accounts(records)
