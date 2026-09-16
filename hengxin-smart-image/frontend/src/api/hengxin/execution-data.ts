export const stages = {
  queued: '排队中', preparing: '准备素材', starting: '启动执行器', generating: '模型处理',
  validating: '校验结果', storing: '存储图片', publishing: '发布结果', completed: '已完成',
  failed: '执行失败', cancelled: '已取消', uncertain: '状态待核实'
} as const
export type ExecutionStage = keyof typeof stages
export const CURRENT_EXECUTION_ROUND = 'current'
export function executionRoundSelection(selected: string, currentRoundId?: string | null) {
  const historical = selected !== CURRENT_EXECUTION_ROUND
  return { historical, roundId: historical ? selected : currentRoundId || '' }
}
export type ExecutionStatus = 'queued' | 'running' | 'collecting' | 'cancelling' | 'uncertain' | 'failed' | 'cancelled' | 'succeeded' | 'partial'
export interface ExecutionData {
  taskId: string; roundId: string; status: ExecutionStatus; source: 'cli' | 'fixture' | 'unavailable'
  diagnosticId: string | null; stage: ExecutionStage; label: string
  startedAt: string | null; finishedAt: string | null; updatedAt: string | null; lastActivityAt: string | null
  totalImages: number; detectedImages: number | null; legacy: boolean
  events: { sequence: number; stage: ExecutionStage; message: string; at: string | null }[]
  failure: { code: string; message: string; action: string; stage: ExecutionStage;
    slotErrors: { slot: number; code: string; message: string }[] } | null
}
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const text = (v: unknown): v is string => typeof v === 'string' && v.trim().length > 0
const count = (v: unknown): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v >= 0
const stage = (v: unknown): v is ExecutionStage => typeof v === 'string' && Object.hasOwn(stages, v)
const time = (v: unknown) => v === null || (typeof v === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(v) && Number.isFinite(Date.parse(v)))
export function isExecutionData(v: unknown): v is ExecutionData {
  if (!record(v) || !text(v.taskId) || !text(v.roundId) || !text(v.status) ||
    !['queued', 'running', 'collecting', 'cancelling', 'uncertain', 'failed', 'cancelled', 'succeeded', 'partial'].includes(v.status) ||
    (v.source !== 'cli' && v.source !== 'fixture' && v.source !== 'unavailable') || !stage(v.stage) || !text(v.label) ||
    !(v.diagnosticId === null || (typeof v.diagnosticId === 'string' && /^[\da-f]{8}-[\da-f]{4}-[\da-f]{4}-[\da-f]{4}-[\da-f]{12}$/i.test(v.diagnosticId))) ||
    ![v.startedAt, v.finishedAt, v.updatedAt, v.lastActivityAt].every(time) ||
    !count(v.totalImages) || !(v.detectedImages === null || count(v.detectedImages)) || typeof v.legacy !== 'boolean') return false
  if (!Array.isArray(v.events) || v.events.length > 100 || !v.events.every(e => record(e) && count(e.sequence) && stage(e.stage) && text(e.message) && time(e.at))) return false
  const f = v.failure
  return f === null || (record(f) && text(f.code) && text(f.message) && text(f.action) && stage(f.stage) &&
    Array.isArray(f.slotErrors) && f.slotErrors.every(e => record(e) && count(e.slot) && text(e.code) && text(e.message)))
}
export function executionPollDelay(status: ExecutionStatus): number | null {
  if (status === 'uncertain') return 5000
  return ['queued', 'running', 'collecting', 'cancelling'].includes(status) ? 2000 : null
}
export function executionStageLabel(data: ExecutionData) {
  const terminal = { failed: '执行失败', cancelled: '已取消', succeeded: '已完成', partial: '部分失败' }
  return Object.hasOwn(terminal, data.status) ? terminal[data.status as keyof typeof terminal] : data.label
}
export function elapsedSeconds(data: ExecutionData, now: number): number | null {
  if (!data.startedAt) return null
  const end = data.finishedAt ?? (executionPollDelay(data.status) === null ? data.updatedAt : null)
  if (!end && executionPollDelay(data.status) === null) return null
  return Math.max(0, Math.floor(((end ? Date.parse(end) : now) - Date.parse(data.startedAt)) / 1000))
}
export function activityIsStale(data: ExecutionData, now: number) {
  const activity = data.lastActivityAt ?? data.updatedAt ?? data.startedAt
  return executionPollDelay(data.status) !== null && !!activity && now - Date.parse(activity) >= 60000
}
export function formatExecutionTime(value: string | null) {
  return value ? new Date(value).toLocaleString('zh-CN', { hour12: false }) : '未提供'
}
