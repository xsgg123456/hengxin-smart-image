"""Public execution view; no raw model messages, paths or credentials."""
from typing import Literal
from pydantic import BaseModel, Field

Stage = Literal['queued', 'preparing', 'starting', 'generating', 'validating', 'storing',
                'publishing', 'completed', 'failed', 'cancelled', 'uncertain']


class ProcessEvent(BaseModel):
    sequence: int
    stage: Stage
    message: str
    at: str | None


class SlotFailure(BaseModel):
    slot: int
    code: str
    message: str


class Failure(BaseModel):
    code: str
    message: str
    action: str
    stage: Stage
    slotErrors: list[SlotFailure] = Field(default_factory=list)


class ExecutionView(BaseModel):
    taskId: str
    roundId: str
    status: str
    source: Literal['cli', 'fixture', 'unavailable']
    diagnosticId: str | None
    stage: Stage
    label: str
    startedAt: str | None
    finishedAt: str | None
    updatedAt: str | None
    lastActivityAt: str | None
    totalImages: int
    detectedImages: int | None
    legacy: bool
    events: list[ProcessEvent]
    failure: Failure | None
