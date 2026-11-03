import { createIdentityRequest, record } from '../identity/request'
import { isMaterial, type Material, type MaterialKind } from './materials'
import type { Designer, TaskDraft } from './tasks'
export type DraftFields = Omit<TaskDraft, 'materialIds' | 'draftId' | 'draftVersion'>
export interface SourceFile { id: string; filename: string; size: number; contentType: string; category: string }
export interface Requirement { id: string; platformName: string; brandName: string; title: string; productName: string; language: string; designerName: string; status: string; createdAt: string; files: SourceFile[]; matchedDesigner: Designer | null }
export interface SourceResult { sku: string; count: number; truncated: boolean; list: Requirement[] }
export interface DraftImport { id: string; sourceFileId: string; filename: string; size: number; kind: MaterialKind; state: 'queued' | 'running' | 'ready' | 'failed' | 'cancelled'; progress: number; error: string | null; materialId: string | null }
export interface RequirementDraft { id: string; version: number; fields: DraftFields; source: { sku: string; requirementId: string } | null; materials: Material[]; imports: DraftImport[]; updatedAt: string; submitKey: string; lastSubmittedTaskId?: string | null; lastSubmittedKey?: string | null; matchedDesigner?: Designer | null }
export interface DraftsApi {
  get(): Promise<RequirementDraft>
  save(version: number, fields: DraftFields): Promise<RequirementDraft>
  source(version: number, sku: string, requirementId: string, fields: DraftFields): Promise<RequirementDraft>
  retry(id: string): Promise<RequirementDraft>
  cancel(id: string): Promise<RequirementDraft>
  removeMaterial(id: string): Promise<RequirementDraft>
  clear(version: number): Promise<RequirementDraft>
  query(sku: string): Promise<SourceResult>
}
const text = (v: unknown): v is string => typeof v === 'string'
export function isDraftFields(v: unknown): v is DraftFields {
  return record(v) && ['name','productName','brand','platform','language','market','designerId'].every(k => text(v[k])) && Array.isArray(v.skus) && v.skus.length === 1 && v.skus.every(s => record(s) && text(s.code))
}
export function isRequirementDraft(v: unknown): v is RequirementDraft {
  return record(v) && text(v.id) && Number.isInteger(v.version) && Number(v.version) > 0 && isDraftFields(v.fields) && text(v.submitKey) && text(v.updatedAt)
    && (v.source === null || (record(v.source) && text(v.source.sku) && text(v.source.requirementId)))
    && Array.isArray(v.materials) && v.materials.every(isMaterial) && Array.isArray(v.imports) && v.imports.every(i => record(i)
      && ['id','sourceFileId','filename'].every(k => text(i[k])) && Number.isFinite(i.size) && Number(i.size) >= 0
      && ['requirement','competitor'].includes(String(i.kind)) && ['queued','running','ready','failed','cancelled'].includes(String(i.state))
      && Number.isFinite(i.progress) && Number(i.progress) >= 0 && Number(i.progress) <= 100 && (i.error === null || text(i.error)) && (i.materialId === null || text(i.materialId)))
    && (v.lastSubmittedTaskId == null || text(v.lastSubmittedTaskId)) && (v.lastSubmittedKey == null || text(v.lastSubmittedKey))
    && (v.matchedDesigner == null || (record(v.matchedDesigner) && text(v.matchedDesigner.id) && text(v.matchedDesigner.name) && text(v.matchedDesigner.department)))
}
export function isSourceResult(v: unknown): v is SourceResult {
  return record(v) && text(v.sku) && Number.isInteger(v.count) && Number(v.count) >= 0 && typeof v.truncated === 'boolean' && Array.isArray(v.list) && v.list.every(r => record(r)
    && ['id','platformName','brandName','title','productName','language','designerName','status','createdAt'].every(k => text(r[k]))
    && (r.matchedDesigner === null || (record(r.matchedDesigner) && text(r.matchedDesigner.id) && text(r.matchedDesigner.name) && text(r.matchedDesigner.department)))
    && Array.isArray(r.files) && r.files.every(f => record(f) && text(f.id) && text(f.filename) && Number.isFinite(f.size) && Number(f.size) >= 0))
}
export function createDraftsApi(fetcher: typeof fetch = fetch): DraftsApi {
  const request = createIdentityRequest(fetcher), base = '/api/overseas/v1/requirement-draft'
  return {
    get: () => request(base, isRequirementDraft),
    save: (version, fields) => request(base, isRequirementDraft, { version, fields }, { method: 'PUT' }),
    source: (version, sku, requirementId, fields) => request(`${base}/source`, isRequirementDraft, { version, sku, requirementId, fields }, { timeoutMs: 45000 }),
    retry: id => request(`${base}/imports/${encodeURIComponent(id)}/retry`, isRequirementDraft, {}),
    cancel: id => request(`${base}/imports/${encodeURIComponent(id)}`, isRequirementDraft, {}, { method: 'DELETE' }),
    removeMaterial: id => request(`${base}/materials/${encodeURIComponent(id)}`, isRequirementDraft, {}, { method: 'DELETE' }),
    clear: version => request(base, isRequirementDraft, { version }, { method: 'DELETE' }),
    query: sku => request('/api/overseas/v1/requirement-source', isSourceResult, undefined, { params: { sku }, timeoutMs: 45000 })
  }
}
