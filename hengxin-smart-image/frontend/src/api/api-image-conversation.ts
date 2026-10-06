import { ApiError, createRequest } from './hengxin/http'
import { checkIdentityResponse, identity } from './hengxin/identity'
import { picture } from './api-image-edits-validate'
import type { EditConversation, EditEvent, EditTurn, EditTurnInput } from '../types/api-image-conversation'
const object = (v: unknown): v is Record<string, unknown> => !!v && typeof v === 'object' && !Array.isArray(v)
const text = (v: unknown): v is string => typeof v === 'string'
const count = (v: unknown): v is number => typeof v === 'number' && Number.isSafeInteger(v) && v >= 0
const nullableText = (v: unknown) => v === null || text(v)
const nullableNumber = (v: unknown) => v === null || count(v)
const statuses = ['queued', 'running', 'waiting_user', 'candidate', 'adopted', 'cancelled', 'failed', 'uncertain']
const turn = (v: unknown): v is EditTurn => object(v) && text(v.id) && text(v.status) && statuses.includes(v.status)
  && text(v.text) && text(v.prompt) && nullableNumber(v.baseVersion) && nullableText(v.baseTurnId) && text(v.baseFileId)
  && nullableText(v.annotationFileId) && nullableText(v.candidateFileId) && Array.isArray(v.messages) && v.messages.every(text)
  && nullableText(v.error) && text(v.createdAt) && nullableNumber(v.adoptedVersion)
  && [v.basePicture, v.candidate, v.annotation].every(p => p === null || picture(p))
export const conversationValid = (v: unknown): v is EditConversation => object(v) && nullableText(v.id) && text(v.itemId)
  && nullableNumber(v.currentVersion) && count(v.lastEventId) && Array.isArray(v.turns) && v.turns.every(turn)
export const editEventValid = (v: unknown): v is EditEvent => object(v) && count(v.id) && v.id > 0 && text(v.turnId)
  && (v.type === 'state' || v.type === 'message') && (v.text === undefined || text(v.text))
  && (v.status === undefined || (text(v.status) && statuses.includes(v.status)))

/** Incremental SSE parser: heartbeat comments never advance the persisted event cursor. */
export function eventDecoder(receive: (event: EditEvent) => void) {
  let buffer = ''
  return (chunk: string) => {
    buffer += chunk
    let match: RegExpExecArray | null
    while ((match = /\r?\n\r?\n/.exec(buffer))) {
      const frame = buffer.slice(0, match.index); buffer = buffer.slice(match.index + match[0].length)
      const data = frame.split(/\r?\n/).filter(line => line.startsWith('data:')).map(line => line.slice(5).replace(/^ /, '')).join('\n')
      if (!data) continue
      const value: unknown = JSON.parse(data)
      if (!editEventValid(value)) throw new ApiError('INVALID_RESPONSE', '实时消息格式错误')
      receive(value)
    }
  }
}
export function createConversationClient(baseUrl: string, fetcher: typeof fetch = fetch) {
  const root = `${baseUrl.replace(/\/$/, '')}/api-image-edits`, request = createRequest(root, fetcher)
  const path = (task: string, item: string) => `/tasks/${encodeURIComponent(task)}/items/${encodeURIComponent(item)}/conversation`
  return {
    get: (task: string, item: string) => request(path(task, item), conversationValid),
    submit: (task: string, item: string, input: EditTurnInput, key: string) => request(path(task, item) + '/turns', conversationValid, 'POST', input, 10000, { 'Idempotency-Key': key }),
    stop: (task: string, item: string, turnId: string) => request(`${path(task, item)}/turns/${encodeURIComponent(turnId)}/stop`, conversationValid, 'POST'),
    adopt: (task: string, item: string, turnId: string, expectedVersion: number, key: string) => request(`${path(task, item)}/turns/${encodeURIComponent(turnId)}/adopt`, conversationValid, 'POST', { expectedVersion }, 10000, { 'Idempotency-Key': key }),
    async events(task: string, item: string, after: number, signal: AbortSignal, receive: (event: EditEvent) => void) {
      const reading = identity.read()
      try {
        const response = await fetcher(`${root}${path(task, item)}/events?after=${after}`, { credentials: 'include', headers: { Accept: 'text/event-stream', 'Last-Event-ID': String(after) }, signal: AbortSignal.any([reading.signal, signal]) })
        reading.assert(); await checkIdentityResponse(response.status, reading.epoch); reading.assert()
        if (!response.ok) throw new ApiError('STREAM_FAILED', `实时连接失败（${response.status}）`, response.status)
        if (!response.headers.get('content-type')?.includes('text/event-stream') || !response.body) throw new ApiError('INVALID_RESPONSE', '实时连接返回格式错误')
        const reader = response.body.getReader(), decoder = new TextDecoder()
        const parse = eventDecoder(event => { reading.assert(); if (!signal.aborted) receive(event) })
        try { while (!signal.aborted) { const value = await reader.read(); reading.assert(); if (value.done) break; parse(decoder.decode(value.value, { stream: true })) } }
        finally { await reader.cancel().catch(() => {}); reader.releaseLock() }
      } finally { reading.release() }
    }
  }
}
export const imageConversations = createConversationClient(import.meta.env?.VITE_API_URL || '/api/v1')
