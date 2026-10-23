import { MAX_UPLOAD_BYTES } from './upload-limits'
import { isSkill, type Skill } from './management'
import { createIdentityRequest, IdentityError, record } from '../identity/request'
export interface Asset { id: string; name: string; contentType: string; sizeBytes: number; url: string; source: 'task' | 'upload' }
export interface UploadedAsset extends Asset { materialState?: 'added' | 'existing' | 'restored' }
export interface StudioPicture { id: string; name: string; url: string; width: number; height: number; turnId: string; sku: string | null; archived: boolean; sourcePath?: string | null }
export interface StudioTurn { id: string; text: string; skillName: string | null; status: string; reply: string | null; error: string | null; jobId: string; jobVersion: number; attachments: Asset[]; pictures: StudioPicture[]; referencePictures: StudioPicture[]; createdAt: string; conversationId?: string; deliveryError?: string | null }
export interface StudioConversation { id: string; name: string; version: number; createdAt: string; updatedAt: string; activeTurnId: string | null; status: string; turnCount: number; deletionStatus?: 'deleting' | 'delete_failed' | null; deletionError?: string | null }
export interface Studio { conversations?: StudioConversation[]; activeConversationCount?: number; maxConversations?: number; taskId: string; taskVersion: number; archiveId: string | null; reopened: boolean; completed: boolean; turns: StudioTurn[]; materials: Asset[]; skills: Skill[]; activeTurnId: string | null; conversationId?: string | null }
export interface StudioEvent { id: number; turnId: string; kind: string; text: string; createdAt: string }
export interface StudioTranscript { id: number; turnId: string; itemId: string; kind: 'message' | 'reasoning' | 'tool' | 'notice'; text: string; state: 'running' | 'completed' | 'failed'; createdAt: string }
export interface TranscriptPage { items: StudioTranscript[]; cursor: number; hasMore: boolean }
export interface ImageEdit { pictureId: string; annotationId: string | null; text: string }
export interface TurnInput { conversationId?: string; text: string; skillId: string | null; attachmentIds: string[]; referencePictureIds: string[]; imageEdits?: ImageEdit[] }
const root = '/api/overseas/v1', base = (id: string) => `${root}/tasks/${encodeURIComponent(id)}/studio`
const string = (v: unknown): v is string => typeof v === 'string'
const integer = (v: unknown) => Number.isInteger(v) && Number(v) >= 0
export function isAsset(v: unknown, taskId: string): v is Asset {
  if (!record(v) || !['id', 'name', 'contentType', 'url'].every(k => string(v[k])) || !integer(v.sizeBytes)) return false
  const id = String(v.id), source = v.source
  return source === 'task' ? id.startsWith('task:') && v.url === `${root}/materials/${encodeURIComponent(id.slice(5))}/content`
    : source === 'upload' && id.startsWith('upload:') && v.url === `${base(taskId)}/files/${encodeURIComponent(id.slice(7))}/content`
}
export function isConversation(v: unknown): v is StudioConversation {
  return record(v) && ['id', 'name', 'createdAt', 'updatedAt'].every(k => string(v[k])) && integer(v.version) && Number(v.version) > 0
    && (v.activeTurnId === null || string(v.activeTurnId)) && integer(v.turnCount)
    && ['queued', 'running', 'succeeded', 'failed', 'cancelled', 'empty'].includes(String(v.status))
    && (v.deletionStatus == null || ['deleting', 'delete_failed'].includes(String(v.deletionStatus))) && (v.deletionError == null || string(v.deletionError))
}
export function isStudio(v: unknown, taskId: string): v is Studio {
  return record(v) && (v.conversations === undefined || (Array.isArray(v.conversations) && v.conversations.every(isConversation) && new Set(v.conversations.map(c => c.id)).size === v.conversations.length))
    && (v.activeConversationCount === undefined || integer(v.activeConversationCount)) && (v.maxConversations === undefined || v.maxConversations === 10) && v.taskId === taskId && typeof v.completed === 'boolean' && (v.activeTurnId === null || string(v.activeTurnId))
    && Number.isInteger(v.taskVersion) && Number(v.taskVersion) > 0 && typeof v.reopened === 'boolean'
    && (v.archiveId === null || (string(v.archiveId) && !!v.archiveId.trim()))
    && (v.conversationId === undefined || v.conversationId === null || string(v.conversationId))
    && Array.isArray(v.materials) && v.materials.every(a => isAsset(a, taskId))
    && Array.isArray(v.skills) && v.skills.every(isSkill)
    && Array.isArray(v.turns) && v.turns.every(t => record(t) && ['id','text','status','jobId','createdAt'].every(k => string(t[k])) && (t.reply === null || string(t.reply))
      && (t.skillName === null || string(t.skillName)) && (t.error === null || string(t.error)) && integer(t.jobVersion)
      && (t.conversationId === undefined || string(t.conversationId)) && (t.deliveryError === undefined || t.deliveryError === null || string(t.deliveryError))
      && Array.isArray(t.attachments) && t.attachments.every(a => isAsset(a, taskId))
      && Array.isArray(t.pictures) && t.pictures.every(p => isStudioPicture(p, taskId) && p.turnId === t.id)
      && Array.isArray(t.referencePictures) && t.referencePictures.every(p => isStudioPicture(p, taskId)))
}
function isStudioPicture(p: unknown, taskId: string): p is StudioPicture {
  return record(p) && string(p.id) && string(p.name) && string(p.turnId)
    && p.url === `${base(taskId)}/pictures/${encodeURIComponent(p.id)}/content` && integer(p.width) && integer(p.height)
    && (p.sku === null || string(p.sku)) && typeof p.archived === 'boolean'
    && (p.sourcePath === undefined || p.sourcePath === null || string(p.sourcePath))
}
export function isTranscriptPage(v: unknown): v is TranscriptPage {
  return record(v) && integer(v.cursor) && typeof v.hasMore === 'boolean' && Array.isArray(v.items)
    && v.items.every(e => record(e) && integer(e.id) && ['turnId','itemId','text','createdAt'].every(k => string(e[k]))
      && ['message','reasoning','tool','notice'].includes(String(e.kind)) && ['running','completed','failed'].includes(String(e.state)))
}
export function validateStudioFile(file: Pick<File, 'name' | 'size'>) {
  if (!file.size || file.size > MAX_UPLOAD_BYTES) throw Error('请选择非空文件，单个最大 500 MB')
}
export function createStudioApi(fetcher: typeof fetch = fetch) {
  const request = createIdentityRequest((url, options) => fetcher(url, { ...options, cache: 'no-store' }))
  const read = (signal?: AbortSignal) => signal ? createIdentityRequest((url, options) => fetcher(url, { ...options, cache: 'no-store', signal: options?.signal ? AbortSignal.any([signal, options.signal]) : signal })) : request
  const guard = (id: string) => (v: unknown): v is Studio => isStudio(v, id)
  return {
    get: (id: string, signal?: AbortSignal, conversationId?: string) => read(signal)(base(id), guard(id), undefined, { params: conversationId ? { conversationId } : {} }),
    removeMaterial: (id: string, assetId: string, conversationId?: string) => request(`${base(id)}/materials/${encodeURIComponent(assetId)}`, guard(id), {}, { method: 'DELETE', params: conversationId ? { conversationId } : {} }),
    transcript: (id: string, after: number, signal?: AbortSignal, conversationId?: string) => read(signal)(`${base(id)}/transcript`, isTranscriptPage, undefined, { params: { after, ...(conversationId ? { conversationId } : {}) } }),
    newConversation: (id: string, key: string, name?: string) => request(`${base(id)}/conversations`, guard(id), name ? { name } : {}, { idempotencyKey: key }),
    renameConversation: (id: string, conversationId: string, name: string, version: number, key: string) => request(`${base(id)}/conversations/${encodeURIComponent(conversationId)}`, guard(id), { name, version }, { method: 'PATCH', idempotencyKey: key }),
    deleteConversation: (id: string, conversationId: string, version: number, key: string) => request(`${base(id)}/conversations/${encodeURIComponent(conversationId)}`, guard(id), { version }, { method: 'DELETE', idempotencyKey: key }),
    send: (id: string, body: TurnInput, key: string, conversationId?: string) => request(`${base(id)}/turns`, guard(id), body, { idempotencyKey: key, params: conversationId ? { conversationId } : {} }),
    cancel: (id: string, turn: StudioTurn) => request(`${base(id)}/turns/${encodeURIComponent(turn.id)}/cancel`, guard(id), { version: turn.jobVersion }),
    archive: (id: string, pictureIds: string[], sku: string, key: string, conversationId?: string) => request(`${base(id)}/archive`, guard(id), { pictureIds, sku, ...(conversationId ? { conversationId } : {}) }, { idempotencyKey: key }),
    complete: (id: string, version: number, key: string) => request(`${base(id)}/complete`, guard(id), { version }, { idempotencyKey: key }),
    reopen: (id: string, version: number, key: string) => request(`${base(id)}/reopen`, guard(id), { version }, { idempotencyKey: key }),
    events: (id: string, after: number) => request(`${base(id)}/events`, (v): v is { items: StudioEvent[]; cursor: number } => record(v) && integer(v.cursor) && Array.isArray(v.items) && v.items.every(e => record(e) && integer(e.id) && ['turnId','kind','text','createdAt'].every(k => string(e[k]))), undefined, { params: { after } }),
    async upload(id: string, file: File, signal: AbortSignal, conversationId?: string) {
      validateStudioFile(file); const body = new FormData(); body.append('file', file)
      const response = await fetcher(`${base(id)}/files${conversationId ? `?conversationId=${encodeURIComponent(conversationId)}` : ''}`, { method: 'POST', body, credentials: 'include', headers: { 'X-HX-Request': '1' }, signal })
      if (!response.ok) throw new IdentityError(response.status, response.status === 413 ? '单个附件不能超过 500 MB' : '文件上传失败，请重试')
      const value: unknown = await response.json()
      if (!isAsset(value, id) || (record(value) && value.materialState !== undefined && !['added', 'existing', 'restored'].includes(String(value.materialState)))) throw Error('文件响应格式错误')
      return value as UploadedAsset
    },

  }
}
export type StudioApi = ReturnType<typeof createStudioApi>
