import { ApiError, createRequest } from './hengxin/http'
import type { ApiTaskInput, ApiTaskState } from '../types/api-image-edits'
import * as valid from './api-image-edits-validate'
export const apiImageDemo = ['demo', 'mock'].includes(import.meta.env?.MODE || '')
export function createApiImageClient(baseUrl: string, fetcher: typeof fetch = fetch) {
  const root = `${baseUrl.replace(/\/$/, '')}/api-image-edits`
  const request = createRequest(root, fetcher)
  const path = (id: string) => `/tasks/${encodeURIComponent(id)}`
  return {
    status: () => request('/status', valid.channel),
    upload: (file: File) => { const body = new FormData(); body.append('file', file); return request('/files', valid.picture, 'POST', body, 60000) },
    deleteFile: (id: string) => request(`/files/${encodeURIComponent(id)}`, (v): v is void | { deleted: true } => valid.empty(v) || valid.deleted(v), 'DELETE'),
    create: (input: ApiTaskInput, key: string) => request('/tasks', valid.accepted, 'POST', input, 10000, { 'Idempotency-Key': key }),
    list: (query: { page: number; pageSize: number; search: string; status: ApiTaskState | '' }) => request(`/tasks?${new URLSearchParams(Object.entries(query).map(([key, value]) => [key, String(value)]))}`, valid.page),
    task: async (id: string) => { const task = await request(path(id), valid.task); task.items.sort((a, b) => a.position - b.position); return task },
    retry: (id: string, key: string) => request(`${path(id)}/retry`, valid.accepted, 'POST', undefined, 10000, { 'Idempotency-Key': key }),
    remove: (id: string) => request(path(id), valid.deleted, 'DELETE'),
    resume: () => request('/channel/resume', valid.resumed, 'POST'),
    resolve: (id: string) => request(`${path(id)}/resolve`, valid.accepted, 'POST', { confirmedStopped: true }),
    download: async (id: string) => {
      let response: Response
      try { response = await fetcher(`${root}/files/${encodeURIComponent(id)}/content?download=true`, { credentials: 'include', signal: AbortSignal.timeout(60000) }) }
      catch { throw new ApiError('UNAVAILABLE', '下载连接失败，请重试') }
      if (response.status === 401 && typeof window !== 'undefined') window.dispatchEvent(new Event('hengxin:unauthorized'))
      if (!response.ok) throw new ApiError('DOWNLOAD_FAILED', `下载失败（${response.status}）`, response.status)
      if (!response.headers.get('content-type')?.startsWith('image/')) throw new ApiError('INVALID_RESPONSE', '下载内容不是图片')
      return response.blob()
    }
  }
}
export const apiImages = createApiImageClient(import.meta.env?.VITE_API_URL || '/api/v1')
export const errorText = (error: unknown) => error instanceof Error ? error.message : '操作失败，请重试'
export const uncertainResponse = (error: unknown) => !(error instanceof ApiError) || !error.status || error.status >= 500 || error.status === 408
