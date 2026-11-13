"""Provision only the reviewed domestic Studio host paths, without touching data."""
import os
from pathlib import Path
import stat

import domestic_studio_wiring as wiring

ROOT = Path('/var/lib/hengxin-domestic')
RELEASE_GATE = ROOT / 'release-gate'
SOCKET_DIR = Path(wiring.SOCKET_DIR)
TMPFILES = Path('/etc/tmpfiles.d/hengxin-domestic-studio.conf')
TMPFILES_CONTENT = b'd /run/hengxin-domestic-skill-publisher 0750 root 10001 -\n'


def sync_directory(path):
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def gate_state(u, name, root=RELEASE_GATE):
    if name not in ('workers', 'ingress'):
        raise RuntimeError('Unknown release gate')
    root = Path(root)
    u.safe(root)
    info = root.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
            or stat.S_IMODE(info.st_mode) != 0o755):
        raise RuntimeError('Release gate directory identity differs')
    marker = root / name
    u.safe(marker)
    info = marker.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_gid != 0
            or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) != 0o644 or info.st_size > 16):
        raise RuntimeError('Release gate marker identity differs')
    value = marker.read_bytes()
    if value not in (b'open\n', b'closed\n'):
        raise RuntimeError('Unknown release gate state')
    return value == b'open\n'


def set_gate(u, name, opened, root=RELEASE_GATE):
    gate_state(u, name, root)
    u.write(Path(root) / name, b'open\n' if opened else b'closed\n', mode=0o644)
    sync_directory(root)
    if gate_state(u, name, root) is not opened:
        raise RuntimeError('Release gate state did not persist')


def directory(u, path, uid, gid, mode):
    """Refuse links, unexpected owners or modes; never correct an existing path."""
    path = Path(path)
    u.safe(path.parent)
    try:
        info = path.lstat()
    except FileNotFoundError:
        path.mkdir(mode=0o700)
        os.chown(path, uid, gid)
        os.chmod(path, mode)
        info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != uid or info.st_gid != gid
            or stat.S_IMODE(info.st_mode) != mode):
        raise RuntimeError('Unexpected domestic Studio directory identity: ' + str(path))
    return path


def identities(ctx):
    for name in ('hengxin-vps-codex-worker', 'hengxin-domestic-deletions'):
        service = ctx.get(name, {})
        if (not isinstance(service.get('user'), int) or service['user'] == 0
                or 986 not in [service.get('group'), *service.get('extra_groups', [])]):
            raise RuntimeError('Domestic native service cannot share the Studio lock: ' + name)


def provision(u, root=ROOT, socket_dir=SOCKET_DIR, tmpfiles=TMPFILES, initial=True):
    root, socket_dir, tmpfiles = Path(root), Path(socket_dir), Path(tmpfiles)
    directory(u, root, 0, 0, 0o755)
    skills = directory(u, root / 'local-skills', 0, 0, 0o755)
    directory(u, root / 'skill-transfers', 0, 0, 0o700)
    directory(u, root / 'studio-locks', 0, 986, 0o2770)
    gate = directory(u, root / 'release-gate', 0, 0, 0o755)
    for name in ('workers', 'ingress'):
        marker = gate / name
        if marker.exists() or marker.is_symlink():
            u.safe(marker)
            if stat.S_IMODE(marker.stat().st_mode) != 0o644 or marker.read_bytes() != b'closed\n':
                raise RuntimeError('Unexpected release gate state')
        else:
            u.write(marker, b'closed\n', mode=0o644, exclusive=True)
    sync_directory(gate)
    directory(u, socket_dir, 0, 10001, 0o750)
    if initial and any(skills.iterdir()):
        raise RuntimeError('Unrecognized existing domestic Skill data')
    u.safe(tmpfiles.parent)
    if tmpfiles.exists() or tmpfiles.is_symlink():
        u.safe(tmpfiles)
        if tmpfiles.read_bytes() != TMPFILES_CONTENT or stat.S_IMODE(tmpfiles.stat().st_mode) != 0o644:
            raise RuntimeError('Domestic Studio boot configuration differs')
    else:
        u.write(tmpfiles, TMPFILES_CONTENT, mode=0o644, exclusive=True)
