from pydantic import BaseModel


class ApiExecutionSettings(BaseModel):
    enabled: bool
    taskConcurrency: int
    imagesPerBatch: int
    requestTimeoutSeconds: int
    downloadTimeoutSeconds: int
    leaseSeconds: int
    model: str
    quality: str
    resolution: str
    imagesPerRequest: int
    sizePolicy: str


class CliExecutionSettings(BaseModel):
    enabled: bool
    concurrency: int
    capacity: int
    timeoutSeconds: int
    timeoutCapacity: int
    model: str
    reasoningEffort: str
    usesSkills: bool


class RetentionSettings(BaseModel):
    enabled: bool
    cacheIdleDays: int
    historyIdleDays: int


class ExecutionSettings(BaseModel):
    api: ApiExecutionSettings
    cli: CliExecutionSettings
    maxUploadBytes: int
    retention: RetentionSettings
