import { createIdentityRequest, IdentityError, record } from '../identity/request'
export const stages = { analysis: '整套分析', generation: '按 SKU 生图', revision: '单图返工' }
export type Stage = keyof typeof stages
export const managementPages = { usage: '调用统计', monitor: '执行监控', users: '用户与角色', skills: 'Skill 管理', settings: '系统配置' }
export type ManagementPage = keyof typeof managementPages
export const managementCapability = (page: ManagementPage) => page === 'usage' || page === 'monitor' ? 'stats.read' : page === 'users' ? 'members.manage' : page + '.manage'
export interface ManagementQuery { from: string; to: string; taskId: string; kind: string; status: string; page: number; pageSize: number }
export interface Usage { jobs: number; queued: number; running: number; uncertain: number; succeeded: number; failed: number; cancelled: number; generationImages: number; revisionImages: number; inputTokens: number | null; outputTokens: number | null; cost: number | null }
export interface Job { id: string; taskId: string; taskName: string; kind: string; status: string; executionCount: number; imageCount: number; inputTokens: number | null; outputTokens: number | null; createdAt: string; startedAt: string | null; completedAt: string | null; error: string | null }
export interface Jobs { items: Job[]; total: number; page: number; pageSize: number }
export interface SkillVersion { version: number; files: Record<string,string>; assetNames?: string[]; createdAt: string }
export interface Skill { id: string; name: string; stage: Stage; enabled: boolean; version: number; currentVersion: number; versions: SkillVersion[] }
export interface Settings { version: number; paused: boolean; concurrency: number; timeoutSeconds: number; defaults: Record<Stage,string | null>; autoCleanup: false }
const count = (v: unknown) => Number.isInteger(v) && Number(v) >= 0
const positive = (v: unknown) => count(v) && Number(v) > 0
const nullableCount = (v: unknown) => v === null || count(v)
export function isUsage(v: unknown): v is Usage { return record(v) && ['jobs','queued','running','uncertain','succeeded','failed','cancelled','generationImages','revisionImages'].every(k => count(v[k])) && nullableCount(v.inputTokens) && nullableCount(v.outputTokens) && v.cost === null }
export function isJobs(v: unknown): v is Jobs { return record(v) && count(v.total) && positive(v.page) && positive(v.pageSize) && Array.isArray(v.items) && v.items.every(j => record(j) && ['id','taskId','taskName','kind','status','createdAt'].every(k => typeof j[k] === 'string') && ['startedAt','completedAt','error'].every(k => j[k] === null || typeof j[k] === 'string') && count(j.executionCount) && count(j.imageCount) && nullableCount(j.inputTokens) && nullableCount(j.outputTokens)) }
export function isSkill(v: unknown): v is Skill { return record(v) && typeof v.id === 'string' && typeof v.name === 'string' && Object.hasOwn(stages,String(v.stage)) && typeof v.enabled === 'boolean' && positive(v.version) && positive(v.currentVersion) && Array.isArray(v.versions) && v.versions.every(r => record(r) && positive(r.version) && typeof r.createdAt === 'string' && record(r.files) && typeof r.files['SKILL.md'] === 'string' && Object.values(r.files).every(s => typeof s === 'string')) }
export function isSettings(v: unknown): v is Settings { return record(v) && positive(v.version) && typeof v.paused === 'boolean' && positive(v.concurrency) && Number(v.concurrency) <= 5 && count(v.timeoutSeconds) && Number(v.timeoutSeconds) >= 10 && Number(v.timeoutSeconds) <= 7200 && v.autoCleanup === false && record(v.defaults) && Object.keys(stages).every(k => record(v.defaults) && (v.defaults[k] === null || typeof v.defaults[k] === 'string')) }
export function createManagementApi(fetcher: typeof fetch = fetch) {
  const request = createIdentityRequest(fetcher), base = '/api/overseas/v1/management'
  return {
    uploadPackage: async (file: File, name: string, stage: Stage, identity?: string, version?: number): Promise<Skill> => {
      const query = new URLSearchParams({name, stage})
      if (identity && version !== undefined) { query.set('identity', identity); query.set('version', String(version)) }
      const body = new FormData(); body.append('file', file)
      let response: Response
      try { response = await fetcher(base + '/skill-packages?' + query, {method:'POST', credentials:'include', headers:{'X-HX-Request':'1',Accept:'application/json'}, body, signal:AbortSignal.timeout(120000)}) }
      catch { throw new IdentityError(0, '连接中断，发布结果未知，请刷新核实') }
      let value: unknown
      try { value = await response.json() } catch { value = undefined }
      if (!response.ok) throw new IdentityError(response.status, response.status === 422 ? 'Skill ZIP无效，请检查文件结构及大小' : response.status === 403 ? '暂无权限' : 'Skill发布失败，请刷新核实')
      if (!isSkill(value)) throw new IdentityError(0, '发布响应异常，请刷新核实')
      return value
    },
    usage: (query: ManagementQuery) => request(base + '/usage', isUsage, undefined, { params: { ...query } }),
    jobs: (query: ManagementQuery) => request(base + '/jobs', isJobs, undefined, { params: { ...query } }),
    skills: () => request(base + '/skills', (v): v is { items: Skill[] } => record(v) && Array.isArray(v.items) && v.items.every(isSkill)),
    createSkill: (name: string, stage: Stage, files: Record<string,string>) => request(base + '/skills', isSkill, { name, stage, files }),
    publish: (id: string, version: number, files: Record<string,string>) => request(base + '/skills/' + encodeURIComponent(id) + '/versions', isSkill, { version, files }),
    toggle: (id: string, version: number, enabled: boolean) => request(base + '/skills/' + encodeURIComponent(id), isSkill, { version, enabled }, { method: 'PATCH' }),
    settings: () => request(base + '/settings', isSettings),
    saveSettings: (v: Settings) => request(base + '/settings', isSettings, { version: v.version, paused: v.paused, concurrency: v.concurrency, timeoutSeconds: v.timeoutSeconds, defaults: { ...v.defaults } }, { method: 'PATCH' })
  }
}
export type ManagementApi = ReturnType<typeof createManagementApi>
export const managementError = (e: unknown) => e instanceof IdentityError && e.status === 409 ? '记录已变化，请刷新最新版本；你的草稿已保留' : e instanceof IdentityError && e.status === 422 ? '配置不符合要求，请检查名称、指令内容及默认阶段绑定' : e instanceof Error ? e.message : '服务暂不可用，请重试'
