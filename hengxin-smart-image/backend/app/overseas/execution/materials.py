"""Write only frozen job inputs; no domestic business or Skill lookup."""
import json
import re
from pathlib import PurePosixPath
from hashlib import sha256
from types import SimpleNamespace
from app.overseas.management.schemas import validate_files
from app.core.skill_package import MAX_TOTAL, MAX_ZIP
from app.storage.minio_store import get_store


def prepare(job, workspace):
    # Queue copies JSON transactionally. Keep the exact input for later audit.
    encoded = json.dumps(job.payload, ensure_ascii=False, allow_nan=False)
    (workspace.control / 'input.json').write_text(encoded, encoding='utf-8')
    work = getattr(workspace, 'round_work', workspace.work)
    (work / 'input.json').write_text(encoded, encoding='utf-8')
    skill = job.payload.get('skill')
    workspace.use_skill = skill is not None
    if skill is None:
        return
    if skill.get('installedRelease'):
        from app.overseas.management.installed_catalog import frozen_package
        package = frozen_package(skill)
        root = work / 'skills' / package.name
        from .skill_copy import write_package
        write_package(root, package.files, work)
        workspace.skill_name = package.name
        workspace.local_skill = root
        return
    name, files = skill.get('name'), skill.get('files')
    if (not isinstance(name, str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_-]{0,99}', name)
            or not isinstance(files, dict) or not files.get('SKILL.md')):
        raise ValueError('Invalid frozen Skill')
    workspace.skill_name = name
    assets = skill.get('assets') or {}
    if set(files) & set(assets):
        raise ValueError('Duplicate frozen Skill resource')
    validate_files({**files, **{path: 'resource' for path in assets}})
    root = work / 'skills' / name
    for relative, content in files.items():
        path = PurePosixPath(relative)
        if (not relative or path.is_absolute() or ':' in relative or '\\' in relative
                or any(part in ('', '.', '..') for part in relative.split('/'))
                or not isinstance(content, str)):
            raise ValueError('Invalid frozen Skill file')
        target = root.joinpath(*path.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding='utf-8')
    total = sum(len(content.encode('utf-8')) for content in files.values())
    for relative, asset in assets.items():
        expected = asset['sizeBytes']
        if not isinstance(expected, int) or not 0 <= expected <= MAX_ZIP:
            raise ValueError('Invalid frozen Skill resource size')
        total += expected
        if total > MAX_TOTAL:
            raise ValueError('Frozen Skill exceeds size limit')
        response = get_store().open(SimpleNamespace(bucket=asset['bucket'], object_key=asset['objectKey']))
        try:
            content = response.read(expected + 1)
        finally:
            response.close()
            response.release_conn()
        if len(content) != expected or sha256(content).hexdigest() != asset['checksum']:
            raise ValueError('Frozen Skill resource integrity mismatch')
        target = root.joinpath(*PurePosixPath(relative).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
    workspace.local_skill = root
