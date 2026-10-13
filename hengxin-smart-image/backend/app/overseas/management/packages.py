"""Legacy package reader retained only for old snapshot validation tests."""
from io import BytesIO
from pathlib import PurePosixPath
from stat import S_IFMT, S_IFREG, S_IFDIR
from zipfile import ZipFile
from app.modules.skills.package_validator import MAX_FILES, MAX_TOTAL, MAX_ZIP
from .schemas import validate_files

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
