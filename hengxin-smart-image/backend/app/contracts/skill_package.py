from pydantic import BaseModel, Field, field_validator
from app.core.semver import validate_semver
from .business import Mode


class SkillRegisterInput(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$')
    mode: Mode
    version: str = Field(max_length=100)
    description: str = Field(default='', max_length=2000)

    @field_validator('version')
    @classmethod
    def valid_version(cls, value):
        return validate_semver(value)
