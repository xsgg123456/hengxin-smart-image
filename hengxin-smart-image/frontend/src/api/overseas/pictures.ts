import { createIdentityRequest, IdentityError, record } from '../identity/request'
import { isTaskDetail, type TaskDetail, type Page } from './tasks'
import type { AnnotationMark } from '../../views/hengxin/components/annotation/annotation-model'
export interface PictureVersion { version: number; url: string; width: number; height: number; note: string; createdAt: string }
export interface Picture { id: string; taskId: string; sku: string; position: number; title: string; version: number; approved: boolean; status: 'pending' | 'ready' | 'reworking' | 'failed'; url: string | null; width: number | null; height: number | null; history: PictureVersion[] }
export interface PictureList { items: Picture[]; taskVersion: number }
export interface Archive { id: string; taskId: string; productName: string; brand: string; skus: { code: string }[]; pictureCount: number; createdAt: string }
export type PictureCommand = { kind: 'approve' | 'revision' | 'retry' | 'archive'; taskId: string; pictureId: string; version: number; taskVersion: number; sku: string; note: string; marks: AnnotationMark[] }
const positive = (v: unknown) => Number.isInteger(v) && Number(v) > 0
const text = (v: unknown): v is string => typeof v === 'string'
const root = '/api/overseas/v1'
export const pictureUrl = (id: string, version: number) => `${root}/pictures/${encodeURIComponent(id)}/versions/${version}/content`
export function isPicture(v: unknown): v is Picture {
  if (!record(v) || !['id', 'taskId', 'sku', 'title'].every(k => text(v[k])) || !Number.isInteger(v.position) || Number(v.position) < 0 || !Number.isInteger(v.version) || Number(v.version) < 0 || typeof v.approved !== 'boolean' || !['pending', 'ready', 'reworking', 'failed'].includes(String(v.status))) return false
  if (v.version === 0 ? v.url !== null || v.approved || v.status === 'ready' : v.url !== pictureUrl(String(v.id), Number(v.version)) || !positive(v.width) || !positive(v.height)) return false
  return Array.isArray(v.history) && v.history.every(h => record(h) && positive(h.version) && h.url === pictureUrl(String(v.id), Number(h.version)) && positive(h.width) && positive(h.height) && text(h.note) && text(h.createdAt))
}
export function isPictureList(v: unknown): v is PictureList {
  return record(v) && positive(v.taskVersion) && Array.isArray(v.items) && v.items.every(isPicture) && new Set(v.items.map(p => p.id)).size === v.items.length
}
export function canArchive(items: Picture[], status: string) { return status === 'review' && items.length > 0 && items.every(p => p.version > 0 && p.status === 'ready' && p.approved) }
export function createPicturesApi(fetcher: typeof fetch = fetch) {
  const request = createIdentityRequest((url, options) => fetcher(url, { ...options, cache: 'no-store' }))
  const task = (id: string) => `${root}/tasks/${encodeURIComponent(id)}`
  async function binary(url: string) {
    let result: Response
    try { result = await fetcher(url, { credentials: 'include', cache: 'no-store', signal: AbortSignal.timeout(60000) }) } catch { throw new IdentityError(0, '图片服务连接失败，请重试') }
    if (!result.ok) throw new IdentityError(result.status, result.status === 403 ? '暂无权限' : result.status === 401 ? '身份已失效，请重新登录' : '文件读取失败，请重试')
    return result.blob()
  }
  return {
    list: (id: string) => request(`${task(id)}/pictures`, (v): v is PictureList => isPictureList(v) && v.items.every(p => p.taskId === id)),
    command: (c: PictureCommand, key: string) => {
      const url = c.kind === 'retry' ? `${task(c.taskId)}/generation/retry` : c.kind === 'archive' ? `${task(c.taskId)}/archive` : `${root}/pictures/${encodeURIComponent(c.pictureId)}/${c.kind === 'approve' ? 'approve' : 'revisions'}`
      const body = c.kind === 'retry' ? { version: c.taskVersion, sku: c.sku } : c.kind === 'archive' ? { version: c.taskVersion } : { version: c.version, taskVersion: c.taskVersion, ...(c.kind === 'revision' ? { note: c.note, marks: c.marks } : {}) }
      return request(url, (v): v is TaskDetail => isTaskDetail(v) && v.id === c.taskId, body, { idempotencyKey: key })
    },
    content: (id: string, version: number) => binary(`${pictureUrl(id, version)}?download=true`),
    archives: (query: { product: string; brand: string; sku: string; search: string; page: number; pageSize: number }) => request(`${root}/archives`, (v): v is Page<Archive> => record(v) && Array.isArray(v.items) && Number.isInteger(v.total) && Number(v.total) >= 0 && positive(v.page) && positive(v.pageSize) && v.items.every(a => record(a) && ['id', 'taskId', 'productName', 'brand', 'createdAt'].every(k => text(a[k])) && positive(a.pictureCount) && Array.isArray(a.skus) && a.skus.every(s => record(s) && text(s.code))), undefined, { params: query }),
    download: (id: string) => binary(`${root}/archives/${encodeURIComponent(id)}/download`)
  }
}
export function saveBlob(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob), a = document.createElement('a'); a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 1000)
}

export function pictureFilename(id: string, version: number, type: string) {
  const extension = type === 'image/jpeg' ? 'jpg' : type === 'image/webp' ? 'webp' : type === 'image/png' ? 'png' : 'bin'
  return `${id}-v${version}.${extension}`
}
