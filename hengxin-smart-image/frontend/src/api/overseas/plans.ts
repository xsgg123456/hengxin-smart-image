import { createIdentityRequest, record } from '../identity/request'
import { isTaskDetail, type TaskDetail } from './tasks'

export const planStatuses = { pending: '等待分析结果', ready: '待确认', confirmed: '已确认', failed: '分析失败', cancelled: '已停止', uncertain: '结果待核实' }
export interface PlanPicture { title: string; description: string; prompt: string; width: number; height: number }
export interface PlanContent { skus: { code: string; pictures: PlanPicture[] }[] }
export interface Plan { id: string; taskId: string; version: number; status: keyof typeof planStatuses; jobId: string; feedback: string; content: PlanContent | null; createdAt: string }
export interface PlanList { items: Plan[]; taskVersion: number }
const text = (v: unknown): v is string => typeof v === 'string'
const positive = (v: unknown) => Number.isInteger(v) && Number(v) > 0
export function isPlanContent(v: unknown): v is PlanContent {
  if (!record(v) || !Array.isArray(v.skus) || !v.skus.length) return false
  const codes = new Set<string>(); let total = 0
  return v.skus.every(s => {
    if (!record(s) || !text(s.code) || !s.code.trim() || codes.has(s.code) || !Array.isArray(s.pictures) || !s.pictures.length) return false
    codes.add(s.code); total += s.pictures.length
    return total <= 100 && s.pictures.every(p => record(p) && ['title', 'description', 'prompt'].every(k => text(p[k]) && p[k].trim()) && positive(p.width) && Number(p.width) <= 8192 && positive(p.height) && Number(p.height) <= 8192)
  })
}
export function isPlan(v: unknown): v is Plan {
  return record(v) && ['id', 'taskId', 'jobId', 'feedback', 'createdAt'].every(k => text(v[k])) && positive(v.version)
    && text(v.status) && Object.hasOwn(planStatuses, v.status) && (isPlanContent(v.content) || (v.content === null && !['ready', 'confirmed'].includes(v.status)))
}
export function isPlanList(v: unknown): v is PlanList {
  if (!record(v) || !positive(v.taskVersion) || !Array.isArray(v.items) || !v.items.every(isPlan)) return false
  return new Set(v.items.map(p => p.id)).size === v.items.length && v.items.every((p, i, a) => !i || a[i - 1].version > p.version)
}
export function createPlansApi(fetcher: typeof fetch = fetch) {
  const request = createIdentityRequest((url, options) => fetcher(url, { ...options, cache: 'no-store' }))
  const base = (id: string) => `/api/overseas/v1/tasks/${encodeURIComponent(id)}`
  return {
    list: (id: string) => request(`${base(id)}/plans`, (v): v is PlanList => isPlanList(v) && v.items.every(p => p.taskId === id)),
    analyze: (id: string, version: number, feedback: string, key: string) => request(`${base(id)}/analysis`, (v): v is TaskDetail => isTaskDetail(v) && v.id === id, { version, feedback }, { idempotencyKey: key }),
    confirm: (id: string, planId: string, version: number, key: string) => request(`${base(id)}/plans/${encodeURIComponent(planId)}/confirm`, (v): v is TaskDetail => isTaskDetail(v) && v.id === id, { version }, { idempotencyKey: key })
  }
}
