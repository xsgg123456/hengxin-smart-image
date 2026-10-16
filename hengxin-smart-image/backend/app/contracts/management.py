from .fields import omitted
from typing import Literal
from pydantic import BaseModel, Field
from .business import PageQuery, Role, User


class UserOption(BaseModel):
    id: str
    name: str


class ManagedUser(User):
    department: str
    lastLoginAt: str | None


class UserQuery(PageQuery):
    directory: Literal['members', 'legacy'] = 'members'
    status: Literal['pending', 'active', 'disabled'] = omitted()
    role: Role = omitted()


class UserInput(BaseModel):
    id: str
    role: Role | None
    status: Literal['pending', 'active', 'disabled']


class SystemConfig(BaseModel):
    version: int
    concurrency: int
    timeoutSeconds: int
    maxUploadBytes: int


class SettingsAudit(BaseModel):
    id: str
    operatorId: str
    operatorName: str
    changedAt: str
    version: int
    fields: list[str]


class DingTalkInput(BaseModel):
    corpId: str
    appId: str
    callbackDomain: str


class DingTalkConfig(DingTalkInput):
    state: Literal['unconfigured', 'ready', 'error']


class ManagedSettings(SystemConfig):
    capacity: int
    timeoutCapacity: int
    dingtalk: DingTalkConfig
    audit: list[SettingsAudit]


class SettingsInput(SystemConfig):
    version: int = Field(ge=1, strict=True)
    concurrency: int = Field(ge=1, le=10, strict=True)
    timeoutSeconds: int = Field(ge=60, le=7200, strict=True)
    maxUploadBytes: int = Field(ge=1024**2, le=10 * 1024**2, strict=True)
    dingtalk: DingTalkInput
