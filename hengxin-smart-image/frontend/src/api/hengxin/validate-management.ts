import type { ManagedSettings, ManagedSkill, ManagedUser, MonitorReport, UsageAttempt, UsageReport, UsageSummary } from '../../types/management'
import type { PageResult, SystemConfig } from '../../types/hengxin'
import { user, skillList } from './validate'
type Guard<T> = (v: unknown) => v is T
const obj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const str = (v: unknown): v is string => typeof v === 'string'
const num = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v) && v >= 0
const integer = (v: unknown): v is number => num(v) && Number.isInteger(v)
const date = (v: unknown) => str(v) && Number.isFinite(Date.parse(v))
const nullableDate = (v: unknown) => v === null || date(v)
const nullableNum = (v: unknown) => v === null || num(v)
const list = <T>(v: unknown, guard: Guard<T>): v is T[] => Array.isArray(v) && v.every(guard)
const choice = (v: unknown, values: string[]) => str(v) && values.includes(v)
const summary: Guard<UsageSummary> = (v): v is UsageSummary => obj(v)
  && ['tasks', 'attempts', 'initial', 'single', 'whole', 'running', 'success', 'partial', 'failed', 'timeout', 'outputImages'].every(k => integer(v[k]))
  && ['inputTokens', 'outputTokens', 'averageQueueSeconds', 'averageDurationSeconds', 'successRate'].every(k => nullableNum(v[k]))
  && (v.successRate === null || (num(v.successRate) && v.successRate <= 1))
const attempt: Guard<UsageAttempt> = (v): v is UsageAttempt => obj(v)
  && ['id', 'taskId', 'taskName', 'creatorId', 'operatorId', 'operatorName'].every(k => str(v[k]))
  && choice(v.mode, ['wallpaper', 'product', 'text']) && choice(v.kind, ['initial', 'single', 'whole'])
  && choice(v.state, ['running', 'success', 'partial', 'failed', 'timeout']) && date(v.startedAt) && nullableDate(v.finishedAt)
  && (v.state === 'running' ? v.finishedAt === null : v.finishedAt !== null) && integer(v.outputImages) && num(v.queueSeconds) && nullableNum(v.durationSeconds)
  && (v.usage === null || (obj(v.usage) && integer(v.usage.inputTokens) && integer(v.usage.outputTokens)))
export const usage: Guard<UsageReport> = (v): v is UsageReport => obj(v) && choice(v.scope, ['personal', 'all']) && v.timezone === 'Asia/Shanghai' && summary(v.summary)
  && Array.isArray(v.users) && v.users.every(u => obj(u) && str(u.id) && str(u.name))
  && Array.isArray(v.rows) && v.rows.every(r => obj(r) && date(r.date) && str(r.userId) && str(r.userName) && summary(r.summary) && list(r.details, attempt))
export const managedUser: Guard<ManagedUser> = (v): v is ManagedUser => user(v) && obj(v) && str(v.department) && nullableDate(v.lastLoginAt)
export const userPage: Guard<PageResult<ManagedUser>> = (v): v is PageResult<ManagedUser> => obj(v) && list(v.items, managedUser) && integer(v.total) && integer(v.page) && v.page > 0 && integer(v.pageSize) && v.pageSize > 0
export const managedSkill: Guard<ManagedSkill> = (v): v is ManagedSkill => skillList([v]) && obj(v) && nullableDate(v.installedAt) && (v.node === null || str(v.node)) && date(v.updatedAt) && (v.error === null || str(v.error)) && typeof v.referenced === 'boolean'
export const managedSkills: Guard<ManagedSkill[]> = (v): v is ManagedSkill[] => list(v, managedSkill)
export const skillDefaults: Guard<SystemConfig['defaultSkillIds']> = (v): v is SystemConfig['defaultSkillIds'] => obj(v)
  && ['wallpaper', 'product', 'text'].every(k => v[k] === null || (str(v[k]) && v[k].trim().length > 0))
export const monitor: Guard<MonitorReport> = (v): v is MonitorReport => {
  if (obj(v) && v.issue !== undefined && (!obj(v.issue) || !str(v.issue.code) || !str(v.issue.message))) return false
  if (!obj(v) || !nullableDate(v.checkedAt) || !choice(v.state, ['idle', 'running', 'unavailable', 'unknown']) || !integer(v.queueSize) || !integer(v.runningCount)
    || !Array.isArray(v.tasks) || !v.tasks.every(t => obj(t) && ['taskId', 'name', 'operatorName', 'state'].every(k => str(t[k])) && (t.sessionId === null || str(t.sessionId)) && nullableNum(t.elapsedSeconds) && (t.error === null || str(t.error)))) return false
  const d = v.detail
  return d === null || (obj(d) && Array.isArray(d.workers) && d.workers.every(w => obj(w) && str(w.id) && date(w.checkedAt) && choice(w.state, ['idle', 'running', 'unavailable', 'unknown']) && ['queueSize', 'runningCount', 'concurrency'].every(k => integer(w[k])))
    && (d.cliVersion === null || str(d.cliVersion)) && (d.configured === null || typeof d.configured === 'boolean') && (d.lastResult === null || str(d.lastResult)) && nullableNum(d.freeDiskBytes)
    && Array.isArray(d.dependencies) && d.dependencies.every(x => obj(x) && str(x.name) && choice(x.state, ['available', 'unavailable', 'unknown']) && str(x.message)))
}
export const settings: Guard<ManagedSettings> = (v): v is ManagedSettings => obj(v) && integer(v.version) && v.version > 0 && integer(v.concurrency) && v.concurrency > 0 && integer(v.timeoutSeconds) && v.timeoutSeconds > 0 && integer(v.maxUploadBytes) && v.maxUploadBytes > 0
  && obj(v.defaultSkillIds) && ['wallpaper', 'product', 'text'].every(k => v.defaultSkillIds && obj(v.defaultSkillIds) && (v.defaultSkillIds[k] === null || str(v.defaultSkillIds[k])))
  && obj(v.dingtalk) && ['corpId', 'appId', 'callbackDomain'].every(k => obj(v.dingtalk) && str(v.dingtalk[k])) && choice(v.dingtalk.state, ['unconfigured', 'ready', 'error'])
  && Array.isArray(v.audit) && v.audit.every(a => obj(a) && ['id', 'operatorId', 'operatorName'].every(k => str(a[k])) && date(a.changedAt) && integer(a.version) && Array.isArray(a.fields) && a.fields.every(str))
