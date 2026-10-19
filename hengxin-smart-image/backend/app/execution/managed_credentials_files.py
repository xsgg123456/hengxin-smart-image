"""No-follow credential storage and a bounded, process-wide refresh lock."""
import os
import stat
import time
import uuid
from contextlib import contextmanager
from pathlib import Path


def regular(fd):
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        raise ValueError('unsafe credential file')


class Directory:
    def __init__(self, path, fd):
        self.path, self.fd = path, fd

    def open(self, name, flags, mode=0o600):
        if self.fd is not None:
            result = os.open(name, flags | os.O_NOFOLLOW | os.O_NONBLOCK,
                             mode, dir_fd=self.fd)
        else:
            target = self.path / name
            if target.is_symlink() or (target.exists() and target.is_junction()):
                raise ValueError('unsafe credential file')
            result = os.open(target, flags | os.O_BINARY, mode)
        try:
            regular(result)
        except BaseException:
            os.close(result)
            raise
        return result

    def read(self, name, optional=False):
        try:
            fd = self.open(name, os.O_RDONLY)
        except FileNotFoundError:
            if optional:
                return None
            raise
        with os.fdopen(fd, 'rb') as stream:
            if os.name == 'posix':
                os.fchmod(stream.fileno(), 0o600)
            data = stream.read(131073)
        if len(data) > 131072:
            raise ValueError('credential file too large')
        return data

    def write(self, name, data):
        # Validate existing entries even though replace never follows links.
        self.read(name, optional=True)
        temporary = '.auth-' + uuid.uuid4().hex
        try:
            fd = self.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
            with os.fdopen(fd, 'wb') as stream:
                if os.name == 'posix':
                    os.fchmod(stream.fileno(), 0o600)
                stream.write(data)
                stream.flush()
                os.fsync(stream.fileno())
            if self.fd is not None:
                os.replace(temporary, name, src_dir_fd=self.fd, dst_dir_fd=self.fd)
                os.fsync(self.fd)
            else:
                os.replace(self.path / temporary, self.path / name)
                (self.path / name).chmod(0o600)
        finally:
            try:
                if self.fd is not None:
                    os.unlink(temporary, dir_fd=self.fd)
                else:
                    (self.path / temporary).unlink()
            except FileNotFoundError:
                pass


@contextmanager
def directory(path, create=False):
    path = Path(os.path.abspath(path))
    fd = None
    try:
        if os.name == 'posix':
            fd = os.open(path.anchor, os.O_RDONLY | os.O_DIRECTORY)
            for index, component in enumerate(path.parts[1:]):
                if create and index == len(path.parts) - 2:
                    try:
                        os.mkdir(component, mode=0o700, dir_fd=fd)
                    except FileExistsError:
                        pass
                child = os.open(component, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW,
                                dir_fd=fd)
                os.close(fd)
                fd = child
        else:
            for item in reversed([path, *path.parents]):
                if item.is_symlink() or (item.exists() and item.is_junction()):
                    raise ValueError('unsafe credential directory')
            if create:
                path.mkdir(mode=0o700, exist_ok=True)
            if not path.is_dir():
                raise ValueError('missing credential directory')
        yield Directory(path, fd)
    finally:
        if fd is not None:
            os.close(fd)


@contextmanager
def refresh_lock(folder, name, timeout=35):
    fd = folder.open(name, os.O_RDWR | os.O_CREAT)
    acquired = False
    deadline = time.monotonic() + timeout
    try:
        if os.name == 'posix':
            import fcntl
            os.fchmod(fd, 0o600)
            lock = lambda: fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            unlock = lambda: fcntl.flock(fd, fcntl.LOCK_UN)
        else:
            import msvcrt
            if os.fstat(fd).st_size == 0:
                os.write(fd, b'\0')
            os.lseek(fd, 0, os.SEEK_SET)
            lock = lambda: msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
            unlock = lambda: msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        while True:
            try:
                lock()
                acquired = True
                break
            except OSError:
                if time.monotonic() >= deadline:
                    raise TimeoutError('credential lock timeout') from None
                time.sleep(0.05)
        yield
    finally:
        if acquired:
            unlock()
        os.close(fd)
