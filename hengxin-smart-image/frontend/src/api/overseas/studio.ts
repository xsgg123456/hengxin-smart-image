import { MAX_UPLOAD_BYTES } from './upload-limits'
import { isSkill, type Skill } from './management'
import { createIdentityRequest, IdentityError, record } from '../identity/request'
export interface Asset { id: string; name: string; contentType: string; sizeBytes: number; url: string; source: 'task' | 'upload' }
export interface StudioPicture { id: string; name: string; url: string; width: number; height: number; turnId: string; sku: string | null; archived: boolean; sourcePath?: string | null }
export interface StudioTurn { id: string; text: string; skillName: string | null; status: string; reply: string | null; error: string | null; jobId: string; jobVersion: number; attachments: Asset[]; pictures: StudioPicture[]; referencePictures: StudioPicture[]; createdAt: string; conversationId?: string; deliveryError?: string | null }
export interface Studio { taskId: string; completed: boolean; turns: StudioTurn[]; materials: Asset[]; skills: Skill[]; activeTurnId: string | null; conversationId?: string | null }
export interface StudioEvent { id: number; turnId: string; kind: string; text: string; createdAt: string }
export interface StudioTranscript { id: number; turnId: string; itemId: string; kind: 'message' | 'reasoning' | 'tool' | 'notice'; text: string; state: 'running' | 'completed' | 'failed'; createdAt: string }
export interface TranscriptPage { items: StudioTranscript[]; cursor: number; hasMore: boolean }
export interface TurnInput { text: string; skillId: string | null; attachmentIds: string[]; referencePictureIds: string[] }
const root = '/api/overseas/v1', base = (id: string) => `${root}/tasks/${encodeURIComponent(id)}/studio`
const string = (v: unknown): v is string => typeof v === 'string'
const integer = (v: unknown) => Number.isInteger(v) && Number(v) >= 0
export function isAsset(v: unknown, taskId: string): v is Asset {
  if (!record(v) || !['id', 'name', 'contentType', 'url'].every(k => string(v[k])) || !integer(v.sizeBytes)) return false
  const id = String(v.id), source = v.source
  return source === 'task' ? id.startsWith('task:') && v.url === `${root}/materials/${encodeURIComponent(id.slice(5))}/content`
    : source === 'upload' && id.startsWith('upload:') && v.url === `${base(taskId)}/files/${encodeURIComponent(id.slice(7))}/content`
}
export function isStudio(v: unknown, taskId: string): v is Studio {
  return record(v) && v.taskId === taskId && typeof v.completed === 'boolean' && (v.activeTurnId === null || string(v.activeTurnId))
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
  const extension = file.name.split('.').pop()?.toLowerCase() || ''
  if (['doc', 'ppt'].includes(extension)) throw Error('请先将 DOC/PPT 转换为 DOCX/PPTX 或 PDF')
  if (!['jpg','jpeg','png','webp','pdf','docx','pptx','xls','xlsx','csv','txt'].includes(extension)) throw Error('不支持此文件格式')
}
export function createStudioApi(fetcher: typeof fetch = fetch) {
  const request = createIdentityRequest((url, options) => fetcher(url, { ...options, cache: 'no-store' }))
  const read = (signal?: AbortSignal) => signal ? createIdentityRequest((url, options) => fetcher(url, { ...options, cache: 'no-store', signal: options?.signal ? AbortSignal.any([signal, options.signal]) : signal })) : request
  const guard = (id: string) => (v: unknown): v is Studio => isStudio(v, id)
  return {
    get: (id: string, signal?: AbortSignal) => read(signal)(base(id), guard(id)),
    transcript: (id: string, after: number, signal?: AbortSignal) => read(signal)(`${base(id)}/transcript`, isTranscriptPage, undefined, { params: { after } }),
    newConversation: (id: string, key: string) => request(`${base(id)}/conversations`, guard(id), {}, { idempotencyKey: key }),
    send: (id: string, body: TurnInput, key: string) => request(`${base(id)}/turns`, guard(id), body, { idempotencyKey: key }),
    cancel: (id: string, turn: StudioTurn) => request(`${base(id)}/turns/${encodeURIComponent(turn.id)}/cancel`, guard(id), { version: turn.jobVersion }),
    archive: (id: string, pictureIds: string[], sku: string, key: string) => request(`${base(id)}/archive`, guard(id), { pictureIds, sku }, { idempotencyKey: key }),
    complete: (id: string, key: string) => request(`${base(id)}/complete`, guard(id), {}, { idempotencyKey: key }),
    events: (id: string, after: number) => request(`${base(id)}/events`, (v): v is { items: StudioEvent[]; cursor: number } => record(v) && integer(v.cursor) && Array.isArray(v.items) && v.items.every(e => record(e) && integer(e.id) && ['turnId','kind','text','createdAt'].every(k => string(e[k]))), undefined, { params: { after } }),
    async upload(id: string, file: File, signal: AbortSignal) {
      validateStudioFile(file); const body = new FormData(); body.append('file', file)
      const response = await fetcher(`${base(id)}/files`, { method: 'POST', body, credentials: 'include', headers: { 'X-HX-Request': '1' }, signal })
      if (!response.ok) throw new IdentityError(response.status, response.status === 413 ? '单个附件不能超过 500 MB' : '文件上传失败，请重试')
      const value: unknown = await response.json(); if (!isAsset(value, id)) throw Error('文件响应格式错误'); return value
    },
    async content(url: string, id: string, signal: AbortSignal) {
      const suffix = url.startsWith(`${base(id)}/`) ? url.slice(base(id).length) : ''
      if (!/^\/(files|pictures)\/[a-zA-Z0-9-]+\/content$/.test(suffix) && !/^\/api\/overseas\/v1\/materials\/[a-zA-Z0-9-]+\/content$/.test(url)) throw Error('文件地址无效')
      const response = await fetcher(url, { credentials: 'include', cache: 'no-store', headers: { 'X-HX-Request': '1' }, signal })
      if (!response.ok) throw new IdentityError(response.status, '文件读取失败'); return response.blob()
    }
  }
}
export type StudioApi = ReturnType<typeof createStudioApi>
