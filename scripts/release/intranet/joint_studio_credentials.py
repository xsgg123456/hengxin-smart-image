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
        if not group.startswith('/') or '..' in Path(group).parts:
            raise RuntimeError('Unexpected credential control group')
        path = CGROUP_ROOT / group.lstrip('/')
        if path.exists():
            u.safe(path)
            if (not (path / 'cgroup.procs').is_file()
                    or any(item.read_text().split() for item in path.rglob('cgroup.procs'))):
                raise RuntimeError('Credential service still has live processes')


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
    if os.geteuid() != 0 or len(u.ACCOUNT_SOCKETS) != 4:
        raise RuntimeError('Credential recovery requires the known root runtime')
    for name in SERVICES:
        stopped(u, name)
    owners = (SERVICES[0], SERVICES[0], SERVICES[0], SERVICES[1])
    for name, service in zip(u.ACCOUNT_SOCKETS, owners):
        path = Path(name)
        if not any(record[0] == name and record[2] != 0 for record in state['sockets']):
            raise RuntimeError('Missing original credential socket record')
        try:
            initial = path.lstat()
        except FileNotFoundError:
            continue  # systemd or the graceful account shutdown removed it.
        uid = state['ctx'][service]['user']
        if (not stat.S_ISSOCK(initial.st_mode) or initial.st_uid != uid
                or stat.S_IMODE(initial.st_mode) != 0 or initial.st_nlink != 1):
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
