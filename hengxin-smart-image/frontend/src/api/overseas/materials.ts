import { createIdentityRequest, IdentityError, record } from '../identity/request'
export type MaterialKind = 'requirement' | 'competitor'
export interface ParseVersion { version: number; status: 'ready' | 'failed'; parserVersion: string; text: string; error: string | null; createdAt: string }
export interface Material extends ParseVersion { id: string; kind: MaterialKind; name: string; sizeBytes: number; contentType: string; taskId: string | null; versions: ParseVersion[] }
export interface MaterialsApi {
  upload(file: File, kind: MaterialKind, progress: (percent: number) => void, signal: AbortSignal): Promise<Material>
  get(id: string): Promise<Material>
  list(taskId: string): Promise<Material[]>
  retry(id: string): Promise<Material>
  remove(id: string): Promise<void>
  content(id: string, download: boolean, signal: AbortSignal): Promise<Blob>
}
const text = (v: unknown): v is string => typeof v === 'string'
function isVersion(v: unknown): v is ParseVersion {
  return record(v) && Number.isInteger(v.version) && Number(v.version) > 0 && ['ready', 'failed'].includes(String(v.status))
    && text(v.parserVersion) && text(v.text) && text(v.createdAt) && (v.error === null || text(v.error))
    && (v.status !== 'ready' || v.text.trim().length > 0)
}
export function isMaterial(v: unknown): v is Material {
  return isVersion(v) && record(v) && ['id', 'name', 'contentType'].every(k => text(v[k]))
    && ['requirement', 'competitor'].includes(String(v.kind)) && Number.isInteger(v.sizeBytes) && Number(v.sizeBytes) > 0
    && (v.taskId === null || text(v.taskId)) && Array.isArray(v.versions) && v.versions.length > 0 && v.versions.every(isVersion)
    && v.versions.some(item => item.version === v.version && item.status === v.status)
}
export function validateFile(file: Pick<File, 'name' | 'size'>, kind: MaterialKind) {
  if (!file.size) throw Error('文件为空，请选择包含内容的文件')
  if (file.size > 20 * 1024 * 1024) throw Error('单个文件不能超过 20 MiB')
  const extension = file.name.split('.').pop()?.toLowerCase()
  if (extension === 'doc') throw Error('暂不支持 DOC，请另存为 DOCX 或 PDF 后上传')
  if (!(kind === 'requirement' ? ['pdf', 'docx'] : ['xls', 'xlsx', 'csv']).includes(extension || '')) throw Error('文件类型不符合资料要求')
}
export function readyMaterialIds(files: Material[]) {
  if (!files.length || files.length > 2 || files.some(f => f.status !== 'ready' || f.taskId !== null)) throw Error('至少提供一份解析成功的资料；请先移除或重试失败资料')
  if (new Set(files.map(f => f.kind)).size !== files.length || new Set(files.map(f => f.id)).size !== files.length) throw Error('每类资料仅支持一份')
  return files.map(f => f.id)
}
export function materialError(reason: unknown) {
  if (reason instanceof IdentityError) {
    if (reason.status === 409) return '资料已被绑定或任务已变化，请刷新后重试'
    if (reason.status === 413) return '单个文件不能超过 20 MiB'
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
    retry: id => request(`${path(id)}/retry`, isMaterial, {}, { timeoutMs: 120000 }),
    async remove(id) { await binary(path(id), 'DELETE') },
    async content(id, download, signal) { return (await binary(`${path(id)}/content?download=${download}`, 'GET', signal)).blob() },
    async upload(file, kind, progress, signal) {
      validateFile(file, kind)
      return new Promise<Material>((resolve, reject) => {
        if (signal.aborted) { reject(new Error('上传已取消')); return }
        const xhr = xhrFactory(), abort = () => xhr.abort()
        const cleanup = () => signal.removeEventListener('abort', abort)
        xhr.open('POST', `${base}?kind=${kind}`); xhr.withCredentials = true; xhr.timeout = 120000
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
