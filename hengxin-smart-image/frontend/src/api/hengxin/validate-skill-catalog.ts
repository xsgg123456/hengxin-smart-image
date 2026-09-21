import type { CatalogSkill, SkillSync, SkillSyncAccepted } from '../../types/management'
const record = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const text = (v: unknown): v is string => typeof v === 'string'
export const catalogSkill = (v: unknown): v is CatalogSkill => record(v)
  && text(v.id) && !!v.id && text(v.name) && !!v.name && text(v.description)
  && (v.mode === null || (text(v.mode) && ['wallpaper', 'product', 'text'].includes(v.mode)))
  && text(v.status) && ['available', 'disabled', 'invalid', 'needs_type', 'syncing'].includes(v.status)
  && typeof v.isDefault === 'boolean' && typeof v.referenced === 'boolean'
  && (v.error === null || text(v.error)) && text(v.updatedAt)
export const catalogList = (v: unknown): v is CatalogSkill[] => Array.isArray(v) && v.every(catalogSkill)
export const syncState = (v: unknown): v is SkillSync => record(v)
  && (v.jobId === null || (text(v.jobId) && !!v.jobId))
  && text(v.status) && ['idle', 'queued', 'running', 'succeeded', 'failed'].includes(v.status)
  && (v.error === null || text(v.error))
export const syncAccepted = (v: unknown): v is SkillSyncAccepted => record(v)
  && text(v.jobId) && !!v.jobId && text(v.status) && ['queued', 'running'].includes(v.status)
