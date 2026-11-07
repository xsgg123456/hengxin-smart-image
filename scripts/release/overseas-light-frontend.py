"""Install only this release's static files, retaining unrelated assets and directories."""
import importlib.util
import hashlib
import json
import os
from pathlib import Path
import stat
from uuid import uuid4


def load(name):
    spec = importlib.util.spec_from_file_location(name.replace('-', '_'), Path(__file__).with_name(name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


r = load('overseas-light-runtime').r
frontend = load('sku-frontend')
frontend.r = r; frontend.BASE_VERSION = '0.2.66'
BACKUP_FILES = {name: f'{index:02d}.backup' for index, name in enumerate(frontend.ENTRIES)}


guard = load('overseas-light-guard')
guard.r = r
open_directory = guard.open_directory
trusted_directory = guard.trusted_directory
protect_publication_directories = guard.protect_publication_directories


def read_regular(path):
    if os.name != 'posix':
        r.require(not any(p.is_symlink() for p in (path, *path.parents)) and path.is_file(), 'Unsafe static file')
        return path.read_bytes()
    parent = open_directory(path.parent)
    try:
        descriptor = os.open(path.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
        with os.fdopen(descriptor, 'rb') as stream:
            r.require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode), 'Unsafe static file')
            return stream.read()
    finally:
        os.close(parent)


def digest_regular(path): return hashlib.sha256(read_regular(path)).hexdigest()


def unlink_regular(path):
    if os.name != 'posix':
        r.require(not any(p.is_symlink() for p in (path, *path.parents)), 'Linked static destination')
        path.unlink(missing_ok=True)
        return
    parent = open_directory(path.parent)
    try:
        try:
            value = os.stat(path.name, dir_fd=parent, follow_symlinks=False)
        except FileNotFoundError:
            return
        r.require(stat.S_ISREG(value.st_mode), 'Unsafe static destination')
        os.unlink(path.name, dir_fd=parent)
    finally:
        os.close(parent)


def atomic_frontend_copy(source, destination, *, exclusive=False):
    r.require(not any(p.is_symlink() for p in (destination, *destination.parents)), 'Linked static destination')
    body = read_regular(source)
    name = destination.name + '.overseas-light-' + uuid4().hex
    if os.name == 'posix':
        parent = open_directory(destination.parent)
        created = False
        try:
            try:
                current = os.stat(destination.name, dir_fd=parent, follow_symlinks=False)
                r.require(stat.S_ISREG(current.st_mode), 'Unsafe static destination')
            except FileNotFoundError:
                pass
            descriptor = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=parent)
            created = True
            with os.fdopen(descriptor, 'wb') as stream:
                stream.write(body)
                os.fchmod(stream.fileno(), 0o644)
            if exclusive:
                try:
                    os.link(name, destination.name, src_dir_fd=parent, dst_dir_fd=parent, follow_symlinks=False)
                except FileExistsError:
                    existing = os.open(destination.name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=parent)
                    with os.fdopen(existing, 'rb') as stream:
                        r.require(stat.S_ISREG(os.fstat(stream.fileno()).st_mode) and stream.read() == body,
                                  'Existing shared asset collision')
            else:
                os.replace(name, destination.name, src_dir_fd=parent, dst_dir_fd=parent)
                created = False
        finally:
            if created:
                os.unlink(name, dir_fd=parent)
            os.close(parent)
        return
    temporary = destination.with_name(name)
    created = False
    try:
        with temporary.open('xb') as stream:
            created = True
            stream.write(body)
        temporary.chmod(0o644)
        r.require(not any(p.is_symlink() for p in (destination, *destination.parents)), 'Linked static destination')
        if exclusive:
            try:
                os.link(temporary, destination)
            except FileExistsError:
                r.require(read_regular(destination) == body, 'Existing shared asset collision')
        else:
            os.replace(temporary, destination)
    finally:
        if created:
            temporary.unlink(missing_ok=True)


frontend.atomic_copy = atomic_frontend_copy


def check_frontend_collisions(source, app):
    dist, target = source / 'frontend/dist', app / 'frontend/dist'
    r.require(target.is_dir() and not any(p.is_symlink() for p in (target, *target.parents)),
              'Unsafe frontend directory')
    if os.name == 'posix':
        require_asset_directory(target, target)
    for name in ('frontend/dist/index.html', 'frontend/dist/index.html.gz',
                 'frontend/package.json', 'FRONTEND_RELEASE.json'):
        destination = app / name
        r.require(not any(p.is_symlink() for p in (destination, *destination.parents)) and
                  (not destination.exists() or destination.is_file()), 'Unsafe frontend entry: ' + name)
    checked = set()
    for path in dist.rglob('*'):
        if not path.is_file() or path.name in ('index.html', 'index.html.gz'):
            continue
        destination = target / path.relative_to(dist)
        parent = destination.parent
        while parent != target:
            r.require(not parent.is_symlink() and parent.is_dir(),
                      'Unsafe shared asset directory: ' + parent.relative_to(target).as_posix())
            parent = parent.parent
        if os.name == 'posix' and destination.parent not in checked:
            require_asset_directory(target, destination.parent)
            checked.add(destination.parent)
        r.require(not destination.is_symlink(), 'Linked shared asset: ' + path.relative_to(dist).as_posix())
        r.require(not destination.exists() or destination.is_file() and digest_regular(destination) == digest_regular(path),
                  'Existing shared asset collision: ' + path.relative_to(dist).as_posix())


