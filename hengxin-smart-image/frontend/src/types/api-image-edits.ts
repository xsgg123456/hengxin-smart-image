export type ApiTaskState = 'queued' | 'running' | 'succeeded' | 'partial_failed' | 'failed' | 'uncertain'
export type ApiItemState = 'queued' | 'running' | 'retry_wait' | 'collecting' | 'succeeded' | 'failed' | 'uncertain'
export type CliActivity = 'idle' | 'queued' | 'running' | 'uncertain'
export interface ApiTaskActivity {
  cliActivity?: CliActivity
  canDelete?: boolean; deleteBlockedReason?: string | null
  deletionState?: 'idle' | 'deleting' | 'failed'; deletionError?: string | null
}
export interface ApiDeletion { state: 'deleted' | 'deleting' | 'failed'; message: string | null }
export interface ApiPicture { fileId: string; name: string; url: string; width?: number; height?: number }
export type ApiOperationKind = 'generation' | 'revision' | 'image_edit' | 'text_edit' | 'text_repair'
export const operationLabel = (kind?: ApiOperationKind) => kind === 'image_edit' ? '图片修改' : kind === 'text_repair' ? '修复文案' : kind === 'text_edit' ? '文字修改' : kind === 'generation' ? '初始生成' : '修改'
export interface ApiVersion { kind?: ApiOperationKind; number: number; picture: ApiPicture; created: string; operator: string; text: string; annotation: ApiPicture | null; baseVersion: number | null }
export interface ApiRevision { kind?: ApiOperationKind; state: ApiItemState; text: string; annotation: ApiPicture | null; operator: string; baseVersion: number; retries: number; error: string | null }
export interface ApiRevisionInput { kind?: 'image_edit' | 'text_edit' | 'text_repair'; prompt?: string; baseVersion: number; text: string; annotationFileId?: string | null }
export interface ApiRetry { cycleId: string | null; attempts: number; maxAttempts: number; startedAt: string | null; deadlineAt: string | null; nextAttemptAt: string | null; stopRequested: boolean; canStop: boolean; reason: string | null }
export interface ApiItem { retry?: ApiRetry; cliActivity?: CliActivity; currentVersion: number | null; versions: ApiVersion[]; revision: ApiRevision | null; id: string; position: number; source: ApiPicture | null; state: ApiItemState; retries: number; nextAttemptAt: string | null; result: ApiPicture | null; error: string | null }
export interface ApiTask extends ApiTaskActivity {
  id: string; name: string; prompt: string; created: string; status: ApiTaskState
  operator: string; batch: { current: number; total: number; running: number }
  material: ApiPicture | null; items: ApiItem[]; events: string[]; error: string | null
  metrics: { requestCount: number; retryCount: number; elapsedSeconds: number | null; queueSeconds?: number | null; generationSeconds?: number | null }
}
export interface ApiChannel { enabled: boolean; paused: boolean; reason: string | null; cooldownUntil?: string | null; recovering?: boolean }
export interface ApiTaskInput { name: string; prompt: string; originalFileIds: string[]; materialFileId: string }
export interface ApiTaskSummary extends ApiTaskActivity {
  creatorId?: string
  id: string; name: string; created: string; status: ApiTaskState; operator: string
  cover: ApiPicture | null; counts: { total: number; success: number; failed: number; uncertain: number }
  batch: { current: number; total: number; running: number }
}
export interface ApiRecordsStats { tasks: number; pendingTasks: number; successImages: number; failedImages: number }
export interface ApiTaskCreator { id: string; name: string }
export interface ApiRecordsQuery { page: number; pageSize: number; search: string; status: ApiTaskState | ''; scope?: 'mine' | 'all'; creatorId?: string; dateFrom?: string; dateTo?: string }
export interface ApiTaskPage { items: ApiTaskSummary[]; total: number; page: number; pageSize: number; stats?: ApiRecordsStats }
export const taskLabels: Record<ApiTaskState, string> = { queued: '等待中', running: '处理中', succeeded: '已完成', partial_failed: '部分未完成', failed: '未完成', uncertain: '等待结果' }
export const itemLabels: Record<ApiItemState, string> = { queued: '等待中', running: '生成中', retry_wait: '重试中', collecting: '保存中', succeeded: '已完成', failed: '未完成', uncertain: '生成中' }
export const isApiTaskPending = (task: Pick<ApiTask, 'status'>) => ['queued', 'running', 'uncertain'].includes(task.status)
export const isTaskActive = (task: Pick<ApiTask, 'status'> & ApiTaskActivity) => isApiTaskPending(task) || (!!task.cliActivity && task.cliActivity !== 'idle') || task.deletionState === 'deleting'
export const cliActivityLabel = (state?: CliActivity) => state === 'queued' ? '等待修改' : state === 'running' || state === 'uncertain' ? '图片修改中' : ''
export const deleteBlockedReason = (task: Pick<ApiTask, 'status'> & ApiTaskActivity) => task.deletionState === 'deleting' ? '正在永久删除任务及关联资料' : task.deleteBlockedReason || (isTaskActive(task) ? '任务仍在执行或结果待核实，暂不可删除' : task.canDelete !== true ? '尚未确认任务可删除，请刷新或更新服务后重试' : '')
export const canDeleteTask = (task: Pick<ApiTask, 'status'> & ApiTaskActivity) => !deleteBlockedReason(task)
