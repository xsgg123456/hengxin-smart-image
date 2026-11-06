"""Bounded, portable folder manifests shared by the API and privileged publisher."""
from typing import Literal
from pydantic import Field, field_validator
from .schemas import Strict, validate_files
from .installed_tree import MAX_ENTRIES, MAX_FILE, MAX_TREE


class FileEntry(Strict):
    size: int = Field(ge=0, le=MAX_FILE, strict=True)
    sha256: str = Field(pattern=r'^[a-f0-9]{64}$')


class DirectoryEntry(Strict):
    directory: Literal[True]


def safe_name(value):
    validate_files({'SKILL.md': 'x', value: 'x'})
    if '/' in value:
        raise ValueError('根文件夹名称不能包含路径')
    return value


class TransferCreate(Strict):
    rootName: str = Field(min_length=1, max_length=200)
    entries: dict[str, FileEntry | DirectoryEntry] = Field(min_length=1, max_length=MAX_ENTRIES)
    _name = field_validator('rootName')(safe_name)

    @field_validator('entries')
    @classmethod
    def complete_manifest(cls, entries):
        seen, total, count = {}, 0, 0
        for path, info in entries.items():
            directory = isinstance(info, DirectoryEntry)
            if path.endswith('/') != directory:
                raise ValueError('目录路径必须以 / 结尾，文件不能以 / 结尾')
            relative = path.rstrip('/')
            validate_files({'SKILL.md': 'x', relative: 'x'})
            key = relative.casefold()
            if key in seen:
                raise ValueError('文件夹清单包含大小写冲突或重复路径')
            seen[key] = directory
            if not directory:
                count += 1
                total += info.size
        if count > 1000 or total > MAX_TREE or 'SKILL.md' not in entries:
            raise ValueError('清单须含根 SKILL.md，最多1000文件、256 MiB')
        for path in entries:
            parts = path.rstrip('/').split('/')
            for length in range(1, len(parts)):
                parent = '/'.join(parts[:length]) + '/'
                if parent not in entries or not isinstance(entries[parent], DirectoryEntry):
                    raise ValueError('清单缺少父目录或文件目录路径冲突')
        return entries


class TransferInstall(Strict):
    baseRelease: str | None = Field(pattern=r'^[a-f0-9]{64}$')


class SkillDelete(Strict):
    release: str = Field(pattern=r'^[a-f0-9]{64}$')
    checksum: str = Field(pattern=r'^[a-f0-9]{64}$')
    version: int = Field(ge=1, strict=True)


class SkillReclaim(Strict):
    release: str = Field(pattern=r'^[a-f0-9]{64}$')
    dryRun: bool = Field(default=True, strict=True)
