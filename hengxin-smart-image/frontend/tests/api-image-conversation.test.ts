import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createConversationClient, eventDecoder, conversationValid } from '../src/api/api-image-conversation'
import { identity, StaleIdentityError } from '../src/api/hengxin/identity'
import { createConversationCommand, type ConversationAction } from '../src/views/hengxin/api-image-edits/conversation-command'
import { acceptConversationSnapshot, appendConversationEvent } from '../src/views/hengxin/api-image-edits/conversation-feed'
import type { EditConversation } from '../src/types/api-image-conversation'
const empty = { id: null, itemId: 'item', currentVersion: 2, lastEventId: 0, turns: [] }
test('交错GET与实时消息不回退，重连重复事件与快照重放只显示一次', () => {
  const initial: EditConversation = { ...empty, turns: [{ id: 'turn', status: 'running', text: '', prompt: '', baseVersion: 2, baseTurnId: null, baseFileId: 'base', basePicture: null, candidate: null, annotation: null, annotationFileId: null, candidateFileId: null, messages: [], error: null, createdAt: '', adoptedVersion: null }] }
  const event = { id: 1, turnId: 'turn', type: 'message' as const, text: '新回复' }
  const streamed = appendConversationEvent(initial, event, 0)!
  const late = acceptConversationSnapshot(streamed, initial, 1)!
  assert.deepEqual(late.turns[0].messages, ['新回复'])
  assert.equal(appendConversationEvent(late, event, 1), late)
  const fresh = { ...streamed, lastEventId: 2, turns: [{ ...streamed.turns[0], status: 'waiting_user' as const }] }
  assert.equal(acceptConversationSnapshot(late, fresh, 2), fresh)
  assert.equal(appendConversationEvent(fresh, event, 2), fresh)
})
test('会话请求完整保留底图/意见/幂等键，采用携带预期版本', async () => {
  const calls: { url: string; init?: RequestInit }[] = []
  const api = createConversationClient('/api/v1', async (url, init) => { calls.push({ url: String(url), init }); return new Response(JSON.stringify(empty), { headers: { 'Content-Type': 'application/json' } }) })
  assert.deepEqual(await api.get('t/a', 'item'), empty)
  const input = { baseTurnId: 'candidate-id', text: '标注 1：缩小物体\n保持其他不变', prompt: '完整固定规则', annotationFileId: 'mark' }
  await api.submit('t/a', 'item', input, 'stable-key')
  assert.equal(calls[1].url, '/api/v1/api-image-edits/tasks/t%2Fa/items/item/conversation/turns')
  assert.deepEqual(JSON.parse(String(calls[1].init?.body)), input)
  assert.equal(new Headers(calls[1].init?.headers).get('Idempotency-Key'), 'stable-key')
  await api.adopt('t/a', 'item', 'candidate-id', 2, 'adopt-key')
  assert.deepEqual(JSON.parse(String(calls[2].init?.body)), { expectedVersion: 2 })
  assert.equal(conversationValid({ ...empty, lastEventId: -1 }), false)
})
test('SSE支持跨chunk、多行JSON、CRLF与心跳，游标字段校验', () => {
  const received: unknown[] = [], parse = eventDecoder(event => received.push(event))
  parse(': heartbeat\r\n\r\nid: 1\r\ndata: {"id":1,')
  parse('\r\ndata: "turnId":"turn","type":"message","text":"公开回复"}\r\n\r')
  assert.equal(received.length, 0)
  parse('\n')
  assert.deepEqual(received, [{ id: 1, turnId: 'turn', type: 'message', text: '公开回复' }])
  assert.throws(() => parse('data: {"id":-1,"turnId":"turn","type":"message"}\n\n'))
})
test('SSE补发带after/Last-Event-ID并在身份改变时拒绝旧流', async () => {
  let streamController: ReadableStreamDefaultController<Uint8Array> | undefined
  let started!: () => void
  const ready = new Promise<void>(resolve => { started = resolve })
  const messages: number[] = []
  const api = createConversationClient('/api/v1', async (url, init) => {
    assert.match(String(url), /events\?after=12$/)
    assert.equal(new Headers(init?.headers).get('Last-Event-ID'), '12')
    const stream = new ReadableStream<Uint8Array>({ start(controller) { streamController = controller } })
    started(); return new Response(stream, { headers: { 'Content-Type': 'text/event-stream' } })
  })
  const request = api.events('task', 'item', 12, new AbortController().signal, event => messages.push(event.id))
  await ready; await new Promise(resolve => setTimeout(resolve, 0))
  identity.advance('changed')
  streamController!.enqueue(new TextEncoder().encode('data: {"id":13,"turnId":"turn","type":"message","text":"旧身份"}\n\n'))
  await assert.rejects(request, StaleIdentityError)
  assert.deepEqual(messages, [])
})
test('响应丢失后续接原图片请求，冻结意见与key；采用操作不能替换未确认提交', async () => {
  const command = createConversationCommand(undefined, () => 'idempotency')
  const action: ConversationAction = { kind: 'submit', input: { baseVersion: 2, text: '初始意见', prompt: '原提示词', annotationFileId: 'mark' } }
  const sent: { action: ConversationAction; key: string }[] = []
  let fail = true
  const send = async (frozen: ConversationAction, key: string) => { sent.push({ action: JSON.parse(JSON.stringify(frozen)) as ConversationAction, key }); if (fail) throw new Error('网络断开'); return empty }
  assert.equal(await command.send(action, send), undefined)
  action.input.text = '之后输入'
  fail = false
  assert.deepEqual(await command.send({ kind: 'adopt', turnId: 'other', expectedVersion: 3 }, send), empty)
  assert.deepEqual(sent[1], sent[0])
  assert.equal(command.state.pending, null)
})
