import type { DraftImport, DraftsApi, RequirementDraft } from '../src/api/overseas/requirement-drafts'
import { emptyTaskDraft } from '../src/api/overseas/tasks'
import { createDraftStorage } from '../src/views/overseas/requirement-draft-storage'
export const clone = <T>(value: T): T => JSON.parse(JSON.stringify(value))
export const fresh = (state?: DraftImport['state']): RequirementDraft => ({
  id: 'draft', version: 1, fields: emptyTaskDraft(), source: null, materials: [], updatedAt: '', submitKey: 'key',
  imports: state ? [{ id: 'import', sourceFileId: 'source', filename: 'file.pptx', size: 30, kind: 'requirement', state, progress: 0, error: null, materialId: null }] : []
})
export function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (reason: unknown) => void
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no })
  return { promise, resolve, reject }
}
export function fixture(state?: DraftImport['state']) {
  const data = { server: fresh(state), reads: 0, writes: 0, events: [] as string[], readError: '', saveError: '' }
  const values = new Map<string, string>()
  const storage = createDraftStorage({ getItem: key => values.get(key) || null, setItem: (key, value) => { values.set(key, value) }, removeItem: key => { values.delete(key) } }, 'draft')
  const api: DraftsApi = {
    get: async () => { data.reads++; data.events.push('GET'); if (data.readError) throw Error(data.readError); return clone(data.server) },
    save: async (_version, fields) => { data.writes++; data.events.push('PUT'); if (data.saveError) throw Error(data.saveError); data.server = { ...data.server, version: data.server.version + 1, fields: clone(fields) }; return clone(data.server) },
    source: async () => clone(data.server), retry: async () => clone(data.server), cancel: async () => clone(data.server), removeMaterial: async () => clone(data.server), clear: async () => clone(data.server), query: async sku => ({ sku, count: 0, truncated: false, list: [] })
  }
  return { api, storage, data }
}
