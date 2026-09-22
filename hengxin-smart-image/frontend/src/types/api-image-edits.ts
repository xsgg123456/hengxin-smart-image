export type ApiTaskState = 'queued' | 'running' | 'succeeded' | 'partial_failed' | 'failed' | 'uncertain'
export type ApiItemState = 'queued' | 'running' | 'retry_wait' | 'collecting' | 'succeeded' | 'failed' | 'uncertain'
export interface ApiPicture { fileId: string; name: string; url: string }
export interface ApiItem { id: string; position: number; source: ApiPicture; state: ApiItemState; retries: number; nextAttemptAt: string | null; result: ApiPicture | null; error: string | null }
export interface ApiTask {
  id: string; name: string; prompt: string; created: string; status: ApiTaskState
  material: ApiPicture; items: ApiItem[]; events: string[]; error: string | null
  metrics: { requestCount: number; retryCount: number; elapsedSeconds: number | null; queueSeconds?: number | null; generationSeconds?: number | null }
}
export interface ApiChannel { enabled: boolean; paused: boolean; reason: string | null }
export interface ApiTaskInput { name: string; prompt: string; originalFileIds: string[]; materialFileId: string }
export interface ApiTaskPage { items: ApiTask[]; total: number; page: number; pageSize: number }
export const taskLabels: Record<ApiTaskState, string> = { queued: '排队中', running: '处理中', succeeded: '全部成功', partial_failed: '部分失败', failed: '全部失败', uncertain: '需核实' }
export const itemLabels: Record<ApiItemState, string> = { queued: '等待处理', running: '处理中', retry_wait: '等待重试', collecting: '保存结果中', succeeded: '成功', failed: '失败', uncertain: '需核实' }
export const isTaskActive = (task: ApiTask) => ['queued', 'running', 'uncertain'].includes(task.status)
