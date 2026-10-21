"""Read-only retention management wire contract."""
from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field

Result = Literal['cache_cleared', 'complete', 'objects_pending', 'retry', 'protected', 'waiting', 'due', 'processing']


class RetentionRow(BaseModel):
    id: str
    resourceId: str
    taskId: str | None
    taskName: str
    imagePosition: int
    kind: Literal['cache', 'history']
    result: Result
    processedAt: datetime | None
    lastActivityAt: datetime
    dueAt: datetime
    nextAttemptAt: datetime | None
    detail: str
    turnsRemoved: int = Field(ge=0)
    objectsRemoved: int = Field(ge=0)
    objectsPending: int = Field(ge=0)
    taskDeleted: bool
    detailTab: Literal['history', 'pending']


class RetentionPage(BaseModel):
    items: list[RetentionRow]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    pageSize: int = Field(ge=1, le=100)


class RetentionPolicy(BaseModel):
    enabled: bool
    cacheIdleHours: Literal[24]
    historyIdleHours: Literal[72]
    batchSize: int = Field(ge=1, le=25)
    scanIntervalSeconds: Literal[3600]
    detailRetentionDays: Literal[90]


class RetentionServiceState(BaseModel):
    state: Literal['online', 'offline', 'unknown', 'disabled']
    heartbeatAt: datetime | None
    scanState: Literal['running', 'completed', 'failed', 'unknown']
    lastStartedAt: datetime | None
    lastFinishedAt: datetime | None
    nextScanAt: datetime | None


class RetentionCounts(BaseModel):
    cacheToday: int | None = Field(ge=0)
    cacheTotal: int | None = Field(ge=0)
    historyToday: int | None = Field(ge=0)
    historyTotal: int | None = Field(ge=0)
    retry: int | None = Field(ge=0)
    overdue: int | None = Field(ge=0)
    protected: int | None = Field(ge=0)
    objectsPending: int | None = Field(ge=0)


class RetentionSummary(BaseModel):
    checkedAt: datetime
    policy: RetentionPolicy
    service: RetentionServiceState
    statisticsSince: datetime | None
    counts: RetentionCounts
