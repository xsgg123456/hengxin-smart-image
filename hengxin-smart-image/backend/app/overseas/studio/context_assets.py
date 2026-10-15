"""Versioned frozen inputs; private source metadata never enters the model index."""
import hashlib
import json
import os
import re
from pathlib import Path

from . import context_fs as fs

FIELDS = ('id', 'name', 'bucket', 'object_key', 'content_type', 'size_bytes', 'checksum')


def source(data):
    item = {field: data[field] for field in FIELDS}
    if (any(not isinstance(item[key], str) or not item[key] for key in FIELDS
            if key != 'size_bytes') or not re.fullmatch('[0-9a-f]{64}', item['checksum'])
            or type(item['size_bytes']) is not int or not 0 < item['size_bytes'] <= 500_000_000):
        raise ValueError('Invalid frozen context input')
    return item


def safe_name(name):
    name = re.sub(r'[^\w. -]', '_', name, flags=re.UNICODE).strip(' .')[:80] or 'input'
    if name.split('.')[0].upper() in {'CON', 'PRN', 'AUX', 'NUL', *(
            f'{prefix}{i}' for prefix in ('COM', 'LPT') for i in range(1, 10))}:
        name = 'input-' + name
    return name


def identity(item):
    stable = json.dumps([item['id'], item['bucket'], item['object_key']],
                        separators=(',', ':'), ensure_ascii=True).encode()
    return hashlib.sha256(stable).hexdigest()[:32] + '/' + item['checksum']


def legacy_name(index, item):
    return fs.relative(str(index) + Path(item['name']).suffix.lower())


def register(manifest, history, current_inputs, current_turn, root):
    assets, candidates, current = manifest['assets'], {}, []
    for position, turn in enumerate([*history, dict(turn_id=current_turn, inputs=current_inputs)]):
        legacy = position < len(history) and turn['turn_id'] not in manifest['managed_turns']
        for index, value in enumerate(turn['inputs'], 1):
            item = source(value)
            key = identity(item)
            entry = assets.setdefault(key, dict(source=item, origins=[],
                path=key + '/' + safe_name(item['name'])))
            if turn['turn_id'] not in entry['origins']:
                entry['origins'].append(turn['turn_id'])
            if legacy:
                alias = legacy_name(index, item)
                versions = manifest['aliases'].setdefault(alias, [])
                if key not in versions:
                    versions.append(key)
                candidates.setdefault(key, []).append(root / 'rounds' / turn['turn_id'] / 'inputs' / alias)
            if position == len(history):
                current.append(dict(name=item['name'], path='/work/inputs/' + entry['path']))
    return candidates, current


def matches(path, item):
    fs.checked(path, missing=True, directory=False)
    return os.path.lexists(path) and fs.digest(path) == (item['checksum'], item['size_bytes'])


def restore(root, manifest, candidates, read_source, *, reserve=0):
    directory = fs.mkdir(root / 'inputs')
    pending = []
    for key, entry in manifest['assets'].items():
        item = source(entry['source'])
        if identity(item) != key or entry['path'] != key + '/' + safe_name(item['name']):
            raise ValueError('Invalid context asset manifest')
        target = directory / fs.relative(entry['path'])
        if not matches(target, item):
            pending.append((key, entry, target))
    aliases = []
    for alias, keys in manifest['aliases'].items():
        target = directory / fs.relative(alias)
        versions = [manifest['assets'][key] for key in keys]
        fs.checked(target, missing=True, directory=False)
        if len({v['source']['checksum'] for v in versions}) > 1:
            aliases.append((target, None))
        elif not matches(target, versions[0]['source']):
            aliases.append((target, versions[0]))
    required = sum(entry['source']['size_bytes'] for _, entry, _ in pending)
    required += sum(entry['source']['size_bytes'] for _, entry in aliases if entry is not None)
    fs.space(root, required + reserve)
    for key, entry, target in pending:
        item = entry['source']
        local = next((path for path in candidates.get(key, []) if matches(path, item)), None)
        if local is not None:
            fs.copy(local, target, item['checksum'])
        else:
            try:
                content = read_source(dict(item))
            except Exception as exc:
                raise ValueError('原件恢复失败：' + item['name']) from exc
            if (not isinstance(content, bytes) or len(content) != item['size_bytes']
                    or hashlib.sha256(content).hexdigest() != item['checksum']):
                raise ValueError('原件恢复校验失败：' + item['name'])
            fs.write(target, content)
    for target, entry in aliases:
        if entry is None:
            if os.path.lexists(target):
                fs.checked(target, directory=False).unlink()
            continue
        fs.copy(directory / fs.relative(entry['path']), target, entry['source']['checksum'])
    return {key for key, _, _ in pending}


def public(manifest):
    result = []
    for entry in manifest['assets'].values():
        result.append(dict(name=entry['source']['name'], path='/work/inputs/' + entry['path'],
            sources=entry['origins'], checksum=entry['source']['checksum'], conflict=False))
    for alias, keys in manifest['aliases'].items():
        entries = [manifest['assets'][key] for key in keys]
        conflict = len({entry['source']['checksum'] for entry in entries}) > 1
        result.append(dict(name=alias, logicalPath='/work/inputs/' + alias,
            paths=['/work/inputs/' + entry['path'] for entry in entries],
            sources=sorted({origin for entry in entries for origin in entry['origins']}), conflict=conflict))
    return result