def require_asset_directory(root, directory):
    r.require(root.is_dir() and not any(p.is_symlink() for p in (root, *root.parents)), 'Unsafe frontend directory')
    relative = directory.relative_to(root); r.require('..' not in relative.parts, 'Unsafe asset directory')
    if os.name == 'posix':
        flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        descriptor = open_directory(root)
        try:
            trusted_directory(descriptor)
            for part in relative.parts:
                child = os.open(part, flags, dir_fd=descriptor)
                try:
                    trusted_directory(child)
                except BaseException:
                    os.close(child)
                    raise
                os.close(descriptor)
                descriptor = child
        finally:
            os.close(descriptor)
        return
    current = root
    for part in relative.parts:
        current = current / part
        r.require(not current.is_symlink() and current.is_dir(), 'Unsafe asset directory')


def install_frontend(source, app, backup):
    guard.require_protected(app)
    manifest = r.verify_package(source)
    r.require(json.loads((app / 'frontend/package.json').read_text())['version'] == frontend.BASE_VERSION,
              'Frontend baseline changed')
    check_frontend_collisions(source, app)
    source_dist, target_dist = source / 'frontend/dist', app / 'frontend/dist'
    backup.mkdir(mode=0o700, exist_ok=False)
    saved = {}
    for name in frontend.ENTRIES:
        path = app / name
        if path.exists():
            target = backup / BACKUP_FILES[name]
            atomic_frontend_copy(path, target, exclusive=True)
            saved[name] = digest_regular(target)
            r.require(saved[name] == digest_regular(path), 'Frontend backup checksum mismatch')
    planned = {name: r.digest(source / name) if (source / name).is_file() else None for name in frontend.ENTRIES}
    planned['FRONTEND_RELEASE.json'] = r.digest(source / 'release.json')
    r.private(backup / 'COMPLETE.json', {'saved': saved, 'planned': planned, 'manifest': r.digest(source / 'release.json')})
    for path in source_dist.rglob('*'):
        if not path.is_file() or path.name in ('index.html', 'index.html.gz'):
            continue
        destination = target_dist / path.relative_to(source_dist)
        require_asset_directory(target_dist, destination.parent)
        r.require(not destination.is_symlink(), 'Linked shared asset')
        if destination.exists():
            r.require(destination.is_file() and digest_regular(destination) == digest_regular(path), 'Existing shared asset collision')
        else:
            atomic_frontend_copy(path, destination, exclusive=True)
    for name in ('index.html.gz', 'index.html'):
        path, destination = source_dist / name, target_dist / name
        r.require(not destination.is_symlink(), 'Linked frontend entry')
        if path.exists():
            atomic_frontend_copy(path, destination)
        else:
            unlink_regular(destination)
    atomic_frontend_copy(source / 'frontend/package.json', app / 'frontend/package.json')
    atomic_frontend_copy(source / 'release.json', app / 'FRONTEND_RELEASE.json')
    for name, expected in manifest['files'].items():
        if name == 'frontend/package.json' or name.startswith('frontend/dist/'):
            r.require(digest_regular(app / name) == expected, 'Installed frontend checksum mismatch')
    r.private(backup / 'INSTALLED.json', {name: digest_regular(app / name) if (app / name).exists() else None
                                         for name in frontend.ENTRIES})


def rollback_frontend(app, backup):
    guard.require_protected(app)
    evidence = json.loads(read_regular(backup / 'COMPLETE.json'))
    saved = evidence['saved']
    installed_path = backup / 'INSTALLED.json'
    installed = json.loads(read_regular(installed_path)) if installed_path.exists() else None
    for name in frontend.ENTRIES:
        path = app / name
        r.require(not path.is_symlink(), 'Linked frontend entry')
        actual = digest_regular(path) if path.exists() else None
        allowed = {installed[name]} if installed else {saved.get(name), evidence['planned'][name]}
        r.require(actual in allowed, 'Frontend changed since deployment')
    for name, expected in saved.items():
        r.require(digest_regular(backup / BACKUP_FILES[name]) == expected, 'Frontend backup drift')
    for name in frontend.ENTRIES:
        if name in saved:
            atomic_frontend_copy(backup / BACKUP_FILES[name], app / name)
        else:
            unlink_regular(app / name)


frontend.rollback = rollback_frontend
