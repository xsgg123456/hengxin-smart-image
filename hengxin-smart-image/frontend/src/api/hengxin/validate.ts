import type { Accepted, Archive, Picture, Task, Template, User, Workspace } from '../../types/hengxin'

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
export const user: Guard<User> = (value): value is User => record(value) && id(value.id) && text(value.name)
  && text(value.status) && ['pending', 'active', 'disabled'].includes(value.status)
  && (value.role === null || (text(value.role) && ['super_admin', 'design_manager', 'designer', 'operator'].includes(value.role)))
export const template: Guard<Template> = (value): value is Template => record(value)
  && id(value.id) && text(value.name) && mode(value.mode) && list(value.images, picture)
  && text(value.skill) && typeof value.active === 'boolean' && number(value.version) && id(value.ownerId)
const task: Guard<Task> = (value): value is Task => record(value)
  && id(value.id) && text(value.name) && mode(value.mode) && text(value.template)
  && id(value.skillVersionId) && id(value.ownerId) && (value.sessionId === null || id(value.sessionId))
  && state(value.state) && (value.progress === null || (number(value.progress) && value.progress >= 0 && value.progress <= 100))
  && list(value.images, picture) && list(value.sources, picture) && list(value.feedback, text)
  && text(value.time) && typeof value.archived === 'boolean' && id(value.currentRoundId)
export const archive: Guard<Archive> = (value): value is Archive => record(value)
  && id(value.id) && text(value.name) && mode(value.mode) && list(value.images, picture)
  && text(value.time) && id(value.ownerId) && list(value.imageVersionIds, id)
export const workspace: Guard<Workspace> = (value): value is Workspace => record(value)
  && list(value.templates, template) && list(value.tasks, task) && list(value.archives, archive)
export const accepted: Guard<Accepted> = (value): value is Accepted => record(value)
  && id(value.taskId) && id(value.roundId) && value.state === '排队中'
export const noContent: Guard<void> = (value): value is void => value === undefined
