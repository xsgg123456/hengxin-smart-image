from uuid import UUID
from pydantic import Field, field_validator
from app.overseas.tasks.schemas import StrictBody


class SubmitMaterials(StrictBody):
    materialIds: list[UUID] = Field(min_length=1, max_length=2)
    version: int = Field(ge=1, strict=True)

    @field_validator('materialIds')
    @classmethod
    def unique_materials(cls, values):
        if len(set(values)) != len(values):
            raise ValueError('资料不能重复')
        return values
