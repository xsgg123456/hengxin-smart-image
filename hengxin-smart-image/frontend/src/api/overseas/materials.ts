import { MAX_UPLOAD_BYTES } from './upload-limits'
import { createIdentityRequest, IdentityError, record } from '../identity/request'
export type MaterialKind = 'requirement' | 'competitor'
export interface Material { id: string; kind: MaterialKind; name: string; sizeBytes: number; contentType: string; taskId: string | null; createdAt: string; status: 'ready' }
export interface MaterialsApi {
  upload(file: File, kind: MaterialKind, progress: (percent: number) => void, signal: AbortSignal): Promise<Material>
  get(id: string): Promise<Material>
  list(taskId: string): Promise<Material[]>
  remove(id: string): Promise<void>
}
const text = (v: unknown): v is string => typeof v === 'string'
export function isMaterial(v: unknown): v is Material {
  return record(v) && ['id', 'name', 'contentType', 'createdAt'].every(k => text(v[k])) && v.status === 'ready'
    && ['requirement', 'competitor'].includes(String(v.kind)) && Number.isInteger(v.sizeBytes) && Number(v.sizeBytes) > 0
    && (v.taskId === null || text(v.taskId))
}
export function validateFile(file: Pick<File, 'name' | 'size'>, kind: MaterialKind) {
  if (!file.size) throw Error('文件为空，请选择包含内容的文件')
  if (file.size > MAX_UPLOAD_BYTES) throw Error('单个文件不能超过 500 MB')
  if (!['requirement', 'competitor'].includes(kind)) throw Error('资料类别无效')
}
export function readyMaterialIds(files: Material[]) {
  if (!files.length || files.length > 2 || files.some(f => f.taskId !== null)) throw Error('至少提供一份已上传的未绑定资料')
  if (new Set(files.map(f => f.kind)).size !== files.length || new Set(files.map(f => f.id)).size !== files.length) throw Error('每类资料仅支持一份')
  return files.map(f => f.id)
}
export function materialError(reason: unknown) {
  if (reason instanceof IdentityError) {
    if (reason.status === 409) return '资料已被绑定或任务已变化，请刷新后重试'
    if (reason.status === 413) return '单个文件不能超过 500 MB'
    if ([415, 422].includes(reason.status)) return '文件格式或内容不符合要求，请检查支持类型和文件内容'
  }
  return reason instanceof Error ? reason.message : '资料操作失败，请重试'
}
function failure(status: number) { return new IdentityError(status, status === 401 ? '身份已失效，请重新登录' : status === 403 ? '暂无权限' : status === 404 ? '资料不存在或已不可访问' : '资料服务连接失败，请重试') }
export function createMaterialsApi(fetcher: typeof fetch = fetch, xhrFactory = () => new XMLHttpRequest()): MaterialsApi {
  const base = '/api/overseas/v1/materials', request = createIdentityRequest(fetcher), path = (id: string) => `${base}/${encodeURIComponent(id)}`
  async function binary(url: string, method: string, signal?: AbortSignal) {
    let result: Response
    try { result = await fetcher(url, { method, credentials: 'include', cache: 'no-store', headers: { 'X-HX-Request': '1' }, signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(60000)]) : AbortSignal.timeout(10000) }) }
    catch { throw failure(0) }
    if (!result.ok) throw failure(result.status)
    return result
  }
  return {
    get: id => request(path(id), isMaterial),
    list: id => request(`/api/overseas/v1/tasks/${encodeURIComponent(id)}/materials`, (v): v is Material[] => Array.isArray(v) && v.every(isMaterial)),
    async remove(id) { await binary(path(id), 'DELETE') },
    async upload(file, kind, progress, signal) {
      validateFile(file, kind)
      return new Promise<Material>((resolve, reject) => {
        if (signal.aborted) { reject(new Error('上传已取消')); return }
        const xhr = xhrFactory(), abort = () => xhr.abort()
        const cleanup = () => signal.removeEventListener('abort', abort)
        xhr.open('POST', `${base}?kind=${kind}`); xhr.withCredentials = true; xhr.timeout = 0
        xhr.setRequestHeader('X-HX-Request', '1'); xhr.setRequestHeader('Accept', 'application/json')
        xhr.upload.onprogress = event => { if (event.lengthComputable) progress(Math.round(event.loaded / event.total * 100)) }
        xhr.onload = () => {
          cleanup()
          if (xhr.status < 200 || xhr.status >= 300) { reject(failure(xhr.status)); return }
          let value: unknown
          try { value = JSON.parse(xhr.responseText) } catch { reject(new IdentityError(0, '服务响应格式错误，请重试')); return }
          if (!isMaterial(value)) { reject(new IdentityError(0, '服务响应格式错误，请重试')); return }
          resolve(value)
        }
        xhr.onerror = xhr.ontimeout = () => { cleanup(); reject(failure(0)) }
        xhr.onabort = () => { cleanup(); reject(new Error('上传已取消')) }
        signal.addEventListener('abort', abort, { once: true })
        const data = new FormData(); data.append('file', file); xhr.send(data)
      })
    }
  }
}
