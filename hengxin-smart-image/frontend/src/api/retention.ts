import { createRequest } from './hengxin/http'
import type { RetentionApi, RetentionRecords, RetentionRow, RetentionSummary } from '../types/retention'
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const integer = (v: unknown) => typeof v === 'number' && Number.isSafeInteger(v) && v >= 0
const time = (v: unknown) => typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T.*(?:Z|[+-]\d{2}:\d{2})$/i.test(v) && Number.isFinite(Date.parse(v))
const nullableTime = (v: unknown) => v === null || time(v)
export const retentionResults = ['cache_cleared', 'complete', 'objects_pending', 'retry', 'protected', 'waiting', 'due', 'processing'] as const
export function isRetentionSummary(v: unknown): v is RetentionSummary {
  if (!record(v) || !record(v.policy) || !record(v.service) || !record(v.counts)) return false
  const p = v.policy, s = v.service, c = v.counts
  return time(v.checkedAt) && nullableTime(v.statisticsSince) && typeof p.enabled === 'boolean' &&
    ['cacheIdleHours', 'historyIdleHours', 'batchSize', 'scanIntervalSeconds', 'detailRetentionDays'].every(k => integer(p[k]) && Number(p[k]) > 0) &&
    ['online', 'offline', 'unknown', 'disabled'].includes(String(s.state)) && ['running', 'completed', 'failed', 'unknown'].includes(String(s.scanState)) &&
    ['heartbeatAt', 'lastStartedAt', 'lastFinishedAt', 'nextScanAt'].every(k => nullableTime(s[k])) &&
    ['cacheToday', 'cacheTotal', 'historyToday', 'historyTotal', 'retry', 'overdue', 'protected', 'objectsPending'].every(k => c[k] === null || integer(c[k]))
}
export function isRetentionRow(v: unknown): v is RetentionRow {
  return record(v) && ['id', 'resourceId', 'taskName', 'detail'].every(k => typeof v[k] === 'string') &&
    (v.taskId === null || typeof v.taskId === 'string') && ['cache', 'history'].includes(String(v.kind)) &&
    retentionResults.some(r => r === v.result) && ['history', 'pending'].includes(String(v.detailTab)) &&
    ['imagePosition', 'turnsRemoved', 'objectsRemoved', 'objectsPending'].every(k => integer(v[k])) &&
    nullableTime(v.processedAt) && nullableTime(v.nextAttemptAt) && time(v.lastActivityAt) && time(v.dueAt) && typeof v.taskDeleted === 'boolean'
}
export function isRetentionRecords(v: unknown): v is RetentionRecords {
  return record(v) && Array.isArray(v.items) && v.items.every(isRetentionRow) && integer(v.total) &&
    integer(v.page) && Number(v.page) > 0 && integer(v.pageSize) && Number(v.pageSize) > 0 && Number(v.pageSize) <= 100
}
export function createRetentionApi(base: string, fetcher: typeof fetch = fetch): RetentionApi {
  const request = createRequest(base, fetcher)
  return {
    summary: () => request('/management/retention/summary', isRetentionSummary),
    records: query => {
      const params = new URLSearchParams()
      for (const [key, value] of Object.entries(query)) if (value !== undefined && value !== '') params.set(key, String(value))
      return request(`/management/retention/records?${params}`, isRetentionRecords)
    },
    detail: (id, tab) => request(`/management/retention/records/${encodeURIComponent(id)}?tab=${tab}`, isRetentionRow)
  }
}
export const retentionApi = createRetentionApi(import.meta.env?.VITE_API_URL || '/api/v1')
