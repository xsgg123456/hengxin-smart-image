export type ApiTaskState = 'queued' | 'running' | 'succeeded' | 'partial_failed' | 'failed' | 'uncertain'
export type ApiItemState = 'queued' | 'running' | 'retry_wait' | 'collecting' | 'succeeded' | 'failed' | 'uncertain'
export interface ApiPicture { fileId: string; name: string; url: string; width?: number; height?: number }
export type ApiOperationKind = 'generation' | 'revision' | 'text_edit' | 'text_repair'
export const operationLabel = (kind?: ApiOperationKind) => kind === 'text_repair' ? '修复文案' : kind === 'text_edit' ? '文字修改' : kind === 'generation' ? '初始生成' : '修改'
export interface ApiVersion { kind?: ApiOperationKind; number: number; picture: ApiPicture; created: string; operator: string; text: string; annotation: ApiPicture | null; baseVersion: number | null }
export interface ApiRevision { kind?: ApiOperationKind; state: ApiItemState; text: string; annotation: ApiPicture | null; operator: string; baseVersion: number; retries: number; error: string | null }
export interface ApiRevisionInput { kind?: 'text_edit' | 'text_repair'; prompt?: string; baseVersion: number; text: string; annotationFileId?: string | null }
export interface ApiItem { currentVersion: number | null; versions: ApiVersion[]; revision: ApiRevision | null; id: string; position: number; source: ApiPicture | null; state: ApiItemState; retries: number; nextAttemptAt: string | null; result: ApiPicture | null; error: string | null }
export interface ApiTask {
  id: string; name: string; prompt: string; created: string; status: ApiTaskState
  operator: string; batch: { current: number; total: number; running: number }
  material: ApiPicture | null; items: ApiItem[]; events: string[]; error: string | null
  metrics: { requestCount: number; retryCount: number; elapsedSeconds: number | null; queueSeconds?: number | null; generationSeconds?: number | null }
}
export interface ApiChannel { enabled: boolean; paused: boolean; reason: string | null }
export interface ApiTaskInput { name: string; prompt: string; originalFileIds: string[]; materialFileId: string }
export interface ApiTaskSummary {
  id: string; name: string; created: string; status: ApiTaskState; operator: string
  cover: ApiPicture | null; counts: { total: number; success: number; failed: number; uncertain: number }
  batch: { current: number; total: number; running: number }
}
export interface ApiTaskPage { items: ApiTaskSummary[]; total: number; page: number; pageSize: number }
export const taskLabels: Record<ApiTaskState, string> = { queued: '排队中', running: '处理中', succeeded: '全部成功', partial_failed: '部分失败', failed: '全部失败', uncertain: '需核实' }
export const itemLabels: Record<ApiItemState, string> = { queued: '等待处理', running: '处理中', retry_wait: '等待重试', collecting: '保存结果中', succeeded: '成功', failed: '失败', uncertain: '需核实' }
export const isTaskActive = (task: Pick<ApiTask, 'status'>) => ['queued', 'running', 'uncertain'].includes(task.status)
