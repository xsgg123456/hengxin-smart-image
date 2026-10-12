import re
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, field_validator
from app.contracts.management import SkillRegisterInput
from app.modules.skills.package_validator import MAX_FILES, MAX_TOTAL, MAX_ZIP

Stage = Literal['analysis', 'generation', 'revision']


def validate_files(files):
    if not files or len(files) > MAX_FILES or not files.get('SKILL.md', '').strip():
        raise ValueError('必须提供非空 SKILL.md，文件数不能超过1000')
    seen, total = set(), 0
    for path, content in files.items():
        parts = path.split('/')
        if (not path or len(path) > 500 or '\\' in path or any(
                p in ('', '.', '..') or ':' in p or p.endswith((' ', '.'))
                or any(ord(c) < 32 for c in p)
                or re.fullmatch(r'(?i)(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?', p) for p in parts)):
            raise ValueError('Skill 包含不安全路径')
        if path.casefold() in seen:
            raise ValueError('Skill 包含重复路径')
        seen.add(path.casefold())
        size = len(content.encode('utf-8'))
        total += size
        if size > MAX_ZIP or total > MAX_TOTAL or '\x00' in content:
            raise ValueError('Skill 文件内容或大小无效')
    for path in seen:
        if any('/'.join(path.split('/')[:i]) in seen for i in range(1, len(path.split('/')))):
            raise ValueError('Skill 文件与目录冲突')
    return files


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Files(Strict):
    files: dict[str, str]
    _files = field_validator('files')(validate_files)


class SkillCreate(Files):
    name: str
    stage: Stage

    @field_validator('name')
    @classmethod
    def name_valid(cls, value):
        return SkillRegisterInput(name=value, mode='text', version='1.0.0').name


class SkillPublish(Files):
    version: int = Field(ge=1, strict=True)


class SkillPatch(Strict):
    version: int = Field(ge=1, strict=True)
    enabled: bool = Field(strict=True)


class Defaults(Strict):
    analysis: UUID | None
    generation: UUID | None
    revision: UUID | None


class SettingsPatch(Strict):
    version: int = Field(ge=1, strict=True)
    paused: bool = Field(strict=True)
    concurrency: int = Field(ge=1, le=5, strict=True)
    timeoutSeconds: int = Field(ge=10, le=7200, strict=True)
    defaults: Defaults
