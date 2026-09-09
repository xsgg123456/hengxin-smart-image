/** Phase 1 前端契约；传输字段统一 camelCase，时间使用 ISO 8601。 */
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
  status: 'uploaded' | 'installing' | 'available' | 'disabled' | 'failed'
}
export interface Template {
  id: string
  name: string
  mode: Mode
  images: Picture[]
  skill: string
  active: boolean
  version: number
  ownerId: string
}
export interface Task {
  id: string
  name: string
  mode: Mode
  template: string
  templateId?: string
  templateVersion?: number
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
}
export interface Round {
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
export interface Workspace { templates: Template[]; tasks: Task[]; archives: Archive[] }
export interface CreateTaskInput {
  mode: Mode
  name: string
  templateId?: string
  sources: Picture[]
  note: string
}
export interface RevisionInput { taskId: string; target: number | null; note: string }
export interface HengxinService {
  getUser(): Promise<User>
  getWorkspace(): Promise<Workspace>
  saveTemplate(template: Template): Promise<Template>
  deleteTemplate(id: string): Promise<void>
  createTask(input: CreateTaskInput): Promise<Accepted>
  revise(input: RevisionInput): Promise<Accepted>
  archive(taskId: string): Promise<Archive>
  deleteArchive(id: string): Promise<void>
  dispose(): void
}
