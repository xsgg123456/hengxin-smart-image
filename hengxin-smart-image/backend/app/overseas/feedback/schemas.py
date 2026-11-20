from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Status = Literal['pending', 'processing', 'resolved']
Message = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]


class FeedbackFields(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    @model_validator(mode='after')
    def valid_text(self):
        if any(isinstance(value, str) and '\x00' in value for value in self.__dict__.values()):
            raise ValueError('文本含有无效字符')
        return self


class CreateFeedback(FeedbackFields):
    question: Message = Field(min_length=1)
    source: str = Field(min_length=1, max_length=500)
    task_name: str | None = Field(default=None, max_length=200)
    # Task context joins up to 100 codes of 80 characters with one separator each.
    sku: str | None = Field(default=None, max_length=8099)


class UpdateFeedback(FeedbackFields):
    version: int = Field(strict=True, ge=1)
    status: Status | None = None
    public_reply: Message | None = None
    internal_note: Message | None = None

    @model_validator(mode='after')
    def has_changes(self):
        changes = self.model_fields_set - {'version'}
        if not changes or any(getattr(self, key) is None for key in changes):
            raise ValueError('请提供要更新的状态、回复或备注')
        return self
