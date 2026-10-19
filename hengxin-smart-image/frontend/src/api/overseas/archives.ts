import { createIdentityRequest, IdentityError, record } from '../identity/request'
import type { Page } from './tasks'
export interface Archive { id: string; taskId: string | null; sourceDeleted: boolean; productName: string; brand: string; platform: string; skus: { code: string }[]; pictureCount: number; createdAt: string; cover?: ArchivePicture | null; latestArchive?: ArchiveEvent | null }
export interface ArchivePicture { id: string; name: string; sku: string; width: number; height: number; contentType: string; sizeBytes: number; url: string }
export interface ArchiveEvent { id: string; actorId: string; actorName: string; at: string; pictures: { id: string; name: string; sku: string }[] }
export interface ArchiveDetail extends Archive { pictures: ArchivePicture[]; archiveHistory?: ArchiveEvent[]; historyIncomplete?: boolean }
export interface ArchiveQuery { search: string; page: number; pageSize: number }
const root = '/api/overseas/v1/archives'
const positive = (value: unknown) => Number.isInteger(value) && Number(value) > 0
const text = (value: unknown): value is string => typeof value === 'string'
export const archivePictureUrl = (id: string, pictureId: string) => `${root}/${encodeURIComponent(id)}/pictures/${encodeURIComponent(pictureId)}/content`
export const archiveError = (reason: unknown) => reason instanceof IdentityError && reason.status === 404 ? '成品不存在或已不可访问。' : reason instanceof Error ? reason.message : '成品读取失败，请重试'
function isPicture(picture: unknown, id: string): picture is ArchivePicture {
  return record(picture) && ['id', 'name', 'sku'].every(key => text(picture[key]))
    && ['image/png', 'image/jpeg', 'image/webp'].includes(String(picture.contentType)) && positive(picture.width) && positive(picture.height) && positive(picture.sizeBytes)
    && picture.url === archivePictureUrl(id, String(picture.id))
}
function isArchiveEvent(value: unknown): value is ArchiveEvent {
  return record(value) && ['id', 'actorId', 'actorName'].every(key => text(value[key]) && !!value[key])
    && text(value.at) && /^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/.test(value.at) && Number.isFinite(Date.parse(value.at))
    && Array.isArray(value.pictures) && value.pictures.length > 0
    && value.pictures.every(p => record(p) && ['id', 'name', 'sku'].every(key => text(p[key]) && !!p[key]))
    && new Set(value.pictures.map(p => p.id)).size === value.pictures.length
}
export function isArchive(value: unknown): value is Archive {
  return record(value) && ['id', 'productName', 'brand', 'platform', 'createdAt'].every(key => text(value[key]))
    && (value.taskId === null || text(value.taskId)) && typeof value.sourceDeleted === 'boolean'
    && (value.taskId !== null || value.sourceDeleted) && positive(value.pictureCount)
    && Array.isArray(value.skus) && value.skus.every(sku => record(sku) && text(sku.code))
    && (value.latestArchive === undefined || value.latestArchive === null || isArchiveEvent(value.latestArchive))
    && (value.cover == null || isPicture(value.cover, String(value.id)))
}
function matchesAssets(event: ArchiveEvent, pictures: unknown): boolean {
  return Array.isArray(pictures) && event.pictures.every(p => pictures.some(asset => record(asset) && asset.id === p.id && asset.name === p.name && asset.sku === p.sku))
}
export function isArchiveDetail(value: unknown, id: string): value is ArchiveDetail {
  return isArchive(value) && value.id === id && record(value) && Array.isArray(value.pictures)
    && value.pictures.length === value.pictureCount && new Set(value.pictures.map(p => record(p) ? p.id : null)).size === value.pictureCount
    && value.pictures.every(picture => isPicture(picture, id))
    && (!value.cover || value.cover.id === value.pictures[0].id)
    && (value.historyIncomplete === undefined || typeof value.historyIncomplete === 'boolean')
    && (value.archiveHistory === undefined || (Array.isArray(value.archiveHistory)
      && value.archiveHistory.every(event => isArchiveEvent(event) && matchesAssets(event, value.pictures))
      && new Set(value.archiveHistory.map(event => event.id)).size === value.archiveHistory.length
      && (value.latestArchive == null ? value.archiveHistory.length === 0 : value.archiveHistory[0]?.id === value.latestArchive.id)))
}
export function createArchivesApi(fetcher: typeof fetch = fetch) {
  const request = createIdentityRequest((url, options) => fetcher(url, { ...options, cache: 'no-store' }))
  async function binary(url: string, signal?: AbortSignal) {
    let response: Response
    try { response = await fetcher(url, { credentials: 'include', cache: 'no-store', headers: { 'X-HX-Request': '1' }, signal: signal || AbortSignal.timeout(60000) }) }
    catch (reason) { if (signal?.aborted) throw reason; throw new IdentityError(0, '成品服务连接失败，请重试') }
    if (!response.ok) throw new IdentityError(response.status, response.status === 403 ? '暂无此成品的访问权限' : response.status === 401 ? '身份已失效，请重新登录' : '成品读取失败，请重试')
    return response.blob()
  }
  return {
    list: (query: ArchiveQuery) => request(root, (value): value is Page<Archive> => record(value) && Array.isArray(value.items) && value.items.every(isArchive) && Number.isInteger(value.total) && Number(value.total) >= 0 && positive(value.page) && positive(value.pageSize), undefined, { params: { ...query } }),
    get: (id: string) => request(`${root}/${encodeURIComponent(id)}`, (value): value is ArchiveDetail => isArchiveDetail(value, id)),
    content: (id: string, pictureId: string, signal?: AbortSignal) => binary(archivePictureUrl(id, pictureId), signal),
    download: (id: string) => binary(`${root}/${encodeURIComponent(id)}/download`)
  }
}
export type ArchivesApi = ReturnType<typeof createArchivesApi>
