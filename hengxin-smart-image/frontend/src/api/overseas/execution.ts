import { createIdentityRequest, IdentityError, record } from '../identity/request'

export const executionStatuses = { queued: '等待执行', running: '正在执行', collecting: '正在校验产物', cancelling: '正在停止执行', uncertain: '执行状态待核实', succeeded: '执行完成', failed: '执行失败', cancelled: '执行已取消' }
export const executionKinds = { analysis: '方案分析', reanalysis: '重新分析', generation: '图片生成', revision: '图片返工' }
export interface ExecutionJob {
  id: string; taskId: string; kind: keyof typeof executionKinds; status: keyof typeof executionStatuses; version: number
  error: string | null; createdAt: string; startedAt: string | null; completedAt: string | null
}
export interface ExecutionEvent { id: number; jobId: string; status: keyof typeof executionStatuses; message: string; createdAt: string }
export interface ExecutionEvents { items: ExecutionEvent[]; cursor: number }
const text = (v: unknown): v is string => typeof v === 'string'
const integer = (v: unknown): v is number => Number.isSafeInteger(v) && Number(v) >= 0
const nullableText = (v: unknown) => v === null || text(v)
export function isExecutionJob(v: unknown): v is ExecutionJob {
  return record(v) && text(v.id) && text(v.taskId) && text(v.kind) && Object.hasOwn(executionKinds, v.kind)
    && text(v.status) && Object.hasOwn(executionStatuses, v.status) && integer(v.version) && v.version > 0
    && nullableText(v.error) && text(v.createdAt) && nullableText(v.startedAt) && nullableText(v.completedAt)
}
export function isExecutionEvents(v: unknown): v is ExecutionEvents {
  return record(v) && integer(v.cursor) && Array.isArray(v.items) && v.items.every((e, i, items) => record(e)
    && integer(e.id) && e.id > 0 && (i === 0 || e.id > items[i - 1].id) && e.id <= Number(v.cursor)
    && text(e.jobId) && text(e.status) && Object.hasOwn(executionStatuses, e.status) && text(e.message) && text(e.createdAt))
    && (!v.items.length || v.cursor === v.items[v.items.length - 1].id)
}
export function createExecutionApi(fetcher: typeof fetch = fetch) {
  const request = (signal?: AbortSignal) => createIdentityRequest((url, options) => fetcher(url, { ...options, signal: signal && options?.signal ? AbortSignal.any([signal, options.signal]) : options?.signal, cache: 'no-store' }))
  const base = '/api/overseas/v1'
  return {
    async jobs(taskId: string, signal?: AbortSignal) {
      const value = await request(signal)(`${base}/tasks/${encodeURIComponent(taskId)}/jobs`, (v): v is { items: ExecutionJob[] } => record(v) && Array.isArray(v.items) && v.items.every(e => isExecutionJob(e) && e.taskId === taskId))
      return value.items
    },
    async events(taskId: string, after: number, signal?: AbortSignal) {
      return request(signal)(`${base}/tasks/${encodeURIComponent(taskId)}/execution-events`, (v): v is ExecutionEvents => isExecutionEvents(v) && v.cursor >= after && v.items.every(e => e.id > after) && (v.items.length > 0 || v.cursor === after), undefined, { params: { after } })
    },
    cancel: (id: string, version: number) => request()(`${base}/jobs/${encodeURIComponent(id)}/cancel`, (v): v is ExecutionJob => isExecutionJob(v) && v.id === id, { version })
  }
}
export function executionError(reason: unknown) {
  if (reason instanceof IdentityError && reason.status === 409) return '执行状态已变化，已重新读取，请核对后操作。'
  return reason instanceof Error ? reason.message : '执行状态读取失败，请重试'
}
