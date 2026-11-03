from uuid import UUID
from pydantic import Field, field_validator
from app.overseas.tasks.schemas import StrictBody

MAX_ATTACHMENTS = 100


class DraftSku(StrictBody):
    code: str = Field(default='', max_length=80)


class DraftFields(StrictBody):
    name: str = Field(default='', max_length=80)
    productName: str = Field(default='', max_length=80)
    brand: str = Field(default='', max_length=60)
    platform: str = Field(default='', max_length=80)
    language: str = Field(default='', max_length=10)
    market: str = Field(default='', max_length=60)
    skus: list[DraftSku] = Field(default_factory=lambda: [DraftSku()], min_length=1, max_length=1)
    designerId: str = ''

    @field_validator('designerId')
    @classmethod
    def designer_identifier(cls, value):
        return str(UUID(value)) if value else ''


class VersionBody(StrictBody):
    version: int = Field(ge=1, strict=True)


class SaveDraft(VersionBody):
    fields: DraftFields


class SelectSource(SaveDraft):
    sku: str = Field(min_length=1, max_length=80)
    requirementId: str = Field(min_length=1, max_length=200)
