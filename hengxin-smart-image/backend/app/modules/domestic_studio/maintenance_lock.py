"""Cross-process, per-conversation file fence shared by API and native cleanup."""
from contextlib import contextmanager
import os
from pathlib import Path
import stat
import time
from uuid import UUID

from app.overseas.studio import context_fs as fs
from . import protected as protection

PRODUCTION_ROOT = Path('/var/lib/hengxin-domestic/studio-locks')


@contextmanager
def hold(settings, conversation_id, timeout=30):
    configured = os.environ.get('DOMESTIC_STUDIO_LOCK_ROOT', '').strip()
    production = protection.enabled(settings)
    if production and (not configured or Path(configured) != PRODUCTION_ROOT):
        raise ValueError('Domestic Studio shared lock directory is not configured')
    root = Path(configured) if configured else Path(settings.codex_execution_root).absolute() / 'domestic-studio' / '.maintenance-locks'
    if not root.is_absolute():
        raise ValueError('Shared lock directory must be absolute')
    root = fs.checked(root, directory=True) if production else fs.mkdir(root)
    info = root.stat()
    if production and (info.st_uid != 0 or stat.S_IMODE(info.st_mode) != 0o2770
                       or info.st_gid not in (os.getegid(), *os.getgroups())):
        raise ValueError('Unsafe or inaccessible shared lock directory')
    path = fs.checked(root / (str(UUID(str(conversation_id))) + '.lock'), missing=True, directory=False)
    flags = getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_BINARY', 0)
    try:
        created = os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | flags, 0o660)
    except FileExistsError:
        pass
    else:
        try:
            os.write(created, b'0')
            if os.name == 'posix':
                os.fchmod(created, 0o660)
        finally:
            os.close(created)
    fd = os.open(path, (os.O_RDWR if os.name == 'nt' else os.O_RDONLY) | flags)
    acquired = False
    try:
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or (production and (info.st_gid != root.stat().st_gid or info.st_mode & 0o007))):
            raise ValueError('Unsafe shared conversation lock')
        deadline = time.monotonic() + timeout
        while True:
            try:
                if os.name == 'nt':
                    import msvcrt
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                acquired = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise ValueError('会话文件正在处理，请稍后重试') from None
                time.sleep(.05)
        fs.checked(path, directory=False)
        current = path.stat()
        if (current.st_dev, current.st_ino) != (info.st_dev, info.st_ino):
            raise ValueError('Shared conversation lock changed')
        yield
    finally:
        if acquired:
            if os.name == 'nt':
                import msvcrt
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
