import { randomUUID } from '../../utils/browser-crypto'
import { isDraftFields, type RequirementDraft, type DraftFields } from '@/api/overseas/requirement-drafts'
import { record } from '@/api/identity/request'
import type { TaskDraft } from '@/api/overseas/tasks'
export interface DraftSnapshot { id: string; version: number; fields: DraftFields; source: RequirementDraft['source']; pendingUploads: string[]; submission?: { body: TaskDraft; key: string } }
export interface DraftStorage { read(): DraftSnapshot | undefined; write(value: DraftSnapshot): void; clear(): void }
export function draftStorageKey(actorId: string, context: string) { return `hx:overseas:requirement-draft:${encodeURIComponent(actorId)}:${context}` }
export function createDraftStorage(storage: Pick<Storage, 'getItem' | 'setItem' | 'removeItem'>, key: string): DraftStorage {
  return {
    read() {
      const raw = storage.getItem(key)
      if (!raw) return
      const v: unknown = JSON.parse(raw)
      if (!record(v) || typeof v.id !== 'string' || !Number.isInteger(v.version) || !isDraftFields(v.fields) || !Array.isArray(v.pendingUploads) || !v.pendingUploads.every(n => typeof n === 'string')) throw Error('本地草稿格式异常，已保留原副本')
      if (!(v.source === null || (record(v.source) && typeof v.source.sku === 'string' && typeof v.source.requirementId === 'string'))) throw Error('本地来源信息异常，已保留原副本')
      if (v.submission !== undefined && (!record(v.submission) || typeof v.submission.key !== 'string' || !record(v.submission.body) || !Array.isArray(v.submission.body.materialIds) || !v.submission.body.materialIds.every(id => typeof id === 'string') || !isDraftFields(v.submission.body))) throw Error('本地提交信息异常，已保留原副本')
      return v as unknown as DraftSnapshot
    },
    write: value => storage.setItem(key, JSON.stringify(value)), clear: () => storage.removeItem(key)
  }
}
export function browserDraftStorage(actorId: string): DraftStorage {
  // sessionStorage isolates tabs while retaining the same key over reloads.
  const contextKey = 'hx:requirement-draft:tab'
  let context = sessionStorage.getItem(contextKey)
  if (!context) { context = randomUUID(); sessionStorage.setItem(contextKey, context) }
  return createDraftStorage(localStorage, draftStorageKey(actorId, context))
}
export function sameFields(a: DraftFields, b: DraftFields) { return JSON.stringify(a) === JSON.stringify(b) }
export function sameSource(a: RequirementDraft['source'], b: RequirementDraft['source']) { return JSON.stringify(a) === JSON.stringify(b) }
