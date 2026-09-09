import type { UsageAttempt, UsageQuery, UsageReport, UsageSummary } from '../../types/management'
import type { User, Workspace } from '../../types/hengxin'
import { ApiError } from './http'

export const shanghaiDay = (iso: string) => new Date(new Date(iso).getTime() + 8 * 3600000).toISOString().slice(0, 10)
export function summarize(attempts: UsageAttempt[], tasks: number): UsageSummary {
  const count = (state: UsageAttempt['state']) => attempts.filter(a => a.state === state).length
  const ended = attempts.filter(a => a.finishedAt !== null)
  const completeUsage = attempts.length > 0 && attempts.every(a => a.usage !== null)
  return { tasks, attempts: attempts.length, initial: attempts.filter(a => a.kind === 'initial').length,
    single: attempts.filter(a => a.kind === 'single').length, whole: attempts.filter(a => a.kind === 'whole').length,
    running: count('running'), success: count('success'), partial: count('partial'), failed: count('failed'), timeout: count('timeout'),
    outputImages: attempts.reduce((sum, a) => sum + a.outputImages, 0), successRate: ended.length ? count('success') / ended.length : null,
    inputTokens: completeUsage ? attempts.reduce((sum, a) => sum + a.usage!.inputTokens, 0) : null,
    outputTokens: completeUsage ? attempts.reduce((sum, a) => sum + a.usage!.outputTokens, 0) : null,
    averageQueueSeconds: attempts.length ? attempts.reduce((sum, a) => sum + a.queueSeconds, 0) / attempts.length : null,
    averageDurationSeconds: ended.length ? ended.reduce((sum, a) => sum + (a.durationSeconds ?? 0), 0) / ended.length : null }
}
export function buildUsage(db: Workspace, records: UsageAttempt[], user: User, query: UsageQuery, users: { id: string; name: string }[]): UsageReport {
  const all = user.role === 'super_admin' || user.role === 'design_manager'
  if (!all && query.userId && query.userId !== user.id) throw new ApiError('FORBIDDEN', '只能查看个人统计', 403)
  for (const value of [query.from, query.to]) if (value && (!/^\d{4}-\d{2}-\d{2}$/.test(value) || !Number.isFinite(Date.parse(value)) || new Date(value).toISOString().slice(0, 10) !== value)) throw new ApiError('VALIDATION', '日期格式无效', 422)
  if (query.from && query.to && query.from > query.to) throw new ApiError('VALIDATION', '开始日期不能晚于结束日期', 422)
  const userId = all ? query.userId : user.id
  const inDate = (value: string) => (!query.from || shanghaiDay(value) >= query.from) && (!query.to || shanghaiDay(value) <= query.to)
  const attempts = [...new Map(records.map(a => [a.id, a])).values()].filter(a => (!userId || a.operatorId === userId) && (!query.mode || a.mode === query.mode) && inDate(a.startedAt))
  const tasks = db.tasks.filter(t => (!userId || t.ownerId === userId) && (!query.mode || t.mode === query.mode) && inDate(t.time))
  const keys = new Set([...attempts.map(a => `${shanghaiDay(a.startedAt)}|${a.operatorId}`), ...tasks.map(t => `${shanghaiDay(t.time)}|${t.ownerId}`)])
  const rows = [...keys].sort().reverse().map(key => {
    const [date, id] = key.split('|')
    const details = attempts.filter(a => shanghaiDay(a.startedAt) === date && a.operatorId === id)
    return { date, userId: id, userName: users.find(u => u.id === id)?.name ?? id, details,
      summary: summarize(details, tasks.filter(t => shanghaiDay(t.time) === date && t.ownerId === id).length) }
  })
  return { scope: all ? 'all' : 'personal', timezone: 'Asia/Shanghai', summary: summarize(attempts, tasks.length), rows, users: users.filter(u => all || u.id === user.id) }
}
export function mockAttempts(db: Workspace, userId: string): UsageAttempt[] {
  return db.tasks.filter(t => t.state !== '排队中').flatMap((t, index) => {
    const finished = t.state !== '执行中'
    const startedAt = new Date(t.time).toISOString()
    const base: UsageAttempt = { id: `attempt-${t.id}`, taskId: t.id, taskName: t.name, creatorId: t.ownerId,
      operatorId: t.ownerId, operatorName: t.ownerId === userId ? '当前模拟用户' : '模拟同事', mode: t.mode, kind: 'initial', startedAt,
      finishedAt: finished ? new Date(Date.parse(startedAt) + 60000).toISOString() : null,
      state: t.state === '执行中' ? 'running' : t.state === '待查看' ? 'success' : t.state === '部分失败' ? 'partial' : 'failed',
      outputImages: t.images.length, queueSeconds: 5, durationSeconds: finished ? 60 : null,
      usage: index === 1 ? null : { inputTokens: 1200, outputTokens: 300 } }
    return index === 0 ? [base, { ...base, id: `attempt-single-${t.id}`, operatorId: userId, kind: 'single', outputImages: 1 },
      { ...base, id: `attempt-whole-${t.id}`, operatorId: 'mock-design-manager', kind: 'whole', usage: null }] : [base]
  })
}
