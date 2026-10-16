import type { ManagedSettings, ManagedUser } from '../../types/management'
import type { PageResult } from '../../types/hengxin'
import { user } from './validate'
type Guard<T> = (v: unknown) => v is T
const obj = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const str = (v: unknown): v is string => typeof v === 'string'
const num = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v) && v >= 0
const integer = (v: unknown): v is number => num(v) && Number.isInteger(v)
const date = (v: unknown) => str(v) && Number.isFinite(Date.parse(v))
const nullableDate = (v: unknown) => v === null || date(v)
const list = <T>(v: unknown, guard: Guard<T>): v is T[] => Array.isArray(v) && v.every(guard)
const choice = (v: unknown, values: string[]) => str(v) && values.includes(v)
export const managedUser: Guard<ManagedUser> = (v): v is ManagedUser => user(v) && obj(v) && str(v.department) && nullableDate(v.lastLoginAt)
export const userPage: Guard<PageResult<ManagedUser>> = (v): v is PageResult<ManagedUser> => obj(v) && list(v.items, managedUser) && integer(v.total) && integer(v.page) && v.page > 0 && integer(v.pageSize) && v.pageSize > 0
export const settings: Guard<ManagedSettings> = (v): v is ManagedSettings => obj(v) && integer(v.version) && v.version > 0 && integer(v.capacity) && v.capacity > 0 && integer(v.concurrency) && v.concurrency > 0 && v.concurrency <= v.capacity && integer(v.timeoutSeconds) && v.timeoutSeconds > 0 && integer(v.timeoutCapacity) && v.timeoutCapacity >= 10 && v.timeoutCapacity <= 7200 && v.timeoutSeconds <= v.timeoutCapacity && integer(v.maxUploadBytes) && v.maxUploadBytes >= 1048576 && v.maxUploadBytes <= 10485760
  && obj(v.dingtalk) && ['corpId', 'appId', 'callbackDomain'].every(k => obj(v.dingtalk) && str(v.dingtalk[k])) && choice(v.dingtalk.state, ['unconfigured', 'ready', 'error'])
  && Array.isArray(v.audit) && v.audit.every(a => obj(a) && ['id', 'operatorId', 'operatorName'].every(k => str(a[k])) && date(a.changedAt) && integer(a.version) && Array.isArray(a.fields) && a.fields.every(str))
