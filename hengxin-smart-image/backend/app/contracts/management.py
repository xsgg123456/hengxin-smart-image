from .fields import omitted
from typing import Literal
from pydantic import BaseModel, Field, field_validator
from app.core.semver import validate_semver
from .business import Mode, PageQuery, Role, SkillVersion, User


class UsageQuery(BaseModel):
    from_: str = omitted(alias='from')
    to: str = omitted()
    userId: str = omitted()
    mode: Mode = omitted()


class TokenUsage(BaseModel):
    inputTokens: int
    outputTokens: int


class UsageAttempt(BaseModel):
    id: str
    taskId: str
    taskName: str
    creatorId: str
    operatorId: str
    operatorName: str
    mode: Mode
    kind: Literal['initial', 'single', 'whole']
    startedAt: str
    finishedAt: str | None
    state: Literal['running', 'success', 'partial', 'failed', 'timeout']
    outputImages: int
    queueSeconds: float
    durationSeconds: float | None
    usage: TokenUsage | None


class UsageSummary(BaseModel):
    tasks: int
    attempts: int
    initial: int
    single: int
    whole: int
    running: int
    success: int
    partial: int
    failed: int
    timeout: int
    outputImages: int
    successRate: float | None
    inputTokens: int | None
    outputTokens: int | None
    averageQueueSeconds: float | None
    averageDurationSeconds: float | None


class UsageRow(BaseModel):
    date: str
    userId: str
    userName: str
    summary: UsageSummary
    details: list[UsageAttempt]


class UserOption(BaseModel):
    id: str
    name: str


class UsageReport(BaseModel):
    scope: Literal['personal', 'all']
    timezone: Literal['Asia/Shanghai']
    summary: UsageSummary
    rows: list[UsageRow]
    users: list[UserOption]


class WorkerStatus(BaseModel):
    id: str
    checkedAt: str
    state: Literal['idle', 'running', 'unavailable', 'unknown']
    queueSize: int
    runningCount: int
    concurrency: int


class MonitorTask(BaseModel):
    taskId: str
    name: str
    operatorName: str
    state: str
    sessionId: str | None
    elapsedSeconds: float | None
    error: str | None


class DependencyStatus(BaseModel):
    name: str
    state: Literal['available', 'unavailable', 'unknown']
    message: str


class MonitorDetail(BaseModel):
    workers: list[WorkerStatus]
    cliVersion: str | None
    configured: bool | None
    lastResult: str | None
    dependencies: list[DependencyStatus]
    freeDiskBytes: int | None


class Issue(BaseModel):
    code: str
    message: str


class MonitorReport(BaseModel):
    issue: Issue = omitted()
    checkedAt: str | None
    state: Literal['idle', 'running', 'unavailable', 'unknown']
    queueSize: int | None
    runningCount: int | None
    taskCount: int | None
    tasks: list[MonitorTask]
    detail: MonitorDetail | None


class ManagedUser(User):
    department: str
    lastLoginAt: str | None


class UserQuery(PageQuery):
    status: Literal['pending', 'active', 'disabled'] = omitted()
    role: Role = omitted()


class UserInput(BaseModel):
    id: str
    role: Role | None
    status: Literal['pending', 'active', 'disabled']


class ManagedSkill(SkillVersion):
    sourceType: Literal['zip', 'local']
    description: str
    installedAt: str | None
    node: str | None
    updatedAt: str
    error: str | None
    referenced: bool


class SkillStatusInput(BaseModel):
    status: Literal['available', 'disabled']


class SkillRegisterInput(BaseModel):
    name: str = Field(min_length=1, max_length=100, pattern=r'^[a-zA-Z0-9][a-zA-Z0-9_-]*$')
    mode: Mode
    version: str = Field(max_length=100)
    description: str = Field(default='', max_length=2000)

    @field_validator('version')
    @classmethod
    def valid_version(cls, value):
        return validate_semver(value)


class DefaultSkillIds(BaseModel):
    wallpaper: str | None
    product: str | None
    text: str | None


class SystemConfig(BaseModel):
    version: int
    concurrency: int
    timeoutSeconds: int
    maxUploadBytes: int
    defaultSkillIds: DefaultSkillIds


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
