from typing import Annotated, Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

Text80 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Text60 = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=60)]


class StrictBody(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)


class Sku(StrictBody):
    code: Text80


class CreateTask(StrictBody):
    name: Text80
    productName: Text80
    brand: Text60
    platform: Literal['Amazon', 'TikTok Shop', 'Shopee', 'Lazada', '其他']
    market: Text60
    remarks: str = Field(default='', max_length=1000)
    skus: list[Sku] = Field(min_length=1, max_length=100)
    designerId: UUID

    @field_validator('platform', mode='before')
    @classmethod
    def strip_platform(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator('skus')
    @classmethod
    def unique_codes(cls, values):
        if len({item.code.casefold() for item in values}) != len(values):
            raise ValueError('SKU不能重复')
        return values


class Assignment(StrictBody):
    designerId: UUID
    version: int = Field(ge=1, strict=True)
