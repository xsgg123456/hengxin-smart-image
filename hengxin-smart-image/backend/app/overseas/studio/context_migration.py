"""Read-only legacy inventory and retryable, non-destructive file migration."""
import hashlib
import json
import os
import stat
from pathlib import PurePosixPath

from . import context_assets as assets
from . import context_fs as fs

EXCLUDED = {'input.json', 'skills', '.context-files.json'}
PRIVATE_DIRECTORIES = {'.agents', '.codex', '.git', '.aws', '.ssh', '.gnupg'}
JOURNAL = 'migration-pending.json'


def walk(root, *, legacy=True):
    fs.checked(root, directory=True)
    pending = [root]
    while pending:
        directory = pending.pop()
        fs.checked(directory, directory=True)
        for child in sorted(directory.iterdir()):
            relative = child.relative_to(root).as_posix()
            parts = PurePosixPath(relative).parts
            if legacy and (parts[0] in EXCLUDED or any(p in PRIVATE_DIRECTORIES for p in parts)):
                continue
            fs.relative(relative)
            fs.checked(child)
            if stat.S_ISDIR(child.lstat().st_mode):
                pending.append(child)
            else:
                fs.checked(child, directory=False)
                yield relative, child


def scan(root, history, managed=(), *, include_originals=False):
    files = []
    for turn in history:
        if turn['turn_id'] in managed:
            continue
        directory = root / 'rounds' / turn['turn_id']
        fs.checked(directory, missing=True, directory=True)
        if not directory.exists():
            continue
        originals = {'inputs/' + assets.legacy_name(i, item): item
                     for i, item in enumerate(turn['inputs'], 1)}
        for relative, path in walk(directory):
            checksum, size = fs.digest(path)
            original = originals.get(relative)
            if original and (checksum, size) == (original['checksum'], original['size_bytes']):
                if include_originals:
                    files.append(dict(turn_id=turn['turn_id'], relative=relative, logical=relative,
                                      checksum=checksum, size_bytes=size, original=True))
                continue
            # Non-original user files in the old inputs directory remain editable.
            logical = ('recovered-inputs/' + turn['turn_id'] + '/' + relative
                       if relative.startswith('inputs/') else relative)
            files.append(dict(turn_id=turn['turn_id'], relative=relative, logical=logical,
                              checksum=checksum, size_bytes=size))
    return files


def key(item):
    return item['turn_id'], item['relative'], item['checksum']


def groups(files):
    result = {}
    for item in files:
        result.setdefault(item['logical'], []).append(item)
    return result


def conflicts(files):
    grouped = groups(files)
    result = {name for name, items in grouped.items()
              if len({item['checksum'] for item in items}) > 1}
    for name in grouped:
        for parent in PurePosixPath(name).parents:
            if parent.as_posix() in grouped:
                result.update((name, parent.as_posix()))
    return result


def version_path(item):
    return '.context-recovered/' + item['turn_id'] + '/' + item['checksum'] + '/' + item['relative']


def source_for(item, persistent, root, *, required=True):
    candidates = [persistent / 'work' / fs.relative(item.get('path', version_path(item)))]
    candidates.append(persistent / 'work' / version_path(item))
    if item['turn_id'] != 'workspace':
        candidates.append(root / 'rounds' / item['turn_id'] / fs.relative(item['relative']))
    candidates.append(persistent / 'work' / fs.relative(item['logical']))
    for path in candidates:
        if (os.path.lexists(path) and fs.checked(path).is_file()
                and fs.digest(path) == (item['checksum'], item['size_bytes'])):
            return path
    if required:
        raise ValueError('历史文件来源已变化，无法恢复版本：' + item['relative'])


def reconcile(persistent, root, recorded):
    """Mapped work is editable, including paths named after a former hash."""
    available, current = {}, {}
    for item in recorded:
        path = persistent / 'work' / fs.relative(item['path'])
        if os.path.lexists(path) and fs.checked(path).is_file():
            checksum, size = fs.digest(path)
            if (checksum, size) != (item['checksum'], item['size_bytes']):
                edited = dict(turn_id='workspace', relative=item['logical'],
                    logical=item['logical'], checksum=checksum, size_bytes=size,
                    path=item['path'], conflict=item.get('conflict', False))
                current[key(edited)] = edited
        # A workspace-only version may have been edited in place; do not claim
        # its former bytes exist. Legacy bytes are recovered from intact rounds.
        if source_for(item, persistent, root, required=False) is not None:
            available[key(item)] = item
    available.update(current)
    return available


def recovery_target(work, item, keep_alias=False):
    """Keep valid public paths and never overwrite an edited recovery path."""
    if ((item.get('conflict') or keep_alias) and item.get('path')
            and (item['path'] != item['logical'] or keep_alias)):
        mapped = work / fs.relative(item['path'])
        if (os.path.lexists(mapped) and fs.checked(mapped).is_file()
                and fs.digest(mapped) == (item['checksum'], item['size_bytes'])):
            return mapped
    relative = version_path(item)
    target, attempt = work / relative, 0
    while os.path.lexists(target):
        if (fs.checked(target).is_file()
                and fs.digest(target) == (item['checksum'], item['size_bytes'])):
            return target
        attempt += 1
        target = work / ('.context-recovered/' + item['turn_id'] + '/'
                         + item['checksum'] + '-' + str(attempt) + '/' + item['relative'])
    return target


