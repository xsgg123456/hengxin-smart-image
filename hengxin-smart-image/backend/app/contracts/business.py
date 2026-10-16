from .fields import omitted
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

Mode = Literal['wallpaper', 'product', 'text']
Role = Literal['super_admin', 'design_manager', 'designer', 'operator']
T = TypeVar('T')


class ApiErrorBody(BaseModel):
    code: str
    message: str
    requestId: str = omitted()


class PageQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=20, ge=1, le=100)
    search: str = omitted()


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    page: int
    pageSize: int
    total: int


class User(BaseModel):
    id: str
    name: str
    role: Role | None
    status: Literal['pending', 'active', 'disabled']
    identitySessionId: str | None = None


class DingTalkAuthConfig(BaseModel):
    configured: bool
    corpId: str
    clientId: str
    callbackPath: str


class DingTalkCodeInput(BaseModel):
    code: str = Field(min_length=1, max_length=4096)
