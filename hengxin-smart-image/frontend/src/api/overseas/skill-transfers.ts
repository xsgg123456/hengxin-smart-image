import { IdentityError, record } from '../identity/request'

export type FolderEntry = { directory: true } | { size: number; sha256: string }
export interface FolderManifest { rootName: string; entries: Record<string, FolderEntry> }
export interface SkillPackage extends FolderManifest { name: string; displayName: string; description: string; checksum: string; release: string }
export interface SkillTransfer extends FolderManifest {
  id: string; status: 'uploading' | 'validated' | 'installed' | 'failed' | 'cancelled'; received: string[]; error?: string | null
  package?: Pick<SkillPackage, 'name' | 'displayName' | 'description' | 'checksum'>
  change?: 'create' | 'update' | 'identical'; baseRelease?: string | null
  diff?: { added: string[]; modified: string[]; removed: string[] }; release?: string
}
export const isDirectory = (entry: FolderEntry): entry is { directory: true } => 'directory' in entry
const strings = (v: unknown): v is string[] => Array.isArray(v) && v.every(x => typeof x === 'string')
function isManifest(v: unknown): v is FolderManifest {
  return record(v) && typeof v.rootName === 'string' && record(v.entries) && Object.values(v.entries).every(e => record(e) && (e.directory === true || (e.directory === undefined && Number.isSafeInteger(e.size) && Number(e.size) >= 0 && typeof e.sha256 === 'string' && /^[a-f0-9]{64}$/.test(e.sha256))))
}
export function isTransfer(v: unknown): v is SkillTransfer {
  return isManifest(v) && record(v) && typeof v.id === 'string' && ['uploading', 'validated', 'installed', 'failed', 'cancelled'].includes(String(v.status)) && strings(v.received)
    && (v.package === undefined || (record(v.package) && ['name', 'displayName', 'description', 'checksum'].every(k => typeof v.package === 'object' && v.package !== null && typeof (v.package as Record<string, unknown>)[k] === 'string')))
    && (v.diff === undefined || (record(v.diff) && strings(v.diff.added) && strings(v.diff.modified) && strings(v.diff.removed)))
    && (v.change === undefined || ['create', 'update', 'identical'].includes(String(v.change)))
    && (v.baseRelease === undefined || v.baseRelease === null || typeof v.baseRelease === 'string')
    && (v.error === undefined || v.error === null || typeof v.error === 'string')
    && (v.release === undefined || typeof v.release === 'string')
}
export function isPackage(v: unknown): v is SkillPackage { return isManifest(v) && record(v) && ['name', 'displayName', 'description', 'checksum', 'release'].every(k => typeof v[k] === 'string') }
export function skillTransferError(reason: unknown): string {
  if (reason instanceof IdentityError && reason.status === 409) return 'Skill 或平台配置已变化，请刷新最新状态后重新核对操作'
  if (reason instanceof IdentityError && typeof reason.detail === 'string') return reason.detail
  return reason instanceof Error ? reason.message : '操作失败，请重试'
}
export function createSkillTransferApi(fetcher: typeof fetch = fetch) {
  const base = '/api/overseas/v1/management'
  async function request(path: string, method = 'GET', body?: BodyInit, binary = false, key?: string) {
    let response: Response
    try { response = await fetcher(base + path, { method, credentials: 'include', signal: AbortSignal.timeout(120000), headers: { ...(body === undefined ? {} : { 'Content-Type': binary ? 'application/octet-stream' : 'application/json', 'X-HX-Request': '1' }), ...(key ? { 'Idempotency-Key': key } : {}) }, body }) }
    catch { throw new IdentityError(0, '连接中断，结果尚未确认，请查询状态后重试') }
    if (!response.ok) {
      const value: unknown = await response.json().catch(() => undefined)
      throw new IdentityError(response.status, response.status === 401 ? '身份已失效，请重新登录' : response.status === 403 ? '当前账号没有此操作权限' : '操作失败，请重试', record(value) ? value.detail : undefined)
    }
    return response
  }
  async function json<T>(path: string, guard: (v: unknown) => v is T, method = 'GET', body?: unknown, key?: string): Promise<T> {
    const response = await request(path, method, body === undefined ? undefined : JSON.stringify(body), false, key)
    const value: unknown = response.status === 204 ? undefined : await response.json()
    if (!guard(value)) throw new Error('Skill 服务响应格式错误，请查询状态后重试')
    return value
  }
  const transferPath = (id: string) => '/skill-transfers/' + encodeURIComponent(id)
  const skillPath = (id: string) => '/skills/' + encodeURIComponent(id)
  return {
    create: (manifest: FolderManifest, key: string) => json('/skill-transfers', isTransfer, 'POST', manifest, key),
    list: () => json('/skill-transfers', (v): v is { items: SkillTransfer[] } => record(v) && Array.isArray(v.items) && v.items.every(isTransfer)),
    get: (id: string) => json(transferPath(id), isTransfer),
    async upload(id: string, path: string, file: Blob) { const value: unknown = await (await request(transferPath(id) + '/files?path=' + encodeURIComponent(path), 'PUT', file, true)).json(); if (!isTransfer(value)) throw new Error('上传状态格式错误'); return value },
    validate: (id: string) => json(transferPath(id) + '/validate', isTransfer, 'POST', {}),
    install: (id: string, baseRelease: string | null) => json(transferPath(id) + '/install', isTransfer, 'POST', { baseRelease }),
    cancel: (id: string) => json(transferPath(id), isTransfer, 'DELETE', {}),
    package: (id: string) => json(skillPath(id) + '/package', isPackage),
    async file(id: string, release: string, path: string) { return (await request(skillPath(id) + '/files?' + new URLSearchParams({ release, path }))).arrayBuffer() },
    async remove(id: string, release: string, checksum: string, version: number) { await request(skillPath(id), 'DELETE', JSON.stringify({ release, checksum, version })) }
  }
}
export type SkillTransferApi = ReturnType<typeof createSkillTransferApi>
