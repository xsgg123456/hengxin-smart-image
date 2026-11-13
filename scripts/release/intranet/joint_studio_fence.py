"""Keep recovery behind the migration process and its database transaction."""
from contextlib import contextmanager
import os
from pathlib import Path
import stat
import time


def assert_held(u, descriptor):
    import fcntl
    if type(descriptor) is not int:
        raise RuntimeError('Migration process fence descriptor is invalid')
    current = (Path(u.WORK) / 'domestic-migration.lock').lstat()
    info = os.fstat(descriptor)
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
            or stat.S_IMODE(info.st_mode) != 0o600
            or (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino)):
        raise RuntimeError('Migration process fence is unsafe')
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        raise RuntimeError('Migration process is still running') from None


@contextmanager
def hold(u, timeout=30):
    import fcntl
    root = Path(u.WORK)
    u.safe(root)
    path = root / 'domestic-migration.lock'
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        info, current = os.fstat(descriptor), path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_nlink != 1
                or stat.S_IMODE(info.st_mode) != 0o600
                or (info.st_dev, info.st_ino) != (current.st_dev, current.st_ino)):
            raise RuntimeError('Migration process fence is unsafe')
        deadline = time.monotonic() + timeout
        while True:
            try:
                fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise RuntimeError('Migration process is still running') from None
                time.sleep(.05)
        yield descriptor
    finally:
        # Never explicitly unlock: an inherited descriptor must keep the lock
        # alive if the releasing parent dies while its child is still working.
        os.close(descriptor)


def wait_database(u, ctx):
    """Wait for any earlier migration transaction to commit or roll back."""
    code = ('from app.db.session import get_engine\n'
            'from app.modules.domestic_studio.migration_barrier import acquire\n'
            'with get_engine().begin() as connection:\n'
            '    acquire(connection)\n')
    u.native_run(ctx, code=code, cwd=str(u.RELEASE / 'backend'), timeout=30)
