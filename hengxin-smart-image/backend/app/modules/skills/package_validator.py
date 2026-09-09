"""Read every ZIP entry before accepting; never execute package code."""
import hashlib
import io
import json
import re
import stat
import zipfile
import zlib
from dataclasses import dataclass

import yaml

MAX_ZIP = 20 * 1024 * 1024
MAX_TOTAL = 100 * 1024 * 1024
MAX_FILES = 1000
MODES = ('wallpaper', 'product', 'text')


@dataclass
class Package:
    name: str
    description: str
    checksum: str
    files: dict[str, bytes]
    requires: dict[str, list[str]]


def validate_package(data: bytes, mode: str, version: str) -> Package:
    if mode not in MODES or not re.fullmatch(r'\d+\.\d+\.\d+(?:-[\w.-]+)?', version) or len(version) > 100:
        raise ValueError('类型或语义版本无效')
    if not data or len(data) > MAX_ZIP:
        raise ValueError('ZIP 包必须非空且不超过 20 MiB')
    try:
        return _read(data, mode, version)
    except (zipfile.BadZipFile, UnicodeError, yaml.YAMLError, json.JSONDecodeError,
            RuntimeError, NotImplementedError, zlib.error, EOFError) as error:
        raise ValueError('ZIP 或 Skill 元数据损坏') from error


def _read(data, mode, version):
    files, seen, total = {}, set(), 0
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        if len(archive.infolist()) > MAX_FILES:
            raise ValueError('ZIP 条目超过 1000')
        for entry in archive.infolist():
            path = entry.filename
            parts = path.rstrip('/').split('/')
            if (entry.orig_filename != path or not path or '\\' in path or path.startswith('/')
                    or any(p in ('', '.', '..') or ':' in p or p.endswith((' ', '.'))
                           or any(ord(c) < 32 for c in p) for p in parts)):
                raise ValueError('ZIP 包含不安全路径')
            if any(re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', p) for p in parts):
                raise ValueError('ZIP 包含特殊设备路径')
            key = path.rstrip('/').casefold()
            if key in seen:
                raise ValueError('ZIP 包含重复路径')
            seen.add(key)
            filetype = stat.S_IFMT(entry.external_attr >> 16)
            if filetype not in (0, stat.S_IFREG, stat.S_IFDIR) or (filetype == stat.S_IFDIR and not entry.is_dir()):
                raise ValueError('ZIP 不允许链接或特殊文件')
            total += entry.file_size
            if entry.file_size > MAX_ZIP or total > MAX_TOTAL or entry.file_size > max(1, entry.compress_size) * 100:
                raise ValueError('ZIP 解压大小或压缩比超过限制')
            # read validates CRC; a directory must not conceal payload.
            content = archive.read(entry)
            if entry.is_dir():
                if content:
                    raise ValueError('ZIP 目录条目含数据')
            else:
                files[path] = content
    root = ''
    if 'SKILL.md' not in files:
        roots = {p.split('/')[0] for p in files}
        if len(roots) != 1:
            raise ValueError('ZIP 需要根 SKILL.md 或单个顶层目录')
        root = next(iter(roots)) + '/'
    files = {p[len(root):]: v for p, v in files.items()}
    if 'SKILL.md' not in files:
        raise ValueError('缺少 SKILL.md')
    for path in files:
        if any('/'.join(path.split('/')[:i]) in files for i in range(1, len(path.split('/')))):
            raise ValueError('ZIP 文件与目录路径冲突')
    document = files['SKILL.md'].decode('utf-8-sig')
    match = re.match(r'\A---\s*\r?\n(.*?)\r?\n---(?:\s*\r?\n|$)', document, re.S)
    if not match or len(match.group(1)) > 65536:
        raise ValueError('SKILL.md 需要 YAML name/description')
    metadata = yaml.safe_load(match.group(1))
    if not isinstance(metadata, dict) or any(not isinstance(metadata.get(k), str) or not metadata[k].strip() for k in ('name', 'description')):
        raise ValueError('Skill 名称和描述必填')
    if len(metadata['name']) > 200 or len(metadata['description']) > 10000:
        raise ValueError('Skill 元数据过长')
    manifest = json.loads(files.get('hengxin-skill.json', b'{}'))
    if not isinstance(manifest, dict) or manifest.get('mode', mode) != mode or manifest.get('version', version) != version:
        raise ValueError('包声明类型或版本不匹配')
    requires = manifest.get('requires', {})
    if not isinstance(requires, dict) or set(requires) - {'executables', 'pythonModules'}:
        raise ValueError('不支持的依赖声明')
    for kind, values in requires.items():
        if not isinstance(values, list) or len(values) > 100 or any(not isinstance(v, str) or not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', v) for v in values):
            raise ValueError('依赖声明无效')
    return Package(metadata['name'].strip(), metadata['description'].strip(),
                   hashlib.sha256(data).hexdigest(), files, requires)
