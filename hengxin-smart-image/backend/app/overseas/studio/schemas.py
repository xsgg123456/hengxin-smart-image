from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class Strict(BaseModel):
    model_config = ConfigDict(extra='forbid')


class ImageEdit(Strict):
    pictureId: UUID
    annotationId: str | None = None
    text: str = Field('', max_length=4000)


class Send(Strict):
    text: str = Field('', max_length=100000)
    skillId: UUID | None = None
    attachmentIds: list[str] = Field(default_factory=list, max_length=100)
    referencePictureIds: list[UUID] = Field(default_factory=list, max_length=100)
    imageEdits: list[ImageEdit] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def content(self):
        if not self.text.strip() and not self.attachmentIds and not self.referencePictureIds:
            raise ValueError('请填写意见或添加附件')
        if len(set(self.attachmentIds)) != len(self.attachmentIds):
            raise ValueError('附件不能重复')
        if len(set(self.referencePictureIds)) != len(self.referencePictureIds):
            raise ValueError('图片不能重复')
        pictures, annotations = set(), set()
        for edit in self.imageEdits:
            if edit.pictureId not in self.referencePictureIds or edit.pictureId in pictures:
                raise ValueError('修改图片必须包含在引用图片中，且不能重复绑定')
            pictures.add(edit.pictureId)
            if not edit.text.strip() and not self.text.strip():
                raise ValueError('请填写图片修改意见')
            if edit.annotationId is not None:
                if not edit.text.strip():
                    raise ValueError('标注图片必须填写标注描述')
                if edit.annotationId not in self.attachmentIds or not edit.annotationId.startswith('upload:'):
                    raise ValueError('标注必须是本轮上传附件')
                try:
                    identity = UUID(edit.annotationId.split(':', 1)[1])
                except ValueError:
                    raise ValueError('标注附件编号无效') from None
                if identity in annotations:
                    raise ValueError('标注图片不能重复绑定')
                annotations.add(identity)
        return self


class Cancel(Strict):
    version: int = Field(ge=1)


class ArchiveRequest(Strict):
    pictureIds: list[UUID] = Field(min_length=1, max_length=1000)
    sku: str = Field(min_length=1, max_length=80)


class Complete(Strict):
    pass
