import { createIdentityRequest, record } from '@/api/identity/request'
import { isImageEdit, type ImageEdit } from '@/api/shared/studio'
import type { WorkspaceKey } from './domestic-studio-skills'

export interface ArchiveFile { id: string; kind: 'upload' | 'picture' | 'output'; name: string; contentType: string; sizeBytes: number; width: number | null; height: number | null; url: string }
export interface ArchiveSummary { id: string; productName: string; workspace: 'camera' | 'case'; conversationName: string; createdAt: string; pictureCount: number; cover: ArchiveFile | null; deletionStatus: 'deleting' | 'delete_failed' | null; deletionError: string | null }
export interface ArchiveTranscript { itemId?: string | null; kind: 'message' | 'reasoning' | 'tool' | 'notice'; text: string; state: 'running' | 'completed' | 'failed'; createdAt: string | null }
export interface ArchiveTurn { id: string; text: string; actorName: string | null; createdAt: string; reply: string | null; replyAt: string | null; status?: 'succeeded' | 'partial' | 'failed' | 'cancelled' | null; error?: string | null; transcript?: ArchiveTranscript[] | null; attachments: ArchiveFile[]; referencePictures: ArchiveFile[]; pictures: ArchiveFile[]; outputs: ArchiveFile[]; imageEdits?: ImageEdit[] }
export interface ArchiveDetail extends ArchiveSummary { turns: ArchiveTurn[] }
export interface ArchivePage { items: ArchiveSummary[]; total: number; page: number; pageSize: number }
const root = '/api/v1/domestic-studio'
const identifier = (v: unknown): v is string => typeof v === 'string' && /^[a-f0-9-]{36}$/i.test(v)
const integer = (v: unknown) => Number.isSafeInteger(v) && Number(v) >= 0
const nullableString = (v: unknown) => v === null || typeof v === 'string'
function file(v: unknown, archive: string, kind?: string): v is ArchiveFile {
  return record(v) && identifier(v.id) && ['upload', 'picture', 'output'].includes(String(v.kind))
    && (!kind || v.kind === kind) && typeof v.name === 'string' && typeof v.contentType === 'string'
    && integer(v.sizeBytes) && (v.width === null || integer(v.width)) && (v.height === null || integer(v.height))
    && v.url === `${root}/archives/${archive}/files/${v.id}/content`
}
function summary(v: unknown): v is ArchiveSummary {
  return record(v) && identifier(v.id) && typeof v.productName === 'string' && ['camera', 'case'].includes(String(v.workspace))
    && typeof v.conversationName === 'string' && typeof v.createdAt === 'string' && integer(v.pictureCount)
    && (v.cover === null || file(v.cover, v.id, 'picture'))
    && (v.deletionStatus === null || ['deleting', 'delete_failed'].includes(String(v.deletionStatus))) && nullableString(v.deletionError)
}
function validEdits(value: unknown, attachments: unknown, pictures: unknown): boolean {
  if (value === undefined) return true
  if (!Array.isArray(value) || !Array.isArray(attachments) || !Array.isArray(pictures)) return false
  return value.every((edit: unknown) => isImageEdit(edit)
    && pictures.some((picture: ArchiveFile) => picture.id === edit.pictureId)
    && (edit.annotationId === null || attachments.some((item: ArchiveFile) => `upload:${item.id}` === edit.annotationId))
    && (edit.references || []).every(reference => attachments.some((item: ArchiveFile) => `upload:${item.id}` === reference.attachmentId)))
}
function validTranscript(value: unknown): boolean {
  return value == null || (Array.isArray(value) && value.every(entry => record(entry)
    && (entry.itemId == null || typeof entry.itemId === 'string')
    && ['message', 'reasoning', 'tool', 'notice'].includes(String(entry.kind))
    && ['running', 'completed', 'failed'].includes(String(entry.state))
    && typeof entry.text === 'string' && (entry.createdAt == null || typeof entry.createdAt === 'string')))
}
function detail(v: unknown): v is ArchiveDetail {
  if (!summary(v) || !record(v) || !Array.isArray(v.turns)) return false
  return v.turns.every(turn => record(turn) && identifier(turn.id) && typeof turn.text === 'string'
    && nullableString(turn.actorName) && typeof turn.createdAt === 'string' && nullableString(turn.reply) && nullableString(turn.replyAt)
    && (turn.status == null || ['succeeded', 'partial', 'failed', 'cancelled'].includes(String(turn.status)))
    && (turn.error === undefined || nullableString(turn.error)) && validTranscript(turn.transcript)
    && (['attachments', 'referencePictures', 'pictures', 'outputs'] as const).every(field => Array.isArray(turn[field])
      && turn[field].every((item: unknown) => file(item, v.id, field === 'attachments' ? 'upload' : field === 'outputs' ? 'output' : 'picture')))
    && validEdits(turn.imageEdits, turn.attachments, turn.referencePictures))
}
const page = (v: unknown): v is ArchivePage => record(v) && integer(v.total) && integer(v.page) && integer(v.pageSize)
  && Array.isArray(v.items) && v.items.every(summary)
const status = (v: unknown): v is { archiveId: string; status: string } => record(v) && identifier(v.archiveId)
  && ['deleting', 'delete_failed', 'deleted'].includes(String(v.status))

export function createDomesticArchivesApi(fetcher: typeof fetch = fetch) {
  const request = createIdentityRequest(fetcher)
  return {
    list: (search = '', workspace = '', pageNumber = 1) => request(`${root}/archives`, page, undefined, { params: { search, workspace, page: pageNumber, pageSize: 20 } }),
    detail: (id: string) => { if (!identifier(id)) throw Error('归档编号无效'); return request(`${root}/archives/${id}`, detail) },
    create: (workspace: WorkspaceKey, conversationId: string, productName: string, key: string) => {
      if (!['camera', 'case'].includes(workspace) || !identifier(conversationId)) throw Error('归档来源无效')
      return request(`${root}/workspaces/${workspace}/conversations/${conversationId}/archive`, detail, { productName }, { idempotencyKey: key, timeoutMs: 300000 })
    },
    remove: (id: string) => { if (!identifier(id)) throw Error('归档编号无效'); return request(`${root}/archives/${id}`, status, {}, { method: 'DELETE' }) },
    download(id: string) {
      if (!identifier(id)) throw Error('归档编号无效')
      const anchor = document.createElement('a'); anchor.href = `${root}/archives/${id}/download`; anchor.download = `archive-${id}.zip`
      document.body.appendChild(anchor); try { anchor.click() } finally { anchor.remove() }
    }
  }
}
