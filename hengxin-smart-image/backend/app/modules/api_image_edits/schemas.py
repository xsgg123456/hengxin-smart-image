from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class CreateTask(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=60)
    prompt: str = Field(min_length=1, max_length=4000)
    originalFileIds: list[UUID] = Field(min_length=1, max_length=20)
    materialFileId: UUID

    @field_validator('originalFileIds')
    @classmethod
    def unique_ids(cls, values):
        if len(values) != len(set(values)):
            raise ValueError('原图不能重复')
        return values


class ResolveTask(BaseModel):
    model_config = ConfigDict(extra='forbid')
    confirmedStopped: bool


class ReviseItem(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)
    baseVersion: int = Field(ge=1)
    text: str = Field(default='', max_length=4000)
    annotationFileId: UUID | None = None
    kind: Literal['image_edit', 'text_edit', 'text_repair'] = 'text_edit'
    prompt: str | None = Field(default=None, max_length=10000)

    @model_validator(mode='after')
    def nonempty(self):
        # Old annotation-only bodies may only confirm an already accepted key.
        if self.kind in {'image_edit', 'text_edit'} and not self.text and (
                'kind' in self.model_fields_set or not self.annotationFileId):
            raise ValueError('请填写修改意见')
        if self.kind == 'text_repair' and self.annotationFileId:
            raise ValueError('修复文案不接受标注图')
        return self


class RestoreVersion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1)
