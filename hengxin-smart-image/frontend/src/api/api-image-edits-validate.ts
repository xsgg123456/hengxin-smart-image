import type { ApiChannel, ApiItem, ApiPicture, ApiTask, ApiTaskPage, ApiVersion } from '../types/api-image-edits'
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const text = (v: unknown): v is string => typeof v === 'string'
const id = (v: unknown): v is string => text(v) && v.length > 0
const nullableText = (v: unknown) => v === null || text(v)
const count = (v: unknown): v is number => typeof v === 'number' && Number.isInteger(v) && v >= 0
export const picture = (v: unknown): v is ApiPicture => object(v) && id(v.fileId) && text(v.name) && id(v.url)
const positive = (v: unknown): v is number => count(v) && v > 0
const state = (v: unknown) => text(v) && ['queued', 'running', 'retry_wait', 'collecting', 'succeeded', 'failed', 'uncertain'].includes(v)
const version = (v: unknown): v is ApiVersion => object(v) && positive(v.number) && picture(v.picture)
  && text(v.created) && text(v.operator) && text(v.text) && (v.annotation === null || picture(v.annotation)) && (v.baseVersion === null || positive(v.baseVersion))
const revision = (v: unknown) => v === null || (object(v) && state(v.state) && text(v.text) && text(v.operator)
  && positive(v.baseVersion) && count(v.retries) && nullableText(v.error) && (v.annotation === null || picture(v.annotation)))
const item = (v: unknown): v is ApiItem => object(v) && id(v.id) && count(v.position) && v.position > 0 && (v.source === null || picture(v.source))
  && text(v.state) && ['queued', 'running', 'retry_wait', 'collecting', 'succeeded', 'failed', 'uncertain'].includes(v.state)
  && (v.currentVersion === null || positive(v.currentVersion)) && Array.isArray(v.versions) && v.versions.every(version)
  && new Set(v.versions.map(i => i.number)).size === v.versions.length && revision(v.revision)
  && (v.currentVersion === null ? v.result === null : v.versions.some(i => i.number === v.currentVersion && object(v.result) && i.picture.fileId === v.result.fileId))
  && count(v.retries) && nullableText(v.nextAttemptAt) && nullableText(v.error) && (v.result === null || picture(v.result))
export const task = (v: unknown): v is ApiTask => object(v) && id(v.id) && text(v.name) && text(v.prompt) && text(v.created)
  && text(v.operator) && object(v.batch) && count(v.batch.current) && count(v.batch.total) && count(v.batch.running)
  && text(v.status) && ['queued', 'running', 'succeeded', 'partial_failed', 'failed', 'uncertain'].includes(v.status)
  && (v.material === null || picture(v.material)) && Array.isArray(v.items) && v.items.length > 0 && v.items.every(item)
  && new Set(v.items.map(i => i.position)).size === v.items.length
  && Array.isArray(v.events) && v.events.every(text) && nullableText(v.error)
  && object(v.metrics) && count(v.metrics.requestCount) && count(v.metrics.retryCount)
  && (v.metrics.elapsedSeconds === null || (typeof v.metrics.elapsedSeconds === 'number' && Number.isFinite(v.metrics.elapsedSeconds) && v.metrics.elapsedSeconds >= 0))
export const page = (v: unknown): v is ApiTaskPage => object(v) && Array.isArray(v.items) && v.items.every(task)
  && count(v.total) && count(v.page) && v.page > 0 && count(v.pageSize) && v.pageSize > 0
export const channel = (v: unknown): v is ApiChannel => object(v) && typeof v.enabled === 'boolean' && typeof v.paused === 'boolean' && nullableText(v.reason)
export const accepted = (v: unknown): v is { taskId: string } => object(v) && id(v.taskId)
export const deleted = (v: unknown): v is { deleted: true } => object(v) && v.deleted === true
export const empty = (v: unknown): v is void => v === undefined

export const resumed = (v: unknown): v is { resumed: true } => object(v) && v.resumed === true
