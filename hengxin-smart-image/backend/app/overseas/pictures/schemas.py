from typing import Literal
from pydantic import Field
from app.overseas.tasks.schemas import StrictBody


class VersionRequest(StrictBody):
    version: int = Field(ge=1, strict=True)
    taskVersion: int = Field(ge=1, strict=True)


class Point(StrictBody):
    x: float = Field(ge=0, le=8192, allow_inf_nan=False)
    y: float = Field(ge=0, le=8192, allow_inf_nan=False)


class Mark(Point):
    id: str = Field(min_length=1, max_length=100)
    kind: Literal['rect', 'pen']
    width: float = Field(ge=0, le=8192, allow_inf_nan=False)
    height: float = Field(ge=0, le=8192, allow_inf_nan=False)
    points: list[Point] = Field(max_length=2000)
    note: str = Field(max_length=1000)


class RevisionRequest(VersionRequest):
    note: str = Field(max_length=1000)
    marks: list[Mark] = Field(max_length=100)


class RetryRequest(StrictBody):
    version: int = Field(ge=1, strict=True)
    sku: str = Field(min_length=1, max_length=80)


class ArchiveRequest(StrictBody):
    version: int = Field(ge=1, strict=True)
