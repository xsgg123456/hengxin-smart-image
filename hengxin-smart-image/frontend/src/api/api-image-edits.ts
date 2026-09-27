import { readIdentityBlob } from './hengxin/identity-download'
import { ApiError, createRequest } from './hengxin/http'
import type { ApiTaskInput, ApiTaskState, ApiRevisionInput } from '../types/api-image-edits'
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
    list: (query: { page: number; pageSize: number; search: string; status: ApiTaskState | '' }) => request(`/tasks?${new URLSearchParams(Object.entries({ ...query, view: 'summary' }).map(([key, value]) => [key, String(value)]))}`, valid.page),
    task: async (id: string) => { const task = await request(path(id), valid.task); task.items.sort((a, b) => a.position - b.position); return task },
    retry: (id: string, key: string) => request(`${path(id)}/retry`, valid.accepted, 'POST', undefined, 10000, { 'Idempotency-Key': key }),
    revise: (id: string, item: string, input: ApiRevisionInput, key: string) => request(path(id) + '/items/' + encodeURIComponent(item) + '/revise', valid.accepted, 'POST', input, 10000, { 'Idempotency-Key': key }),
    retryItem: (id: string, item: string, key: string) => request(path(id) + '/items/' + encodeURIComponent(item) + '/retry', valid.accepted, 'POST', undefined, 10000, { 'Idempotency-Key': key }),
    restore: (id: string, item: string, version: number, key: string) => request(path(id) + '/items/' + encodeURIComponent(item) + '/restore', valid.accepted, 'POST', { version }, 10000, { 'Idempotency-Key': key }),
    zip: async (id: string) => {
      const blob = await readIdentityBlob(root + path(id) + '/zip', { signal: AbortSignal.timeout(120000) }, fetcher)
      if (!blob.type.startsWith('application/zip')) throw new ApiError('INVALID_RESPONSE', '下载内容不是 ZIP 文件')
      return blob
    },
    remove: (id: string) => request(path(id), valid.deleted, 'DELETE'),
    resume: () => request('/channel/resume', valid.resumed, 'POST'),
    resolve: (id: string) => request(`${path(id)}/resolve`, valid.accepted, 'POST', { confirmedStopped: true }),
    download: async (id: string) => {
      const blob = await readIdentityBlob(root + '/files/' + encodeURIComponent(id) + '/content?download=true', { signal: AbortSignal.timeout(60000) }, fetcher)
      if (!blob.type.startsWith('image/')) throw new ApiError('INVALID_RESPONSE', '下载内容不是图片')
      return blob
    }
  }
}
export const apiImages = createApiImageClient(import.meta.env?.VITE_API_URL || '/api/v1')
export const errorText = (error: unknown) => error instanceof Error ? error.message : '操作失败，请重试'
export const uncertainResponse = (error: unknown) => !(error instanceof ApiError) || !error.status || error.status >= 500 || error.status === 408
