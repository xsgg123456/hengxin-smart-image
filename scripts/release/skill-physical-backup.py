"""Read-only central library backup; explicit isolated restoration, never production."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat

ROOT = Path('/var/lib/hengxin-overseas/local-skills')
NAME = 'central-skills-backup'


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def safe(path):
    path = Path(os.path.abspath(path))
    for part in (path, *path.parents):
        if part.exists() or part.is_symlink():
            info = part.lstat()
            require(not stat.S_ISLNK(info.st_mode) and not getattr(part, 'is_junction', lambda: False)(),
                    'Linked path: '+str(part))
    return path


def separate(left, right):
    require(not left.is_relative_to(right) and not right.is_relative_to(left), 'Paths must be isolated')


def isolated(path):
    path = safe(path)
    separate(path, safe(ROOT))
    return path


def reader(path):
    flags = os.O_RDONLY | getattr(os, 'O_BINARY', 0) | getattr(os, 'O_NOFOLLOW', 0)
    if hasattr(os, 'geteuid') and os.geteuid() == 0:
        flags |= getattr(os, 'O_NOATIME', 0)
    fd = os.open(safe(path), flags)
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
        os.close(fd)
        raise RuntimeError('Only unlinked regular files allowed: '+str(path))
    return os.fdopen(fd, 'rb')


def digest(path, destination=None):
    sha = hashlib.sha256()
    with reader(path) as source:
        while block := source.read(1024*1024):
            sha.update(block)
            if destination is not None:
                destination.write(block)
    return sha.hexdigest()


def metadata(info):
    return dict(mode=stat.S_IMODE(info.st_mode), uid=info.st_uid, gid=info.st_gid, mtimeNs=info.st_mtime_ns)


def snapshot(root, payload=None):
    entries = []
    def visit(path, name):
        info = safe(path).lstat()
        require(stat.S_ISDIR(info.st_mode) or stat.S_ISREG(info.st_mode), 'Special file rejected: '+name)
        entry = dict(path=name, kind='dir' if stat.S_ISDIR(info.st_mode) else 'file', **metadata(info))
        if entry['kind'] == 'file':
            entry.update(size=info.st_size, sha256=digest(path))
            if payload is not None and not (payload/entry['sha256']).exists():
                with (payload/entry['sha256']).open('xb') as output:
                    require(digest(path, output) == entry['sha256'], 'Source changed during backup')
                    output.flush()
                    os.fsync(output.fileno())
        entries.append(entry)
        if entry['kind'] == 'dir':
            for child in sorted(path.iterdir()):
                visit(child, child.relative_to(root).as_posix())
    visit(root, '.')
    return entries


def valid_index(data):
    require(data.get('schema') == 1 and data.get('source') == ROOT.as_posix(), 'Wrong backup schema/source')
    entries = data.get('entries')
    require(isinstance(entries, list) and entries, 'Missing entries')
    paths, objects = {}, {}
    for item in entries:
        name, kind = item.get('path'), item.get('kind')
        require(isinstance(name, str) and name and '\\' not in name and ':' not in name and '\0' not in name,
                'Invalid relative path')
        parts = PurePosixPath(name)
        require(not parts.is_absolute() and '..' not in parts.parts and parts.as_posix() == name,
                'Unsafe relative path')
        require(name not in paths and kind in ('dir', 'file'), 'Duplicate path or special file')
        keys = {'path', 'kind', 'mode', 'uid', 'gid', 'mtimeNs'} | ({'size', 'sha256'} if kind == 'file' else set())
        require(set(item) == keys, 'Unexpected entry fields')
        require(all(type(item[k]) is int for k in ('mode', 'uid', 'gid', 'mtimeNs')) and
                0 <= item['mode'] <= 0o7777 and item['uid'] >= 0 and item['gid'] >= 0, 'Invalid metadata')
        if kind == 'file':
            require(isinstance(item['sha256'], str) and re.fullmatch('[a-f0-9]{64}', item['sha256']) and
                    type(item['size']) is int and item['size'] >= 0, 'Invalid object reference')
            require(item['sha256'] not in objects or objects[item['sha256']] == item['size'], 'Object size conflict')
            objects[item['sha256']] = item['size']
        paths[name] = item
    require(paths.get('.', {}).get('kind') == 'dir', 'Root directory missing')
    for name in paths:
        if name != '.':
            require(paths.get(PurePosixPath(name).parent.as_posix(), {}).get('kind') == 'dir', 'Parent missing')
    return paths, objects


def verify(work, expected):
    backup = safe(isolated(work)/NAME)
    require(re.fullmatch('[a-f0-9]{64}', expected or '') and digest(backup/'index.json') == expected,
            'Index hash mismatch')
    with reader(backup/'index.json') as stream:
        data = json.load(stream)
    _, objects = valid_index(data)
    require({p.name for p in backup.iterdir()} == {'index.json', 'payload'}, 'Unexpected backup content')
    payload = safe(backup/'payload')
    require(payload.is_dir() and {p.name for p in payload.iterdir()} == set(objects), 'Payload references mismatch')
    for sha, size in objects.items():
        require((payload/sha).lstat().st_size == size and digest(payload/sha) == sha, 'Payload hash mismatch')
    return data


def summary(data, expected):
    _, objects = valid_index(data)
    return dict(indexSha256=expected, entries=len(data['entries']), uniqueFiles=len(objects),
                logicalBytes=sum(e.get('size', 0) for e in data['entries']), payloadBytes=sum(objects.values()))


def create(work, source=ROOT):
    work, source = isolated(work), safe(source)
    if source == safe(ROOT):
        require(hasattr(os, 'geteuid') and os.geteuid() == 0, 'Root required')
    separate(work, source)
    require(source.is_dir(), 'Source directory missing')
    work.mkdir(mode=0o700, parents=True, exist_ok=True)
    if hasattr(os, 'geteuid'):
        info = work.stat()
        require(info.st_uid == 0 and stat.S_IMODE(info.st_mode) == 0o700, 'Work must be root-owned mode 0700')
    backup = work/NAME
    backup.mkdir(mode=0o700)
    payload = backup/'payload'
    payload.mkdir(mode=0o700)
    data = dict(schema=1, source=ROOT.as_posix(), entries=snapshot(source, payload))
    require(snapshot(source) == data['entries'], 'Source changed; backup incomplete')
    with (backup/'index.json').open('x', encoding='utf-8', newline='\n') as output:
        json.dump(data, output, ensure_ascii=False, sort_keys=True, separators=(',', ':'))
        output.flush()
        os.fsync(output.fileno())
    expected = digest(backup/'index.json')
    verify(work, expected)
    return summary(data, expected)


def restore(work, target, expected):
    data = verify(work, expected)
    target, work = isolated(target), isolated(work)
    separate(target, work)
    require(not target.exists() or target.is_dir() and not any(target.iterdir()), 'Restore target must be empty')
    target.mkdir(mode=0o700, parents=True, exist_ok=True)
    entries = sorted(data['entries'], key=lambda e: (len(PurePosixPath(e['path']).parts), e['path']))
    for entry in entries:
        path = target/entry['path']
        if entry['kind'] == 'dir':
            path.mkdir(mode=0o700, exist_ok=True)
        else:
            with path.open('xb') as output:
                require(digest(work/NAME/'payload'/entry['sha256'], output) == entry['sha256'], 'Payload changed')
    for entry in reversed(entries):
        path = target/entry['path']
        if hasattr(os, 'chown'):
            os.chown(path, entry['uid'], entry['gid'], follow_symlinks=False)
        path.chmod(entry['mode'])
        os.utime(path, ns=(entry['mtimeNs'], entry['mtimeNs']))
    actual = {entry['path']: entry for entry in snapshot(target)}
    require(actual == {entry['path']: entry for entry in entries}, 'Restored contents or metadata differ')
    return dict(status='ISOLATED_RESTORE_VERIFIED', target=str(target), **summary(data, expected))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('create', 'verify', 'restore-test'))
    parser.add_argument('--work', type=Path, required=True)
    parser.add_argument('--expected', help='Externally pinned index SHA256; mandatory for verify/restore')
    parser.add_argument('--target', type=Path)
    args = parser.parse_args()
    if args.action != 'verify':
        require(hasattr(os, 'geteuid') and os.geteuid() == 0, 'Root required')
    os.umask(0o077)
    if args.action == 'create':
        result = create(args.work)
    elif args.action == 'verify':
        result = dict(status='BACKUP_VERIFIED', **summary(verify(args.work, args.expected), args.expected))
    else:
        require(args.target is not None, 'restore-test requires --target')
        result = restore(args.work, args.target, args.expected)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    main()
