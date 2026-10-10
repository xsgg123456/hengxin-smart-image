"""API image business reporting, independent of legacy task-center contracts."""
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal['task_created', 'api_request', 'cli_submission', 'cli_round',
                   'cli_candidate', 'version_published', 'adopt', 'restore']
GenerationType = Literal['initial', 'api_edit', 'cli_edit']


class UsageQuery(BaseModel):
    from_: str | None = Field(default=None, alias='from')
    to: str | None = None
    userId: str | None = None
    unassigned: bool = False
    category: Category | None = None
    generationType: GenerationType | None = None
    outputsOnly: bool = False
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=20, ge=1, le=100)


class Summary(BaseModel):
    initialImages: int = 0
    modifiedImages: int = 0
    totalGeneratedImages: int = 0
    generatedTasks: int = 0
    tasksCreated: int = 0
    apiAttempts: int = 0
    apiSucceeded: int = 0
    apiFailed: int = 0
    apiUnknown: int = 0
    apiRunning: int = 0
    apiRetries: int = 0
    apiRetryUnknown: int = 0
    cliSubmitted: int = 0
    cliStarted: int = 0
    cliUnverified: int = 0
    cliSucceeded: int = 0
    cliFailed: int = 0
    cliUnknown: int = 0
    cliCandidates: int = 0
    generatedVersions: int = 0
    unverifiedVersions: int = 0
    adoptions: int = 0
    restores: int = 0
    unverifiedAttribution: int = 0
    requestSuccessRate: float | None = None
    inputTokens: int | None = None
    outputTokens: int | None = None
    cost: float | None = None


class Inventory(BaseModel):
    tasks: int
    sourceImages: int
    withResultImages: int
    succeededImages: int
    failedImages: int
    pendingImages: int
    uncertainImages: int
    deliverySuccessRate: float | None


class Event(BaseModel):
    id: str
    category: Category
    channel: str
    kind: str
    taskId: str
    taskName: str
    taskDeleted: bool
    creatorId: str
    operatorId: str | None
    operatorName: str
    occurredAt: str
    completedAt: str | None
    state: str
    quantity: int
    generationType: GenerationType | None
    generatedImages: int
    isRetry: bool | None
    attribution: Literal['verified', 'historical_unverified']
    durationSeconds: float | None


class DailyRow(BaseModel):
    date: str
    userId: str | None
    userName: str
    summary: Summary


class UserOption(BaseModel):
    id: str
    name: str


class Report(BaseModel):
    scope: Literal['all', 'personal']
    timezone: Literal['Asia/Shanghai'] = 'Asia/Shanghai'
    users: list[UserOption]
    inventory: Inventory
    summary: Summary
    rows: list[DailyRow]
    events: list[Event]
    total: int
    page: int
    pageSize: int
