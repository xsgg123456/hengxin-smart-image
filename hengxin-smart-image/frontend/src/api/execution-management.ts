import { createRequest } from './hengxin/http'
import type { ApiMonitorReport, ExecutionSettings } from '../types/execution-management'
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const number = (v: unknown) => typeof v === 'number' && Number.isInteger(v) && v >= 0
const nullableNumber = (v: unknown) => v === null || number(v)
const state = (v: unknown) => ['available', 'unavailable', 'unknown'].includes(String(v))
const channel = (v: unknown) => v === 'api' || v === 'cli'
export function isApiMonitor(v: unknown): v is ApiMonitorReport {
  return record(v) && typeof v.checkedAt === 'string' && typeof v.incidentsTruncated === 'boolean' &&
    Array.isArray(v.channels) && v.channels.length === 2 && new Set(v.channels.map(c => record(c) ? c.channel : null)).size === 2 &&
    v.channels.every(c => record(c) && channel(c.channel) && nullableNumber(c.concurrencyLimit) && nullableNumber(c.imagesPerBatch) && typeof c.enabled === 'boolean' && (c.paused === null || typeof c.paused === 'boolean') && (c.pauseReason === null || typeof c.pauseReason === 'string') && nullableNumber(c.sharedActiveTurns) && nullableNumber(c.otherActiveTurns) && state(c.state) && ['available', 'unknown'].includes(String(c.queueState)) &&
      Array.isArray(c.workers) && c.workers.every(w => record(w) && typeof w.id === 'string' && typeof w.checkedAt === 'string' && state(w.state) && nullableNumber(w.capacity)) &&
      Array.isArray(c.metrics) && c.metrics.every(m => record(m) && typeof m.phase === 'string' && nullableNumber(m.tasks) && nullableNumber(m.images) && nullableNumber(m.turns))) &&
    Array.isArray(v.incidents) && v.incidents.every(i => record(i) && typeof i.taskId === 'string' && typeof i.name === 'string' && channel(i.channel) && typeof i.phase === 'string' && number(i.images))
}
export function isExecutionSettings(v: unknown): v is ExecutionSettings {
  if (!record(v) || !record(v.api) || !record(v.cli) || !record(v.retention)) return false
  const a = v.api, c = v.cli
  return typeof a.enabled === 'boolean' && typeof c.enabled === 'boolean' && typeof c.usesSkills === 'boolean' &&
    typeof v.retention.enabled === 'boolean' && number(v.retention.cacheIdleDays) && number(v.retention.historyIdleDays) &&
    typeof a.quality === 'string' && typeof a.resolution === 'string' && typeof a.sizePolicy === 'string' && number(a.imagesPerRequest) && typeof a.model === 'string' && typeof c.model === 'string' && typeof c.reasoningEffort === 'string' &&
    [a.taskConcurrency, a.imagesPerBatch, a.requestTimeoutSeconds, a.downloadTimeoutSeconds, a.leaseSeconds,
      c.concurrency, c.capacity, c.timeoutSeconds, c.timeoutCapacity, v.maxUploadBytes].every(number)
}
export function createExecutionManagement(base: string, fetcher: typeof fetch = fetch) {
  const request = createRequest(base, fetcher)
  return {
    getApiMonitor: () => request('/management/api-monitor', isApiMonitor),
    getExecutionSettings: () => request('/management/execution-settings', isExecutionSettings)
  }
}
export const { getApiMonitor, getExecutionSettings } = createExecutionManagement(import.meta.env?.VITE_API_URL || '/api/v1')
