"""Accept a complete Skill ZIP without executing package contents."""
from hashlib import sha256
from io import BytesIO
from pathlib import PurePosixPath
from stat import S_IFMT, S_IFREG, S_IFDIR
from types import SimpleNamespace
from uuid import uuid4
from zipfile import ZipFile, BadZipFile
from zlib import error as ZlibError
from fastapi import HTTPException
from app.core.config import get_settings
from app.overseas.tasks.service import lock_actor
from app.modules.skills.package_validator import MAX_FILES, MAX_TOTAL, MAX_ZIP
from .schemas import validate_files, SkillCreate
from .skills import mutate

TEXT = {'.md', '.txt', '.py', '.js', '.ts', '.json', '.yaml', '.yml', '.toml', '.html', '.css', '.sh', '.ps1', '.csv'}


def unpack(data):
    if not data or len(data) > MAX_ZIP:
        raise ValueError('Skill ZIP 必须非空且不超过20 MiB')
    files, total, seen = {}, 0, set()
    with ZipFile(BytesIO(data)) as archive:
        if len(archive.infolist()) > MAX_FILES:
            raise ValueError('Skill ZIP 条目超过1000')
        for entry in archive.infolist():
            path = entry.filename.rstrip('/')
            # Reuse the same path rules as the existing text Skill registration.
            validate_files({'SKILL.md': 'validation', **({path: 'validation'} if path != 'SKILL.md' else {})})
            if entry.orig_filename != entry.filename or path.casefold() in seen or entry.flag_bits & 1:
                raise ValueError('ZIP 包含重复或加密条目')
            seen.add(path.casefold())
            kind = S_IFMT(entry.external_attr >> 16)
            if kind not in (0, S_IFREG, S_IFDIR) or (kind == S_IFDIR and not entry.is_dir()):
                raise ValueError('ZIP 不支持链接或特殊文件')
            total += entry.file_size
            if entry.file_size > MAX_ZIP or total > MAX_TOTAL or entry.file_size > max(1, entry.compress_size) * 100:
                raise ValueError('ZIP 解压大小或压缩比超限')
            content = archive.read(entry)
            if entry.is_dir():
                if content:
                    raise ValueError('ZIP 目录含数据')
            else:
                files[path] = content
    if 'SKILL.md' not in files:
        roots = {path.split('/')[0] for path in files}
        if len(roots) != 1:
            raise ValueError('请上传单个Skill文件夹，根目录须包含SKILL.md')
        prefix = next(iter(roots)) + '/'
        files = {path[len(prefix):]: content for path, content in files.items()}
    validate_files({path: 'validation' for path in files})
    text, assets = {}, {}
    for path, content in files.items():
        if PurePosixPath(path).suffix.lower() in TEXT:
            text[path] = content.decode('utf-8-sig')
        else:
            assets[path] = content
    validate_files(text)
    return text, assets


def import_package(session, store, actor, data, name, stage, identity=None, version=None):
    lock_actor(session, actor, 'skills.manage')
    try:
        files, resources = unpack(data)
        body = SkillCreate(name=name, stage=stage, files=files)
    except (ValueError, BadZipFile, RuntimeError, NotImplementedError, ZlibError, EOFError):
        raise HTTPException(422, 'Skill包无效：需要单个含非空SKILL.md的安全ZIP及UTF-8文本文件') from None
    assets = {}
    # Immutable object keys make retry and version publication independent.
    # Unknown DB commit outcomes must not delete potentially referenced objects.
    for path, content in resources.items():
        record = SimpleNamespace(bucket=get_settings().minio_bucket,
            object_key=f'skill-assets/{uuid4()}', content_type='application/octet-stream')
        try:
            store.put(record, content)
        except Exception:
            raise HTTPException(503, 'Skill资源存储失败，请稍后重试') from None
        assets[path] = {'bucket': record.bucket, 'objectKey': record.object_key,
                        'checksum': sha256(content).hexdigest(), 'sizeBytes': len(content)}
    payload = SimpleNamespace(name=body.name, stage=body.stage, files=files, assets=assets, version=version)
    return mutate(session, actor, payload, identity, publish=identity is not None)
