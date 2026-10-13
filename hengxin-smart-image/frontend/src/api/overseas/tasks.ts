import { createIdentityRequest, record, IdentityError } from '../identity/request'
import { STATUS_LABELS } from '../../views/overseas/types'
export const taskStatuses = { created: '图需已保存', submitted: '图需已提交', studio: 'AI 设计工作台', completed: '已完成', ...STATUS_LABELS }
export interface TaskDraft { name: string; productName: string; brand: string; platform: string; market: string; remarks: string; skus: { code: string }[]; designerId: string; materialIds?: string[] }
export interface TaskSummary extends Omit<TaskDraft, 'designerId'> {
  workflow?: 'legacy' | 'studio'
  id: string; status: keyof typeof taskStatuses; version: number; createdAt: string; updatedAt: string
  createdBy: { id: string; name: string }; designer: { id: string; name: string; status: string; eligible: boolean }; capabilities: string[]
}
export interface TaskEvent { id: string; kind: string; actorId: string; actorName: string; title: string; at: string; beforeDesignerId: string | null; afterDesignerId: string; version: number }
export interface RequirementsReview { id: string; decision: 'approve' | 'reject'; comment: string; actorId: string; actorName: string; createdAt: string; version: number; materialIds?: string[] }
export interface TaskDetail extends TaskSummary { events: TaskEvent[]; requirementsReviews?: RequirementsReview[] }
export interface Designer { id: string; name: string; department: string }
export interface Page<T> { items: T[]; total: number; page: number; pageSize: number }
export interface TaskQuery { search: string; scope: string; status: string; page: number; pageSize: number }
export interface TasksApi {
  list(query: TaskQuery): Promise<Page<TaskSummary>>
  get(id: string): Promise<TaskDetail>
  create(draft: TaskDraft, key: string): Promise<TaskDetail>
  submitMaterials(id: string, materialIds: string[], version: number, key: string): Promise<TaskDetail>
  assign(id: string, designerId: string, version: number, key: string): Promise<TaskDetail>
  reviewRequirements(id: string, decision: 'approve' | 'reject', comment: string, version: number, key: string): Promise<TaskDetail>
  resubmit(id: string, draft: TaskDraft, version: number, key: string): Promise<TaskDetail>
  designers(query: { search: string; page: number; pageSize: number }): Promise<Page<Designer>>
}
const text = (v: unknown): v is string => typeof v === 'string'
const positive = (v: unknown) => Number.isInteger(v) && Number(v) > 0
const person = (v: unknown) => record(v) && text(v.id) && text(v.name)
export function isTask(v: unknown): v is TaskSummary {
  return record(v) && ['id', 'name', 'productName', 'brand', 'platform', 'market', 'remarks', 'createdAt', 'updatedAt'].every(k => text(v[k]))
    && text(v.status) && Object.hasOwn(taskStatuses, v.status) && positive(v.version)
    && (v.workflow === undefined || v.workflow === 'legacy' || v.workflow === 'studio')
    && Array.isArray(v.skus) && v.skus.length > 0 && v.skus.every(s => record(s) && text(s.code))
    && person(v.createdBy) && person(v.designer) && record(v.designer) && text(v.designer.status) && typeof v.designer.eligible === 'boolean'
    && Array.isArray(v.capabilities) && v.capabilities.every(text)
}
export function isTaskDetail(v: unknown): v is TaskDetail {
  return isTask(v) && record(v) && Array.isArray(v.events) && v.events.every(e => record(e)
    && ['id', 'kind', 'actorId', 'actorName', 'title', 'at', 'afterDesignerId'].every(k => text(e[k]))
    && (e.beforeDesignerId === null || text(e.beforeDesignerId)) && positive(e.version))
    && (v.requirementsReviews === undefined || (Array.isArray(v.requirementsReviews) && v.requirementsReviews.every(r => record(r)
      && ['id', 'comment', 'actorId', 'actorName', 'createdAt'].every(k => text(r[k]))
      && ['approve', 'reject'].includes(String(r.decision)) && positive(r.version)
      && (r.materialIds === undefined || (Array.isArray(r.materialIds) && r.materialIds.every(text))))))
}
function pageOf<T>(guard: (v: unknown) => v is T) {
  return (v: unknown): v is Page<T> => record(v) && Array.isArray(v.items) && v.items.every(guard)
    && Number.isInteger(v.total) && Number(v.total) >= 0 && positive(v.page) && positive(v.pageSize)
}
export function taskError(reason: unknown) {
  if (reason instanceof IdentityError) {
    if (reason.status === 409) return '任务或资料已发生变化，请刷新后重试。'
    if (reason.status === 422) return '图需信息、资料或设计人选不符合要求，请检查后重试。'
    if (reason.status === 404) return '任务不存在或已不可访问。'
  }
  return reason instanceof Error ? reason.message : '请求失败，请重试'
}
export function createTasksApi(fetcher: typeof fetch = fetch): TasksApi {
  const request = createIdentityRequest(fetcher), base = '/api/overseas/v1/tasks'
  return {
    list: query => request(base, pageOf(isTask), undefined, { params: { ...query } }),
    get: id => request(`${base}/${encodeURIComponent(id)}`, isTaskDetail),
    create: (draft, key) => request(base, isTaskDetail, cleanDraft(draft), { idempotencyKey: key }),
    submitMaterials: (id, materialIds, version, key) => request(`${base}/${encodeURIComponent(id)}/materials`, isTaskDetail, { materialIds, version }, { idempotencyKey: key }),
    assign: (id, designerId, version, key) => request(`${base}/${encodeURIComponent(id)}/assignment`, isTaskDetail, { designerId, version }, { method: 'PATCH', idempotencyKey: key }),
    reviewRequirements: (id, decision, comment, version, key) => request(`${base}/${encodeURIComponent(id)}/requirements-review`, isTaskDetail, { decision, comment: comment.trim(), version }, { idempotencyKey: key }),
    resubmit: (id, draft, version, key) => request(`${base}/${encodeURIComponent(id)}/resubmit`, isTaskDetail, { ...cleanDraft(draft), version }, { idempotencyKey: key }),
    designers: query => request('/api/overseas/v1/task-designers', pageOf((v): v is Designer => record(v) && person(v) && text(v.department)), undefined, { params: { ...query } })
  }
}
export function emptyTaskDraft(): TaskDraft { return { name: '', productName: '', brand: '', platform: 'Amazon', market: '', remarks: '', skus: [{ code: '' }], designerId: '' } }
export function cleanDraft(d: TaskDraft): TaskDraft {
  return { name: d.name.trim(), productName: d.productName.trim(), brand: d.brand.trim(), platform: d.platform.trim(), market: d.market.trim(), remarks: d.remarks.trim(), skus: d.skus.map(s => ({ code: s.code.trim() })), designerId: d.designerId, ...(d.materialIds ? { materialIds: [...d.materialIds] } : {}) }
}
export function validateDraft(d: TaskDraft) {
  if (![d.name, d.productName, d.brand, d.platform, d.market, d.designerId].every(v => v.trim())) throw Error('请填写必填信息并指定设计')
  if (!d.skus.length || d.skus.length > 100 || d.skus.some(s => !s.code.trim())) throw Error('请填写 1–100 个 SKU')
  if (new Set(d.skus.map(s => s.code.trim().toLowerCase())).size !== d.skus.length) throw Error('SKU 不能重复')
}
// Keep the same key for each unsuccessful payload, including A → B → A edits.
export function createRequestKeys(random: () => string = () => crypto.randomUUID()) {
  const keys = new Map<string, string>()
  return { for(body: unknown) { const hash = JSON.stringify(body); if (!keys.has(hash)) keys.set(hash, random()); return keys.get(hash)! }, clear() { keys.clear() } }
}
