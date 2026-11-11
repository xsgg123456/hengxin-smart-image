import { createRequest } from './hengxin/http'
import type { ActivityQuery, ActivityReport } from '@/types/activity'
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const count = (v: unknown) => typeof v === 'number' && Number.isFinite(v) && v >= 0
const nullableCount = (v: unknown) => v === null || count(v)
const nullableText = (v: unknown) => v === null || typeof v === 'string'
const summary = (v: unknown) => object(v) && nullableCount(v.images) && count(v.api) && count(v.cli)
export function isActivityReport(v: unknown): v is ActivityReport {
  return object(v) && typeof v.scope === 'string' && typeof v.checkedAt === 'string' && count(v.total) && count(v.page) && count(v.pageSize) && summary(v.summary) &&
    object(v.live) && ['queued','running','uncertain','failed'].every(key => count((v.live as Record<string,unknown>)[key])) &&
    Array.isArray(v.users) && v.users.every(p => object(p) && typeof p.id === 'string' && typeof p.name === 'string') &&
    Array.isArray(v.people) && v.people.every(p => object(p) && nullableText(p.id) && typeof p.name === 'string' && nullableText(p.latest) && summary(p)) &&
    Array.isArray(v.records) && v.records.every(r => object(r) && ['id','taskId','task','person','status','createdAt'].every(key => typeof r[key] === 'string') &&
      nullableText(r.personId) && nullableText(r.startedAt) && nullableText(r.finishedAt) && nullableText(r.error) &&
      (r.kind === null || ['initial','api_edit','cli_edit'].includes(String(r.kind))) && nullableCount(r.images) && nullableCount(r.seconds) &&
      (r.retry === null || typeof r.retry === 'boolean') && typeof r.taskDeleted === 'boolean' && typeof r.current === 'boolean')
}
export function createActivityClient(base: string, fetcher: typeof fetch = fetch) {
  const request = createRequest(base, fetcher)
  return (query: ActivityQuery) => {
    const params = new URLSearchParams()
    Object.entries(query).forEach(([key,value]) => { if (value !== undefined && value !== '') params.set(key, String(value)) })
    return request(`/management/activity?${params}`, isActivityReport)
  }
}
export const getActivity = createActivityClient(import.meta.env?.VITE_API_URL || '/api/v1')
