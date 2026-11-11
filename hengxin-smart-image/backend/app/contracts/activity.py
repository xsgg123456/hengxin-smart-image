"""Read-only domestic activity, keeping outputs separate from executions."""
from typing import Literal

from pydantic import BaseModel, Field
from app.contracts.api_usage import GenerationType, UserOption

Status = Literal['queued', 'running', 'retry_wait', 'collecting', 'cancelling',
                 'uncertain', 'failed', 'succeeded', 'cancelled', 'unknown']


class ActivityQuery(BaseModel):
    view: Literal['people', 'jobs'] = 'people'
    userId: str | None = None
    unassigned: bool = False
    from_: str | None = Field(default=None, alias='from')
    to: str | None = None
    generationType: GenerationType | None = None
    status: Literal['queued', 'running', 'uncertain', 'failed', 'succeeded', 'cancelled', 'unknown'] | None = None
    keyword: str = Field(default='', max_length=200)
    currentOnly: bool = False
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=20, ge=1, le=100)


class Summary(BaseModel):
    images: int | None = 0
    api: int = 0
    cli: int = 0


class Person(Summary):
    id: str | None
    name: str
    latest: str | None


class Record(BaseModel):
    id: str
    taskId: str
    task: str
    personId: str | None
    person: str
    kind: GenerationType | None
    status: Status
    createdAt: str
    startedAt: str | None
    finishedAt: str | None
    images: int | None
    seconds: float | None
    retry: bool | None
    error: str
    taskDeleted: bool
    current: bool = False


class Live(BaseModel):
    queued: int = 0
    running: int = 0
    uncertain: int = 0
    failed: int = 0


class Report(BaseModel):
    scope: Literal['all'] = 'all'
    checkedAt: str
    users: list[UserOption]
    people: list[Person]
    records: list[Record]
    total: int
    page: int
    pageSize: int
    summary: Summary
    live: Live
