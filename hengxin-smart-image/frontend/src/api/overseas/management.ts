import { createIdentityRequest, IdentityError, record } from '../identity/request'
export const stages = { analysis: '整套分析', generation: '按 SKU 生图', revision: '单图返工' }
export type Stage = keyof typeof stages
export const managementPages = { usage: '调用统计', monitor: '执行监控', users: '用户与角色', skills: 'Skill 管理', settings: '系统配置' }
export type ManagementPage = keyof typeof managementPages
export const managementCapability = (page: ManagementPage) => page === 'usage' || page === 'monitor' ? 'stats.read' : page === 'users' ? 'members.manage' : page + '.manage'
export interface ManagementQuery { memberId?: string; from: string; to: string; taskId: string; kind: string; status: string; page: number; pageSize: number }
export interface Usage { jobs: number; queued: number; running: number; uncertain: number; succeeded: number; failed: number; cancelled: number; generationImages: number; revisionImages: number }
export interface Job { id: string; taskId: string; taskName: string; kind: string; status: string; executionCount: number; imageCount: number; operatorId: string | null; operatorName: string | null; createdAt: string; startedAt: string | null; completedAt: string | null; error: string | null }
export interface Operator { id: string; name: string }
export interface Jobs { items: Job[]; total: number; page: number; pageSize: number }
export interface Skill { id: string; name: string; displayName: string; description: string }
export interface Settings { version: number; paused: boolean; concurrency: number; timeoutSeconds: number; defaults: Record<Stage,string | null>; autoCleanup: false }
const count = (v: unknown) => Number.isInteger(v) && Number(v) >= 0
const positive = (v: unknown) => count(v) && Number(v) > 0
export function isUsage(v: unknown): v is Usage { return record(v) && ['jobs','queued','running','uncertain','succeeded','failed','cancelled','generationImages','revisionImages'].every(k => count(v[k])) }
export function isJobs(v: unknown): v is Jobs { return record(v) && count(v.total) && positive(v.page) && positive(v.pageSize) && Array.isArray(v.items) && v.items.every(j => record(j) && ['id','taskId','taskName','kind','status','createdAt'].every(k => typeof j[k] === 'string') && ['startedAt','completedAt','error','operatorId','operatorName'].every(k => j[k] === null || typeof j[k] === 'string') && count(j.executionCount) && count(j.imageCount)) }
export function isSkill(v: unknown): v is Skill { return record(v) && ['id', 'name', 'displayName', 'description'].every(k => typeof v[k] === 'string') && String(v.id).length > 0 && String(v.name).trim().length > 0 && String(v.displayName).trim().length > 0 }
export function isSettings(v: unknown): v is Settings { return record(v) && positive(v.version) && typeof v.paused === 'boolean' && positive(v.concurrency) && Number(v.concurrency) <= 5 && count(v.timeoutSeconds) && Number(v.timeoutSeconds) >= 10 && Number(v.timeoutSeconds) <= 7200 && v.autoCleanup === false && record(v.defaults) && Object.keys(stages).every(k => record(v.defaults) && (v.defaults[k] === null || typeof v.defaults[k] === 'string')) }
export function createManagementApi(fetcher: typeof fetch = fetch) {
  const request = createIdentityRequest(fetcher), base = '/api/overseas/v1/management'
  return {
    operators: () => request(base + '/operators', (v): v is { items: Operator[] } => record(v) && Array.isArray(v.items) && v.items.every(item => record(item) && typeof item.id === 'string' && typeof item.name === 'string')),
    usage: (query: ManagementQuery) => request(base + '/usage', isUsage, undefined, { params: { ...query } }),
    jobs: (query: ManagementQuery) => request(base + '/jobs', isJobs, undefined, { params: { ...query } }),
    skills: () => request(base + '/skills', (v): v is { items: Skill[] } => record(v) && Array.isArray(v.items) && v.items.every(isSkill)),
    settings: () => request(base + '/settings', isSettings),
    saveSettings: (v: Settings) => request(base + '/settings', isSettings, { version: v.version, paused: v.paused, concurrency: v.concurrency, timeoutSeconds: v.timeoutSeconds, defaults: { ...v.defaults } }, { method: 'PATCH' })
  }
}
export type ManagementApi = ReturnType<typeof createManagementApi>
export const managementError = (e: unknown) => e instanceof IdentityError && e.status === 409 ? '记录已变化，请刷新最新版本；你的草稿已保留' : e instanceof IdentityError && e.status === 422 ? '配置不符合要求，请检查名称、指令内容及默认阶段绑定' : e instanceof Error ? e.message : '服务暂不可用，请重试'
