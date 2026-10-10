import type { ApiUsageEvent, ApiUsageReport, ApiUsageSummary } from '../types/api-management-usage'
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const text = (v: unknown): v is string => typeof v === 'string'
const count = (v: unknown): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v >= 0
const nullableText = (v: unknown) => v === null || text(v)
const rate = (v: unknown) => v === null || (typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1)
const time = (v: unknown) => text(v) && Number.isFinite(Date.parse(v))
const summaryKeys = ['initialImages', 'modifiedImages', 'totalGeneratedImages', 'generatedTasks', 'tasksCreated', 'apiAttempts', 'apiSucceeded', 'apiFailed', 'apiUnknown', 'apiRunning', 'apiRetries', 'apiRetryUnknown', 'cliSubmitted', 'cliStarted', 'cliUnverified', 'cliSucceeded', 'cliFailed', 'cliUnknown', 'cliCandidates', 'generatedVersions', 'unverifiedVersions', 'adoptions', 'restores', 'unverifiedAttribution']
export const generationLabels = { initial: '首次生成', api_edit: 'API 修改生成', cli_edit: 'CLI 修改生成' } as const
export const usageCategoryLabels = { task_created: '创建任务', api_request: 'API 请求', cli_submission: 'CLI 提交', cli_round: 'CLI 启动记录', cli_candidate: 'CLI 候选产出', version_published: '正式版本发布记录', adopt: '手动采用', restore: '恢复版本' } as const
function summary(v: unknown): v is ApiUsageSummary {
  return record(v) && summaryKeys.every(key => count(v[key])) && rate(v.requestSuccessRate)
    && v.inputTokens === null && v.outputTokens === null && v.cost === null
}
function event(v: unknown): v is ApiUsageEvent {
  return record(v) && ['id', 'channel', 'kind', 'taskId', 'taskName', 'creatorId', 'operatorName', 'state'].every(key => text(v[key]))
    && text(v.category) && Object.hasOwn(usageCategoryLabels, v.category) && typeof v.taskDeleted === 'boolean'
    && count(v.generatedImages) && (v.generationType === null || (text(v.generationType) && Object.hasOwn(generationLabels, v.generationType)))
    && nullableText(v.operatorId) && time(v.occurredAt) && (v.completedAt === null || time(v.completedAt)) && count(v.quantity)
    && (v.isRetry === null || typeof v.isRetry === 'boolean') && ['verified', 'historical_unverified'].includes(String(v.attribution))
    && (v.durationSeconds === null || (typeof v.durationSeconds === 'number' && Number.isFinite(v.durationSeconds) && v.durationSeconds >= 0))
}
export function apiUsageReport(v: unknown): v is ApiUsageReport {
  if (!record(v) || !record(v.inventory)) return false
  return ['all', 'personal'].includes(String(v.scope)) && v.timezone === 'Asia/Shanghai'
    && Array.isArray(v.users) && v.users.every(u => record(u) && text(u.id) && text(u.name))
    && ['tasks', 'sourceImages', 'withResultImages', 'succeededImages', 'failedImages', 'pendingImages', 'uncertainImages'].every(key => count((v.inventory as Record<string, unknown>)[key]))
    && rate(v.inventory.deliverySuccessRate) && summary(v.summary)
    && Array.isArray(v.rows) && v.rows.every(r => record(r) && text(r.date) && /^\d{4}-\d{2}-\d{2}$/.test(r.date) && nullableText(r.userId) && text(r.userName) && summary(r.summary))
    && Array.isArray(v.events) && v.events.every(event) && count(v.total) && count(v.page) && v.page > 0 && count(v.pageSize) && v.pageSize > 0 && v.pageSize <= 100
}
