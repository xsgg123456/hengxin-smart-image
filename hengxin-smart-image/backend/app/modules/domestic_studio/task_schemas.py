"""Validated domestic task mutations."""
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .workspaces import WorkspaceName

TaskStatus = Literal['active', 'completed']


def valid_name(value):
    if value is None:
        return value
    value = value.strip()
    if not value or any(ord(char) < 32 or ord(char) == 127 for char in value):
        raise ValueError('请输入1–60字符任务名称')
    return value


class NewTask(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=60)
    workspace: WorkspaceName
    _name = field_validator('name')(valid_name)


class UpdateTask(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1)
    name: str | None = Field(None, min_length=1, max_length=60)
    completed: bool | None = None
    _name = field_validator('name')(valid_name)

    @model_validator(mode='after')
    def mutation(self):
        if self.name is None and self.completed is None:
            raise ValueError('请选择任务修改内容')
        return self


class DeleteTask(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1)
