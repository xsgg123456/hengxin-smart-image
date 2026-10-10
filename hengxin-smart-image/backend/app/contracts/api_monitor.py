from typing import Literal
from pydantic import BaseModel


class WorkerObservation(BaseModel):
    id: str
    checkedAt: str
    state: Literal['available', 'unavailable', 'unknown']
    capacity: int | None


class QueueMetric(BaseModel):
    phase: str
    tasks: int | None
    images: int | None
    turns: int | None = None


class ChannelMonitor(BaseModel):
    channel: Literal['api', 'cli']
    state: Literal['available', 'unavailable', 'unknown']
    workers: list[WorkerObservation]
    queueState: Literal['available', 'unknown']
    metrics: list[QueueMetric]
    enabled: bool
    concurrencyLimit: int | None
    imagesPerBatch: int | None
    paused: bool | None = None
    pauseReason: str | None = None
    sharedActiveTurns: int | None = None
    otherActiveTurns: int | None = None


class MonitorIncident(BaseModel):
    taskId: str
    name: str
    channel: Literal['api', 'cli']
    phase: str
    images: int


class ApiMonitorReport(BaseModel):
    checkedAt: str
    channels: list[ChannelMonitor]
    incidents: list[MonitorIncident]
    incidentsTruncated: bool
