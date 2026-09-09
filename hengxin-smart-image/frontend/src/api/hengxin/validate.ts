import type { Accepted, Archive, Picture, Task, Template, User, Workspace, SkillVersion, PageResult, TaskDetailData, TaskPage, ResultSlot, ResultVersion, Round, DeletionReceipt } from '../../types/hengxin'

type Guard<T> = (value: unknown) => value is T
const record = (value: unknown): value is Record<string, unknown> => value !== null && typeof value === 'object' && !Array.isArray(value)
const text = (value: unknown): value is string => typeof value === 'string'
const id = (value: unknown): value is string => text(value) && value.trim().length > 0
const number = (value: unknown): value is number => typeof value === 'number' && Number.isFinite(value)
const list = <T>(value: unknown, guard: Guard<T>): value is T[] => Array.isArray(value) && value.every(guard)
const mode = (value: unknown) => text(value) && ['wallpaper', 'product', 'text'].includes(value)
const state = (value: unknown) => text(value) && ['排队中', '执行中', '待查看', '部分失败', '失败'].includes(value)
const picture: Guard<Picture> = (value): value is Picture => record(value) && text(value.name) && text(value.url)
  && (value.version === undefined || (number(value.version) && value.version >= 1))
  && (value.fileId === undefined || id(value.fileId))
export const uploadedPicture: Guard<Picture> = (value): value is Picture => picture(value) && id(value.fileId)
export const user: Guard<User> = (value): value is User => record(value) && id(value.id) && text(value.name)
  && text(value.status) && ['pending', 'active', 'disabled'].includes(value.status)
  && (value.role === null || (text(value.role) && ['super_admin', 'design_manager', 'designer', 'operator'].includes(value.role)))
export const template: Guard<Template> = (value): value is Template => record(value)
  && (value.skillBinding === undefined || value.skillBinding === 'module_default' || value.skillBinding === 'specific')
  && id(value.id) && text(value.name) && mode(value.mode) && list(value.images, picture)
  && text(value.skill) && typeof value.active === 'boolean' && number(value.version) && id(value.ownerId)
  && (value.skillVersionId === null || id(value.skillVersionId)) && text(value.notes) && text(value.updatedAt)
export const templateList: Guard<Template[]> = (value): value is Template[] => list(value, template)
const skill: Guard<SkillVersion> = (value): value is SkillVersion => record(value)
  && id(value.id) && text(value.name) && mode(value.mode) && text(value.version)
  && text(value.checksum) && typeof value.isDefault === 'boolean'
  && text(value.status) && ['uploaded', 'installing', 'available', 'disabled', 'failed'].includes(value.status)
export const skillList: Guard<SkillVersion[]> = (value): value is SkillVersion[] => list(value, skill)
export const templatePage: Guard<PageResult<Template>> = (value): value is PageResult<Template> => record(value)
  && list(value.items, template) && number(value.total) && Number.isInteger(value.total) && value.total >= 0
  && number(value.page) && Number.isInteger(value.page) && value.page >= 1
  && number(value.pageSize) && Number.isInteger(value.pageSize) && value.pageSize >= 1
const task: Guard<Task> = (value): value is Task => record(value)
  && (value.executionSource === undefined || value.executionSource === 'fixture' || value.executionSource === 'unavailable' || value.executionSource === 'cli')
  && id(value.id) && text(value.name) && mode(value.mode) && text(value.template)
  && (value.templateSnapshot === undefined || template(value.templateSnapshot))
  && id(value.skillVersionId) && id(value.ownerId) && (value.sessionId === null || id(value.sessionId))
  && state(value.state) && (value.progress === null || (number(value.progress) && value.progress >= 0 && value.progress <= 100))
  && list(value.images, picture) && list(value.sources, picture) && list(value.feedback, text)
  && text(value.time) && typeof value.archived === 'boolean' && id(value.currentRoundId)
  && (value.outputCount === undefined || (number(value.outputCount) && Number.isInteger(value.outputCount) && value.outputCount > 0))
  && (value.error === undefined || value.error === null || text(value.error))
export const archive: Guard<Archive> = (value): value is Archive => record(value)
  && id(value.id) && text(value.name) && mode(value.mode) && list(value.images, picture)
  && text(value.time) && id(value.ownerId) && list(value.imageVersionIds, id)
export const workspace: Guard<Workspace> = (value): value is Workspace => record(value)
  && list(value.templates, template) && list(value.tasks, task) && list(value.archives, archive)
export const accepted: Guard<Accepted> = (value): value is Accepted => record(value)
  && id(value.taskId) && id(value.roundId) && value.state === '排队中'
export const noContent: Guard<void> = (value): value is void => value === undefined
const count = (value: unknown): value is number => number(value) && Number.isInteger(value) && value >= 0
const version: Guard<ResultVersion> = (value): value is ResultVersion => picture(value) && record(value)
  && id(value.id) && count(value.version) && value.version > 0 && id(value.roundId) && text(value.createdAt)
const slot: Guard<ResultSlot> = (value): value is ResultSlot => record(value) && count(value.slot)
  && list(value.versions, version) && (value.error === null || text(value.error))
  && (value.currentVersionId === null || (id(value.currentVersionId) && value.versions.some(v => v.id === value.currentVersionId)))
const round: Guard<Round> = (value): value is Round => record(value)
  && (value.executionConfig === undefined || (record(value.executionConfig) && ['version','concurrency','timeoutSeconds'].every(key => record(value.executionConfig) && count(value.executionConfig[key]) && Number(value.executionConfig[key]) > 0)))
  && id(value.id) && id(value.taskId) && id(value.operatorId) && (value.target === null || count(value.target))
  && text(value.note) && state(value.state) && text(value.createdAt)
  && (value.startedAt === null || text(value.startedAt)) && (value.finishedAt === null || text(value.finishedAt))
  && (value.error === null || text(value.error))
export const taskDetail: Guard<TaskDetailData> = (value): value is TaskDetailData => {
  if (!record(value) || !task(value.task) || !list(value.slots, slot) || !list(value.rounds, round)) return false
  const control = value.executionControl
  if (!record(control) || typeof control.canRevise !== 'boolean' || typeof control.canRetry !== 'boolean'
    || !(control.blockedReason === null || id(control.blockedReason))) return false
  const taskId = value.task.id
  return value.slots.every((s, i) => s.slot === i) && value.rounds.every(r => r.taskId === taskId)
    && (value.task.outputCount === undefined || value.slots.length === value.task.outputCount)
}
const page = (value: unknown): value is Record<string, unknown> => record(value)
  && count(value.total) && count(value.page) && value.page > 0 && count(value.pageSize) && value.pageSize > 0
export const taskPage: Guard<TaskPage> = (value): value is TaskPage => {
  if (!page(value) || !list(value.items, task) || !record(value.stats)) return false
  const stats = value.stats
  return ['total', 'processing', 'ready', 'archived'].every(key => count(stats[key]))
}
export const archivePage: Guard<PageResult<Archive>> = (value): value is PageResult<Archive> => page(value) && list(value.items, archive)
export const deletion: Guard<DeletionReceipt> = (value): value is DeletionReceipt => record(value)
  && id(value.id) && id(value.operatorId) && text(value.deletedAt)
