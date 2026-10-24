import { createIdentityRequest, IdentityError, record } from '../identity/request'

export interface StudioOutput { id: string; name: string; contentType: string; sizeBytes: number; url: string }
export interface RecoverableFile { id: string; name: string; path: string; source: 'work' | 'native' | 'snapshot'; sizeBytes: number; version: string }
export interface RecoverableFiles { items: RecoverableFile[]; busy: boolean }
export interface RecoveryResult { saved: { id: string; kind: 'picture' | 'file' }[]; errors: { id: string; name: string; message: string }[] }
const strings = (value: Record<string, unknown>, keys: string[]) => keys.every(key => typeof value[key] === 'string')
const size = (value: unknown) => Number.isSafeInteger(value) && Number(value) >= 0
export function isStudioOutput(value: unknown, taskId: string): value is StudioOutput {
  return record(value) && strings(value, ['id', 'name', 'contentType']) && size(value.sizeBytes)
    && value.url === `/api/overseas/v1/tasks/${encodeURIComponent(taskId)}/studio/outputs/${encodeURIComponent(String(value.id))}/content`
}
export function isRecoverableFiles(value: unknown): value is RecoverableFiles {
  return record(value) && typeof value.busy === 'boolean' && Array.isArray(value.items)
    && value.items.every(item => record(item) && strings(item, ['id', 'name', 'path', 'version']) && size(item.sizeBytes) && ['work', 'native', 'snapshot'].includes(String(item.source)))
    && new Set(value.items.map(item => item.id)).size === value.items.length
}
export function isRecoveryResult(value: unknown): value is RecoveryResult {
  return record(value) && Array.isArray(value.saved) && Array.isArray(value.errors)
    && value.saved.every(item => record(item) && strings(item, ['id']) && ['picture', 'file'].includes(String(item.kind)))
    && value.errors.every(item => record(item) && strings(item, ['id', 'name', 'message']))
}
export function createStudioOutputsApi(fetcher: typeof fetch = fetch) {
  function request(signal?: AbortSignal) {
    return createIdentityRequest((url, options) => fetcher(url, { ...options, cache: 'no-store', signal: signal && options?.signal ? AbortSignal.any([signal, options.signal]) : signal || options?.signal }))
  }
  const base = (taskId: string, conversationId: string) => `/api/overseas/v1/tasks/${encodeURIComponent(taskId)}/studio/conversations/${encodeURIComponent(conversationId)}`
  return {
    list: (taskId: string, conversationId: string, signal?: AbortSignal) => request(signal)(`${base(taskId, conversationId)}/recoverable-files`, isRecoverableFiles, undefined, { timeoutMs: 35000 }),
    recover: (taskId: string, conversationId: string, files: Pick<RecoverableFile, 'id' | 'version'>[], signal?: AbortSignal) => {
      if (!files.length || files.length > 100) throw Error('请选择 1–100 个文件')
      return request(signal)(`${base(taskId, conversationId)}/recover-files`, isRecoveryResult, { files }, { timeoutMs: 120000 })
    }
  }
}
export function recoveryError(reason: unknown) {
  if (reason instanceof IdentityError && typeof reason.detail === 'string') return reason.detail
  return reason instanceof Error ? reason.message : '文件取回失败，请重试'
}
