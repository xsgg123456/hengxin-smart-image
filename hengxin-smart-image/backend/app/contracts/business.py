from .fields import omitted
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field, field_validator
from uuid import UUID

Mode = Literal['wallpaper', 'product', 'text']
Role = Literal['super_admin', 'design_manager', 'designer', 'operator']
TaskState = Literal['排队中', '执行中', '待查看', '部分失败', '失败']
T = TypeVar('T')


class ApiErrorBody(BaseModel):
    code: str
    message: str
    requestId: str = omitted()


class PageQuery(BaseModel):
    page: int = Field(default=1, ge=1)
    pageSize: int = Field(default=20, ge=1, le=100)
    search: str = omitted()
    mode: Mode = omitted()


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


class Picture(BaseModel):
    name: str
    url: str
    version: int = omitted()
    fileId: str = omitted()


class SkillVersion(BaseModel):
    id: str
    name: str
    mode: Mode
    version: str
    checksum: str
    isDefault: bool
    status: Literal['uploaded', 'installing', 'available', 'disabled', 'failed']


class Template(BaseModel):
    skillBinding: Literal['module_default', 'specific'] = omitted()
    id: str
    name: str
    mode: Mode
    images: list[Picture]
    skill: str
    skillVersionId: str | None
    notes: str
    updatedAt: str
    active: bool
    version: int
    ownerId: str


class ExecutionConfig(BaseModel):
    version: int
    concurrency: int
    timeoutSeconds: int


class Round(BaseModel):
    executionConfig: ExecutionConfig = omitted()
    id: str
    taskId: str
    operatorId: str
    target: int | None
    note: str
    state: TaskState
    createdAt: str
    startedAt: str | None
    finishedAt: str | None
    error: str | None


class Task(BaseModel):
    executionSource: Literal['fixture', 'unavailable', 'cli'] = omitted()
    id: str
    name: str
    mode: Mode
    template: str
    templateId: str = omitted()
    templateVersion: int = omitted()
    templateSnapshot: Template = omitted()
    skillVersionId: str
    ownerId: str
    sessionId: str | None
    state: TaskState
    progress: float | None
    images: list[Picture]
    sources: list[Picture]
    feedback: list[str]
    time: str
    archived: bool
    currentRoundId: str
    sku: str = omitted()
    outputCount: int = omitted()
    error: str | None = None


class Archive(BaseModel):
    id: str
    taskId: str = omitted()
    name: str
    mode: Mode
    images: list[Picture]
    time: str
    ownerId: str
    imageVersionIds: list[str]


class DeletionReceipt(BaseModel):
    id: str
    operatorId: str
    deletedAt: str
    resourceType: Literal['task', 'archive', 'template'] = omitted()


class Workspace(BaseModel):
    templates: list[Template]
    tasks: list[Task]
    archives: list[Archive]
    deletions: list[DeletionReceipt] = omitted()


class TaskStats(BaseModel):
    total: int
    processing: int
    ready: int
    archived: int


class TaskPage(PageResult[Task]):
    stats: TaskStats


class ResultVersion(Picture):
    id: str
    version: int
    roundId: str
    createdAt: str


class ResultSlot(BaseModel):
    slot: int
    versions: list[ResultVersion]
    currentVersionId: str | None
    error: str | None


class ExecutionControl(BaseModel):
    canRevise: bool
    canRetry: bool
    blockedReason: str | None


class TaskDetailData(BaseModel):
    executionControl: ExecutionControl
    task: Task
    slots: list[ResultSlot]
    rounds: list[Round]


class TemplateQuery(PageQuery):
    sort: Literal['updated', 'name', 'images'] = omitted()
    activeOnly: bool = omitted()


class TaskQuery(PageQuery):
    state: Literal['排队中', '执行中', '待查看', '部分失败', '失败', 'processing', 'error'] = omitted()


class TemplateInput(BaseModel):
    id: str = omitted()
    name: str = Field(min_length=1)
    mode: Mode
    images: list[Picture]
    skillVersionId: str | None
    active: bool
    notes: str
    expectedVersion: int = omitted()


class CreateTaskInput(BaseModel):
    mode: Mode
    name: str = Field(min_length=1)
    templateId: str = omitted()
    templateVersion: int = omitted()
    skillVersionId: str = omitted()
    sku: str = omitted()
    sources: list[Picture]
    note: str


class RevisionInput(BaseModel):
    taskId: str
    target: int | None = Field(ge=0, strict=True)
    note: str = Field(max_length=1000)
    retry: bool = omitted()
    sourceRoundId: str = omitted()

    @field_validator('taskId', 'sourceRoundId')
    @classmethod
    def valid_uuid(cls, value):
        return str(UUID(value))


class Accepted(BaseModel):
    taskId: str
    roundId: str
    state: Literal['排队中']
