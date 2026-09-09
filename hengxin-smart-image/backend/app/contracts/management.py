from .fields import omitted
from typing import Literal
from pydantic import BaseModel
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
    queueSize: int
    runningCount: int
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
    installedAt: str | None
    node: str | None
    updatedAt: str
    error: str | None
    referenced: bool


class SkillStatusInput(BaseModel):
    status: Literal['available', 'disabled']


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
    dingtalk: DingTalkConfig
    audit: list[SettingsAudit]


class SettingsInput(SystemConfig):
    dingtalk: DingTalkInput
