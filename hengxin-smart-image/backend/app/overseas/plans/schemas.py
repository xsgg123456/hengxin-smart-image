from typing import Annotated
from pydantic import Field, StringConstraints, model_validator
from app.overseas.tasks.schemas import StrictBody

Text = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=20000)]


class AnalysisRequest(StrictBody):
    version: int = Field(ge=1, strict=True)
    feedback: str = Field(default='', max_length=10000)


class ConfirmRequest(StrictBody):
    version: int = Field(ge=1, strict=True)


class Picture(StrictBody):
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=300)]
    description: Text
    prompt: Text
    width: int = Field(ge=1, le=8192, strict=True)
    height: int = Field(ge=1, le=8192, strict=True)


class SkuPlan(StrictBody):
    code: Annotated[str, StringConstraints(min_length=1, max_length=80)]
    pictures: list[Picture] = Field(min_length=1, max_length=100)


class PlanContent(StrictBody):
    skus: list[SkuPlan] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def complete(self):
        if len({s.code.casefold() for s in self.skus}) != len(self.skus):
            raise ValueError('Duplicate SKU')
        if sum(len(s.pictures) for s in self.skus) > 100:
            raise ValueError('At most 100 pictures')
        return self


def validate_content(value, codes):
    result = PlanContent.model_validate(value).model_dump()
    if {s['code'] for s in result['skus']} != set(codes):
        raise ValueError('Plan SKU set does not match frozen input')
    return result
