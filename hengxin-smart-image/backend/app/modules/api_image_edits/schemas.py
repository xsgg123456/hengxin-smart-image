from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator


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
