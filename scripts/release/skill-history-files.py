"""Exact duplicate manifests and reversible moves; never follow production links."""
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import stat
import tarfile
from uuid import UUID


def require(value, message):
    if not value:
        raise ValueError(message)


def safe(path):
    path = Path(path)
    require(path.is_absolute() and '..' not in path.parts, 'Unsafe absolute path')
    for parent in (path, *path.parents):
        require(not parent.is_symlink(), 'Linked path')
    return path


def read(path):
    path = safe(path)
    before = path.stat()
    require(stat.S_ISREG(before.st_mode) and before.st_nlink == 1, 'Unsafe file')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0) | getattr(os, 'O_NOATIME', 0))
    with os.fdopen(fd, 'rb') as stream:
        raw = stream.read()
        after = os.fstat(stream.fileno())
    stamp = lambda s: (s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns,s.st_ctime_ns)
    require(stamp(before) == stamp(after) == stamp(path.stat()), 'File changed')
    return raw


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def file_hash(path):
    value = hashlib.sha256()
    with safe(path).open('rb') as stream:
        while block := stream.read(1024*1024):
            value.update(block)
    return value.hexdigest()


def sync_directory(path):
    if os.name == 'posix':
        fd = os.open(safe(path),os.O_RDONLY|os.O_DIRECTORY|os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


def save(path, value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode()
    with safe(path).open('xb') as stream:
        stream.write(raw)
        stream.flush()
        os.fsync(stream.fileno())
    sync_directory(path.parent)


def inventory(path):
    safe(path)
    require(path.is_dir(), 'Missing package')
    info = path.stat()
    rows = {'.':['dir',stat.S_IMODE(info.st_mode),info.st_uid,info.st_gid]}
    allocated = 0
    for parent, dirs, files in os.walk(path, followlinks=False):
        for name in dirs + files:
            item = safe(Path(parent)/name)
            info = item.lstat()
            mode = stat.S_IMODE(info.st_mode)
            key = item.relative_to(path).as_posix()
            if stat.S_ISDIR(info.st_mode):
                rows[key] = ['dir',mode,info.st_uid,info.st_gid]
            else:
                raw = read(item)
                rows[key] = ['file',mode,info.st_uid,info.st_gid,len(raw),digest(raw)]
                allocated += getattr(info,'st_blocks',0)*512
    require('SKILL.md' in rows, 'Missing SKILL.md')
    return rows, allocated


def target(root, relative):
    parts = Path(relative).parts
    require(len(parts) == 5 and parts[1] == 'rounds' and parts[3] == 'skills', 'Wrong target scope')
    require(str(UUID(parts[0])) == parts[0] and str(UUID(parts[2])) == parts[2], 'Invalid owner')
    require(parts[4] not in ('.','..') and '/' not in parts[4] and '\\' not in parts[4], 'Invalid name')
    path = safe(root/relative)
    require(path.resolve().is_relative_to(root.resolve()), 'Target escaped root')
    return path


def metadata(root, excluded=(), changed_parents=()):
    excluded, changed_parents = set(excluded), set(changed_parents)
    rows = {}
    for parent, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [n for n in dirs if (Path(parent)/n).relative_to(root).as_posix() not in excluded]
        for name in dirs + files:
            item = Path(parent)/name
            key = item.relative_to(root).as_posix()
            info = item.lstat()
            fields = [stat.S_IFMT(info.st_mode),stat.S_IMODE(info.st_mode),info.st_ino,info.st_uid,info.st_gid]
            if key not in changed_parents:
                fields += [info.st_size,info.st_mtime_ns,info.st_ctime_ns]
            if item.is_symlink():
                fields += [os.readlink(item)]
            rows[key] = fields
    return rows


def backup(root, plan, archive):
    """One archive member per content group; plan records every original path."""
    with tarfile.open(archive, 'x:gz', compresslevel=1) as bundle:
        for group in plan['groups']:
            source = target(root,group['keep'])
            require(inventory(source)[0] == group['entries'], 'Backup source drift')
            for name, entry in group['entries'].items():
                member = tarfile.TarInfo(group['key']+'/'+name)
                member.mode, member.uid, member.gid = entry[1:4]
                if entry[0] == 'dir':
                    member.type = tarfile.DIRTYPE
                    bundle.addfile(member)
                else:
                    raw = read(source/name)
                    require((len(raw),digest(raw)) == (entry[4],entry[5]), 'Backup bytes drift')
                    member.size = len(raw)
                    bundle.addfile(member,io.BytesIO(raw))


def verify_backup(plan, archive):
    expected = {g['key']+'/'+name:entry for g in plan['groups'] for name,entry in g['entries'].items()}
    seen = set()
    with tarfile.open(archive,'r:gz') as bundle:
        for member in bundle:
            require(member.name in expected and member.name not in seen, 'Unexpected backup member')
            seen.add(member.name)
            item = expected[member.name]
            require((member.mode,member.uid,member.gid) == tuple(item[1:4]), 'Backup metadata differs')
            if item[0] == 'dir':
                require(member.isdir(), 'Backup directory differs')
            else:
                require(member.isfile(), 'Backup file differs')
                raw = bundle.extractfile(member).read()
                require((len(raw),digest(raw)) == (item[4],item[5]), 'Backup content differs')
    require(seen == set(expected), 'Backup incomplete')


def move_checked(root, work, conversation, groups, check_records):
    """Caller holds the task row and filesystem lock; only duplicate leaves move."""
    channel = safe(root/conversation)
    drops = [name for g in groups for name in g['drop']]
    require(len(drops)==len(set(drops)) and all(g['keep'] not in drops for g in groups), 'Overlapping plan')
    require(all(Path(n).parts[0]==conversation for g in groups for n in [g['keep'],*g['drop']]),
            'Cross-conversation plan')
    excluded = [Path(n).relative_to(conversation).as_posix() for n in drops]
    parents = [str(Path(n).parent) for n in excluded]
    for group in groups:
        require(inventory(target(root,group['keep']))[0] == group['entries'], 'Retained copy drift')
        for name in group['drop']:
            require(inventory(target(root,name))[0] == group['entries'], 'Duplicate drift')
    before = metadata(channel,excluded,parents)
    records = check_records()
    moved = []
    save(work/('journal-'+conversation+'.json'),dict(drops=drops,phase='moving'))
    try:
        for relative in drops:
            source = target(root,relative)
            destination = safe(work/'quarantine'/relative)
            require(not destination.exists(), 'Quarantine already occupied')
            destination.parent.mkdir(parents=True,exist_ok=True,mode=0o700)
            require(source.stat().st_dev == destination.parent.stat().st_dev, 'Cross-device move')
            source.rename(destination)
            moved.append((source,destination))
            sync_directory(source.parent)
            sync_directory(destination.parent)
        require(metadata(channel,excluded,parents) == before, 'Other conversation files changed')
        require(check_records() == records, 'Conversation records changed')
        for group in groups:
            require(inventory(target(root,group['keep']))[0] == group['entries'], 'Retained copy changed')
        save(work/('verified-'+conversation+'.json'),dict(files=len(before),records=digest(records.encode()),drops=drops))
    except BaseException:
        failures = []
        for source,destination in reversed(moved):
            try:
                safe(source)
                require(not os.path.lexists(source), 'Rollback destination occupied')
                safe(destination).rename(source)
            except BaseException as error:
                failures.append(error)
        # A failing disk sync must not prevent restoring the remaining paths.
        for parent in {p.parent for pair in moved for p in pair}:
            try:
                sync_directory(parent)
            except OSError as error:
                failures.append(error)
        if failures:
            raise RuntimeError('Rollback requires inspection; retain journal and backup') from failures[0]
        raise
    for _, destination in moved:
        safe(destination)
        require(destination.is_relative_to(work/'quarantine') and shutil.rmtree.avoids_symlink_attacks,
                'Unsafe quarantine purge')
        shutil.rmtree(destination)
    require(metadata(channel,excluded,parents) == before and check_records() == records, 'Post-purge drift')
    return len(before)
