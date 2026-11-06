"""Describe frozen Skill content before downloading any legacy binary assets."""
import hashlib
import re
from pathlib import PurePosixPath
from types import SimpleNamespace

from app.core.skill_package import MAX_TOTAL, MAX_ZIP
from app.overseas.management.schemas import validate_files
from app.overseas.studio.context_fs import relative


def entry(path, content=None, *, checksum=None, size=None):
    relative(path)
    return dict(checksum=hashlib.sha256(content).hexdigest() if content is not None else checksum,
                size=len(content) if content is not None else size,
                mode=0o755 if PurePosixPath(path).suffix.lower() in ('.sh', '.py') else 0o644)


def describe(skill, get_store, workspace=None):
    if skill.get('installedRelease'):
        from app.overseas.management.installed_catalog import frozen_item, frozen_package
        if workspace is not None and hasattr(workspace, 'home'):
            from .skill_history import find, owner
            _, item, _ = frozen_item(skill)
            found = find(owner(workspace), item)
            if found is not None:
                _, files = found
                return item['name'], {p: entry(p, b) for p, b in files.items()}, files.__getitem__
        package = frozen_package(skill)
        return package.name, {p: entry(p, b) for p, b in package.files.items()}, package.files.__getitem__
    name, texts, assets = skill.get('name'), skill.get('files'), skill.get('assets') or {}
    if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', name)
            or not isinstance(texts, dict) or not texts.get('SKILL.md') or not isinstance(assets, dict)
            or any(not isinstance(v, str) for v in texts.values()) or set(texts) & set(assets)):
        raise ValueError('Invalid frozen Skill')
    validate_files({**texts, **{p: 'resource' for p in assets}})
    files = {p: value.encode('utf-8') for p, value in texts.items()}
    entries = {p: entry(p, value) for p, value in files.items()}
    for path, asset in assets.items():
        checksum, size = asset.get('checksum'), asset.get('sizeBytes')
        if (not isinstance(checksum, str) or not re.fullmatch(r'[a-f0-9]{64}', checksum)
                or type(size) is not int or not 0 <= size <= MAX_ZIP):
            raise ValueError('Invalid frozen Skill resource')
        entries[path] = entry(path, checksum=checksum, size=size)
    if sum(item['size'] for item in entries.values()) > MAX_TOTAL:
        raise ValueError('Frozen Skill exceeds size limit')

    def read(path):
        if path in files:
            return files[path]
        asset = assets[path]
        response = get_store().open(SimpleNamespace(bucket=asset['bucket'], object_key=asset['objectKey']))
        try:
            return response.read(asset['sizeBytes'] + 1)
        finally:
            response.close()
            response.release_conn()

    return name, entries, read
