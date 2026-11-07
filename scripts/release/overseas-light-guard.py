"""Protect publication directories against concurrent non-owner replacement."""
import importlib.util
import json
from contextlib import contextmanager
import os
from pathlib import Path
import signal
import stat
from uuid import uuid4


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


r = load('overseas-light-runtime').r
_active = {}


def open_directory(path):
    """On POSIX, walk each component without following symbolic links."""
    r.require(path.is_absolute() and '..' not in path.parts, 'Unsafe directory path')
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(path.anchor, flags)
    try:
        for part in path.parts[1:]:
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        return descriptor
    except BaseException:
        os.close(descriptor)
        raise


def trusted_directory(descriptor, *, sticky=False):
    value = os.fstat(descriptor)
    mode = stat.S_IMODE(value.st_mode)
    r.require(value.st_uid == 0 and stat.S_ISDIR(value.st_mode) and
              (not mode & 0o022 or sticky and bool(mode & stat.S_ISVTX)), 'Writable or unowned directory')
    return value


def trusted_ancestors(path):
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    descriptor = os.open(path.anchor, flags)
    try:
        trusted_directory(descriptor, sticky=True)
        for part in path.parts[1:]:
            child = os.open(part, flags, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
            trusted_directory(descriptor, sticky=True)
    finally:
        os.close(descriptor)


@contextmanager
def publication_lock(app):
    """Serialize every publication and retain unfinished permission evidence."""
    import fcntl
    trusted_ancestors(app.parent)
    parent = open_directory(app.parent)
    descriptor = None
    try:
        descriptor = os.open('.hengxin-overseas-light.lock', os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW,
                             0o600, dir_fd=parent)
        value = os.fstat(descriptor)
        r.require(stat.S_ISREG(value.st_mode) and value.st_uid == 0 and
                  not stat.S_IMODE(value.st_mode) & 0o022, 'Unsafe publication lock')
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield descriptor, parent
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(parent)


def private_json(parent, name, value, *, exclusive=False):
    """Write a complete private record before making its name visible."""
    temporary = '.' + name + '.' + uuid4().hex + '.new'
    created = False
    try:
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                             0o600, dir_fd=parent)
        created = True
        with os.fdopen(descriptor, 'w') as stream:
            json.dump(value, stream)
            stream.flush()
            os.fsync(stream.fileno())
        if exclusive:
            os.link(temporary, name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
        else:
            os.replace(temporary, name, src_dir_fd=parent, dst_dir_fd=parent)
            created = False
        os.fsync(parent)
    finally:
        if created:
            os.unlink(temporary, dir_fd=parent)


def private_receipt(work, name, value):
    parent = open_directory(work)
    try:
        trusted_directory(parent)
        private_json(parent, name, value)
    finally:
        os.close(parent)


def read_pending(lock):
    parent = lock[1]
    try:
        descriptor = os.open('.hengxin-overseas-light.pending', os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                             dir_fd=parent)
    except FileNotFoundError:
        return None
    with os.fdopen(descriptor, 'rb') as stream:
        value = os.fstat(stream.fileno())
        r.require(stat.S_ISREG(value.st_mode) and value.st_uid == 0 and
                  not stat.S_IMODE(value.st_mode) & 0o022, 'Unsafe pending publication')
        raw = stream.read(65537)
        r.require(len(raw) <= 65536, 'Invalid publication lock state')
        return json.loads(raw)


def write_pending(lock, value):
    parent = lock[1]
    if value is None:
        os.unlink('.hengxin-overseas-light.pending', dir_fd=parent)
        os.fsync(parent)
    else:
        private_json(parent, '.hengxin-overseas-light.pending', value, exclusive=True)


def restore_permissions(descriptors, entries):
    for descriptor, entry in zip(descriptors, entries):
        value = os.fstat(descriptor)
        r.require(value.st_uid == 0 and stat.S_ISDIR(value.st_mode) and
                  (value.st_dev, value.st_ino) == (entry['device'], entry['inode']),
                  'Publication directory identity changed')
    for descriptor, entry in reversed(list(zip(descriptors, entries))):
        os.fchmod(descriptor, entry['mode'])
        r.require(stat.S_IMODE(os.fstat(descriptor).st_mode) == entry['mode'], 'Directory mode restore failed')


def recover_publication_directories(app, work):
    """Restore an interrupted release only when its recorded inodes still match."""
    r.require(os.name == 'posix' and os.geteuid() == 0, 'Root required for permission recovery')
    trusted_ancestors(work)
    with publication_lock(app) as lock:
        pending = read_pending(lock)
        r.require(pending is not None and pending.get('work') == str(work), 'No matching interrupted publication')
        receipt = json.loads((work / 'FRONTEND_PERMISSIONS.json').read_text())
        r.require(receipt.get('id') == pending.get('id') and len(receipt.get('directories', [])) == 2,
                  'Permission receipt mismatch')
        entries = receipt['directories']
        r.require([entry['path'] for entry in entries] == [str(app), str(app / 'frontend')] and
                  all(type(entry['mode']) is int and 0 <= entry['mode'] <= 0o7777 for entry in entries),
                  'Unsafe permission receipt')
        descriptors = []
        try:
            descriptors.append(open_directory(app))
            descriptors.append(open_directory(app / 'frontend'))
            restore_permissions(descriptors, entries)
            private_receipt(work, 'FRONTEND_PERMISSIONS_RESTORED.json', {'id': receipt['id'], 'restored': True})
            write_pending(lock, None)
        finally:
            for descriptor in reversed(descriptors):
                os.close(descriptor)


@contextmanager
def protect_publication_directories(app, work):
    """Temporarily restrict write access, under a cross-process publication lock."""
    if os.name != 'posix':
        yield
        return
    r.require(os.geteuid() == 0, 'Root required for protected publication')
    trusted_ancestors(work)
    with publication_lock(app) as lock:
        r.require(read_pending(lock) is None, 'Unfinished publication permissions require recovery')
        r.require(not (work / 'FRONTEND_PERMISSIONS.json').exists() and
                  not (work / 'FRONTEND_PERMISSIONS_RESTORED.json').exists(), 'Existing permission receipt')
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        parent = open_directory(app.parent)
        descriptors, previous, entries, recorded, registered = [], {}, [], False, False
        def interrupted(signum, _frame):
            raise SystemExit('Publication interrupted: ' + str(signum))
        try:
            app_fd = os.open(app.name, flags, dir_fd=parent)
            descriptors.append(app_fd)
            front_fd = os.open('frontend', flags, dir_fd=app_fd)
            descriptors.append(front_fd)
            values = [os.fstat(app_fd), os.fstat(front_fd)]
            r.require(all(value.st_uid == 0 and stat.S_ISDIR(value.st_mode) for value in values),
                      'Unowned publication directory')
            entries = [{'path': str(path), 'device': value.st_dev, 'inode': value.st_ino,
                        'mode': stat.S_IMODE(value.st_mode)} for path, value in zip((app, app / 'frontend'), values)]
            receipt = {'id': uuid4().hex, 'directories': entries}
            private_receipt(work, 'FRONTEND_PERMISSIONS.json', receipt)
            write_pending(lock, {'id': receipt['id'], 'work': str(work)})
            recorded = True
            for item in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM, signal.SIGQUIT):
                previous[item] = signal.signal(item, interrupted)
            os.fchmod(app_fd, entries[0]['mode'] & ~0o022)
            current_app = os.stat(app.name, dir_fd=parent, follow_symlinks=False)
            r.require(stat.S_ISDIR(current_app.st_mode) and (current_app.st_dev, current_app.st_ino) ==
                      (values[0].st_dev, values[0].st_ino), 'Application directory changed while locking')
            current = os.stat('frontend', dir_fd=app_fd, follow_symlinks=False)
            r.require(stat.S_ISDIR(current.st_mode) and (current.st_dev, current.st_ino) ==
                      (values[1].st_dev, values[1].st_ino), 'Frontend directory changed while locking')
            os.fchmod(front_fd, entries[1]['mode'] & ~0o022)
            key = str(app)
            r.require(key not in _active, 'Publication already protected')
            _active[key] = (app_fd, front_fd)
            registered = True
            yield
        finally:
            if registered:
                del _active[str(app)]
            try:
                if recorded:
                    restore_permissions(descriptors, entries)
                    private_receipt(work, 'FRONTEND_PERMISSIONS_RESTORED.json', {'id': receipt['id'], 'restored': True})
                    write_pending(lock, None)
            finally:
                for item, handler in previous.items():
                    signal.signal(item, handler)
                for descriptor in reversed(descriptors):
                    os.close(descriptor)
                os.close(parent)


def require_protected(app):
    if os.name != 'posix':
        return
    descriptors = _active.get(str(app))
    r.require(descriptors is not None, 'Publication directories are not protected')
    for descriptor in descriptors:
        trusted_directory(descriptor)
