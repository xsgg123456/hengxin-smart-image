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

    @model_validator(mode='after')
    def nonempty(self):
        if not self.text and not self.annotationFileId:
            raise ValueError('请填写修改意见或上传标注图')
        return self


class RestoreVersion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: int = Field(ge=1)