def working_files(work, files):
    """Inventory current aliases and every file that blocks a legacy path."""
    found, directories = set(), set()
    for name in groups(files):
        target = work
        for part in PurePosixPath(name).parts:
            target = target / part
            if not os.path.lexists(target):
                break
            fs.checked(target)
            if target.is_file():
                found.add(target)
                break
        else:
            directories.add(name)
            found.update(path for _, path in walk(target, legacy=False))
    known = {(item['logical'], item['checksum'], item['size_bytes']) for item in files}
    current = []
    for path in sorted(found):
        name = path.relative_to(work).as_posix()
        checksum, size = fs.digest(path)
        if (name, checksum, size) not in known:
            current.append(dict(turn_id='workspace', relative=name, logical=name,
                                checksum=checksum, size_bytes=size))
    return current, directories


def remove_aliases(work, ambiguous):
    directories = set()
    for name in ambiguous:
        target = work / fs.relative(name)
        directories.update(parent for parent in target.parents if parent != work and work in parent.parents)
        if os.path.lexists(target):
            fs.checked(target)
            if target.is_file():
                target.unlink()
            else:
                directories.add(target)
    for directory in sorted(directories, key=lambda path: len(path.parts), reverse=True):
        if os.path.lexists(directory):
            fs.checked(directory)
            if directory.is_dir() and not any(directory.iterdir()):
                directory.rmdir()


def apply(persistent, root, manifest, scanned):
    journal = persistent / JOURNAL
    resumed = fs.load(journal) if os.path.lexists(journal) else []
    for item in resumed:
        for field in ('relative', 'logical', 'path'):
            fs.relative(item[field])
    work = persistent / 'work'
    registered = reconcile(persistent, root, [*manifest['files'], *resumed])
    known = set(registered)
    additions = [item for item in scanned if key(item) not in known]
    files = [*registered.values(), *additions]
    current, directories = working_files(work, files)
    files.extend(current)
    ambiguous = conflicts(files) | directories
    ambiguous.update(item['logical'] for item in files if item.get('conflict'))
    # Ordinary edits keep their working path unless an incoming legacy path
    # actually competes with it. On retry, retain the journal's same decision.
    pending_aliases = {key(item) for item in resumed if item['path'] == item['logical']}
    keep_aliases = {item['logical'] for item in files
        if item['turn_id'] == 'workspace' and item.get('path') == item['logical']
        and (not resumed or key(item) in pending_aliases)
        and not any(item['logical'] == added['logical']
                    or item['logical'].startswith(added['logical'] + '/')
                    or added['logical'].startswith(item['logical'] + '/') for added in additions)}
    copies = []
    for name, entries in groups(files).items():
        if name in ambiguous:
            for item in entries:
                target = recovery_target(work, item, name in keep_aliases)
                if not os.path.lexists(target):
                    copies.append((source_for(item, persistent, root), target, item))
                item['path'], item['conflict'] = target.relative_to(work).as_posix(), True
        else:
            target = work / fs.relative(name)
            if not os.path.lexists(target):
                copies.append((source_for(entries[0], persistent, root), target, entries[0]))
            elif fs.digest(target) != (entries[0]['checksum'], entries[0]['size_bytes']):
                raise ValueError('工作文件在迁移盘点后发生改变：' + name)
            for item in entries:
                item['path'], item['conflict'] = name, False
    fs.space(persistent, sum(item['size_bytes'] for _, _, item in copies))
    # Record every planned source, including edited working copies, before any
    # alias removal. A retry can reconstruct its index after a metadata failure.
    fs.save(journal, files)
    for source, target, item in copies:
        fs.copy(source, target, item['checksum'])
    # All source versions are safe before any incompatible alias is removed.
    remove_aliases(work, ambiguous - keep_aliases)
    manifest['files'] = files
    return len(additions)


def public(manifest):
    return [dict(name=PurePosixPath(item['relative']).name,
                 logicalPath='/work/' + item['logical'], path='/work/' + item['path'],
                 sources=[item['turn_id']], sourceChecksum=item['checksum'],
                 conflict=item['conflict']) for item in manifest['files']]


def inventory(history, files):
    frozen = [dict(turn_id=turn['turn_id'], inputs=[assets.source(item) for item in turn['inputs']])
              for turn in history]
    encoded = json.dumps(dict(history=frozen, files=files), ensure_ascii=True,
                         sort_keys=True, separators=(',', ':')).encode()
    originals = {assets.identity(item): item for turn in frozen for item in turn['inputs']}
    aliases = {}
    for turn in frozen:
        for i, item in enumerate(turn['inputs'], 1):
            aliases.setdefault(assets.legacy_name(i, item), set()).add(item['checksum'])
    ordinary = [item for item in files if not item.get('original')]
    conflicting = sorted('/work/' + name for name in conflicts(ordinary))
    conflicting += sorted('/work/inputs/' + name for name, values in aliases.items() if len(values) > 1)
    return dict(digest=hashlib.sha256(encoded).hexdigest(), ordinaryFiles=len(ordinary),
                ordinaryBytes=sum(item['size_bytes'] for item in ordinary), inputFiles=len(originals),
                inputBytes=sum(item['size_bytes'] for item in originals.values()),
                conflicts=conflicting, files=files)
