import type { ManagementService } from './management'
/** 前端契约；传输字段统一 camelCase，时间使用 ISO 8601。 */
export type Mode = 'wallpaper' | 'product' | 'text'
export type Role = 'super_admin' | 'design_manager' | 'designer' | 'operator'
export type TaskState = '排队中' | '执行中' | '待查看' | '部分失败' | '失败'
export interface User {
  id: string
  name: string
  role: Role | null
  status: 'pending' | 'active' | 'disabled'
}
export interface FileRecord {
  id: string
  name: string
  mimeType: string
  size: number
  width: number
  height: number
  ownerId: string
  url: string
  urlExpiresAt: string | null
}
export interface Picture { name: string; url: string; version?: number; fileId?: string }
export interface SkillVersion {
  id: string
  name: string
  mode: Mode
  version: string
  checksum: string
  isDefault: boolean
  status: 'uploaded' | 'installing' | 'available' | 'disabled' | 'failed'
}
export interface Template {
  skillBinding?: 'module_default' | 'specific'
  id: string
  name: string
  mode: Mode
  images: Picture[]
  skill: string
  skillVersionId: string | null
  notes: string
  updatedAt: string
  active: boolean
  version: number
  ownerId: string
}
export interface Task {
  executionSource?: 'fixture' | 'unavailable' | 'cli'
  id: string
  name: string
  mode: Mode
  template: string
  templateId?: string
  templateVersion?: number
  templateSnapshot?: Template
  skillVersionId: string
  ownerId: string
  sessionId: string | null
  state: TaskState
  progress: number | null
  images: Picture[]
  sources: Picture[]
  feedback: string[]
  time: string
  archived: boolean
  currentRoundId: string
  sku?: string
  outputCount?: number
  error?: string | null
}
export interface Round {
  executionConfig?: { version: number; concurrency: number; timeoutSeconds: number }
  id: string
  taskId: string
  operatorId: string
  target: number | null
  note: string
  state: TaskState
  createdAt: string
  startedAt: string | null
  finishedAt: string | null
  error: string | null
}
export interface ImageVersion {
  id: string
  taskId: string
  roundId: string
  slot: number
  version: number
  fileId: string
  current: boolean
}
export interface Archive {
  id: string
  taskId?: string
  name: string
  mode: Mode
  images: Picture[]
  time: string
  ownerId: string
  imageVersionIds: string[]
}
export interface ExecutionAttempt {
  id: string
  roundId: string
  operatorId: string
  startedAt: string
  finishedAt: string | null
  state: TaskState | 'timeout'
  usage: { inputTokens: number; outputTokens: number } | null
}
export interface WorkerStatus {
  id: string
  checkedAt: string
  state: 'idle' | 'running' | 'unavailable' | 'unknown'
  queueSize: number
  runningCount: number
  concurrency: number
}
export interface SystemConfig {
  version: number
  concurrency: number
  timeoutSeconds: number
  maxUploadBytes: number
  defaultSkillIds: Record<Mode, string | null>
}
export interface PageQuery { page: number; pageSize: number; search?: string; mode?: Mode }
export interface PageResult<T> { items: T[]; page: number; pageSize: number; total: number }
export interface ApiErrorBody { code: string; message: string; requestId?: string }
export interface Accepted { taskId: string; roundId: string; state: '排队中' }
/** 过渡期工作区快照；Phase 2–4 逐页拆分页接口，不用作永久全量接口。 */
export interface Workspace { templates: Template[]; tasks: Task[]; archives: Archive[]; deletions?: DeletionReceipt[] }
export interface DeletionReceipt { id: string; operatorId: string; deletedAt: string; resourceType?: 'task' | 'archive' | 'template' }
export interface TaskQuery extends PageQuery { state?: TaskState | 'processing' | 'error' }
export interface TaskPage extends PageResult<Task> { stats: { total: number; processing: number; ready: number; archived: number } }
export interface ResultVersion extends Picture { id: string; version: number; roundId: string; createdAt: string }
export interface ResultSlot { slot: number; versions: ResultVersion[]; currentVersionId: string | null; error: string | null }
export interface ExecutionControl { canRevise: boolean; canRetry: boolean; blockedReason: string | null }
export interface TaskDetailData { task: Task; slots: ResultSlot[]; rounds: Round[]; executionControl: ExecutionControl }
export interface TemplateQuery extends PageQuery { sort?: 'updated' | 'name' | 'images'; activeOnly?: boolean }
export interface TemplateInput {
  id?: string
  name: string
  mode: Mode
  images: Picture[]
  skillVersionId: string | null
  active: boolean
  notes: string
  expectedVersion?: number
}
export interface CreateTaskInput {
  mode: Mode
  name: string
  templateId?: string
  templateVersion?: number
  skillVersionId?: string
  sku?: string
  sources: Picture[]
  note: string
}
export interface RevisionInput { taskId: string; target: number | null; note: string; retry?: boolean }
export interface HengxinService extends ManagementService {
  getUser(): Promise<User>
  getWorkspace(): Promise<Workspace>
  listTasks(query: TaskQuery): Promise<TaskPage>
  getTask(id: string): Promise<TaskDetailData>
  deleteTask(id: string): Promise<DeletionReceipt>
  listArchives(query: PageQuery): Promise<PageResult<Archive>>
  getArchive(id: string): Promise<Archive>
  listTemplates(query: TemplateQuery): Promise<PageResult<Template>>
  getTemplate(id: string): Promise<Template>
  getTemplateVersions(id: string): Promise<Template[]>
  listSkills(mode?: Mode): Promise<SkillVersion[]>
  uploadFile(file: File): Promise<Picture>
  saveTemplate(template: TemplateInput): Promise<Template>
  deleteTemplate(id: string): Promise<void>
  createTask(input: CreateTaskInput, idempotencyKey?: string): Promise<Accepted>
  revise(input: RevisionInput): Promise<Accepted>
  archive(taskId: string): Promise<Archive>
  deleteArchive(id: string): Promise<void>
  dispose(): void
}
