from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class Send(Strict):
    text: str = Field('', max_length=100000)
    skillId: UUID | None = None
    attachmentIds: list[str] = Field(default_factory=list, max_length=100)
    referencePictureIds: list[UUID] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def content(self):
        if not self.text.strip() and not self.attachmentIds and not self.referencePictureIds:
            raise ValueError('请填写意见或添加附件')
        if len(set(self.attachmentIds)) != len(self.attachmentIds):
            raise ValueError('附件不能重复')
        if len(set(self.referencePictureIds)) != len(self.referencePictureIds):
            raise ValueError('图片不能重复')
        return self


class Cancel(Strict):
    version: int = Field(ge=1)


class ArchiveRequest(Strict):
    pictureIds: list[UUID] = Field(min_length=1, max_length=1000)
    sku: str = Field(min_length=1, max_length=80)


class Complete(Strict):
    pass
