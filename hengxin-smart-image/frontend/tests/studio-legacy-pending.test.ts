import test from 'node:test'
import assert from 'node:assert/strict'
import { createStudioApi } from '../src/api/overseas/studio'
import { IdentityError } from '../src/api/identity/request'
import { composerDraftKey } from '../src/views/overseas/studio/studio-composer-draft'
import { pendingKey } from '../src/views/overseas/studio/studio-pending'
import { fixture, flush, local, session } from './studio-sessions-fixture'

const globalKey = pendingKey('designer', 't')
const body = { text: 'A原待确认请求', skillId: null, attachmentIds: [], referencePictureIds: [] }
const original = { key: 'old-unknown-key', kind: 'send', body, draftConversationId: 'a' }
function seedDraft(id: string, text: string) {
  local.set(composerDraftKey('designer', 't', id), JSON.stringify({ version: 1, text, skill: '', attachments: [], references: [], revisions: [] }))
}

for (const accepted of [true, false]) test(`旧发送${accepted ? '已' : '未'}接受时默认B仍恢复原A并保持body/key，B草稿不变`, async () => {
  const f = fixture(); f.api.get = async (_t, _s, id) => f.snapshot(id || 'b')
  session.set(globalKey, JSON.stringify(original)); seedDraft('a', body.text); seedDraft('b', 'B自己的未发送草稿')
  const before = local.get(composerDraftKey('designer', 't', 'b'))
  let requests = 0, jobs = accepted ? 1 : 0
  f.api.send = async (_t, sent, key, hint) => {
    requests++; assert.deepEqual(sent, body); assert.equal(key, original.key); assert.equal(hint, 'a')
    if (!jobs) jobs++
    return f.snapshot('a')
  }
  const v = f.mount(); await flush()
  try {
    assert.equal(v.state.activeId.value, 'b'); assert.equal(v.state.pending.value, undefined)
    await v.state.retry(); assert.equal(requests, 0); assert.equal(v.state.text.value, 'B自己的未发送草稿')
    await v.state.selectSession('a'); assert.equal(v.state.pending.value?.key, original.key)
    await v.state.retry(); assert.equal(requests, 1); assert.equal(jobs, 1); assert.equal(v.state.text.value, '')
    await v.state.selectSession('b'); assert.equal(v.state.text.value, 'B自己的未发送草稿')
    assert.equal(local.get(composerDraftKey('designer', 't', 'b')), before)
  } finally { v.close() }
})

test('默认原会话也能恢复旧pending，4xx核实失败保留键/正文且可刷新重试', async () => {
  const f = fixture(); session.set(globalKey, JSON.stringify(original)); seedDraft('a', body.text)
  f.api.send = async () => { throw new IdentityError(409, '原请求会话不一致') }
  let v = f.mount(); await flush()
  assert.equal(v.state.pending.value?.key, original.key); await v.state.retry(); assert.equal(v.state.text.value, body.text)
  assert.ok(session.has(pendingKey('designer', 't', 'a'))); v.close()
  v = f.mount(); await flush()
  try { assert.equal(v.state.pending.value?.key, original.key); assert.equal(v.state.text.value, body.text) } finally { v.close() }
})

for (const owner of [undefined, 'deleted']) test(`旧请求原ID${owner ? '删除' : '缺失'}保留原记录和所有草稿，禁止默认重放`, async () => {
  const f = fixture(); f.api.get = async (_t, _s, id) => f.snapshot(id || 'b')
  const saved = JSON.stringify({ ...original, draftConversationId: owner })
  session.set(globalKey, saved); seedDraft('b', 'B草稿'); seedDraft('deleted', '已删除会话草稿')
  const before = new Map(local)
  const v = f.mount(); await flush()
  try {
    await v.state.retry(); assert.equal(f.calls.filter(c => c.kind === 'send').length, 0)
    assert.equal(session.get(globalKey), saved); assert.match(v.state.preferenceNotice.value, /原会话.*无法确认/)
    for (const [key, value] of before) assert.equal(local.get(key), value)
    assert.equal(v.state.text.value, 'B草稿')
  } finally { v.close() }
})

test('旧archive无原ID保留并提示，不猜测图片归属或改变请求体重发', async () => {
  const f = fixture(), saved = JSON.stringify({ kind: 'archive', key: 'old-archive', body: { pictureIds: ['p'], sku: 'A' } })
  session.set(globalKey, saved); let writes = 0; f.api.archive = async () => { writes++; return f.snapshot('b') }
  const v = f.mount(); await flush()
  try { await v.state.retry(); assert.equal(writes, 0); assert.equal(session.get(globalKey), saved); assert.match(v.state.preferenceNotice.value, /原会话/) } finally { v.close() }
})

test('有原ID的旧archive保持原body无会话字段，旧conversation核实不清A或B草稿', async () => {
  for (const kind of ['archive', 'conversation'] as const) {
    const f = fixture(); f.api.get = async (_t, _s, id) => f.snapshot(id || 'b')
    session.set(globalKey, JSON.stringify({ key: `old-${kind}`, kind, draftConversationId: 'a', ...(kind === 'archive' ? { body: { pictureIds: ['p'], sku: 'A' } } : {}) }))
    seedDraft('a', 'A草稿'); seedDraft('b', 'B草稿'); let writes = 0
    f.api.archive = async (_t, pictures, sku, key, id) => { writes++; assert.equal(id, undefined); assert.deepEqual(pictures, ['p']); assert.equal(sku, 'A'); assert.equal(key, 'old-archive'); return f.snapshot('a') }
    f.api.newConversation = async (_t, key) => { writes++; assert.equal(key, 'old-conversation'); return f.snapshot('b') }
    const v = f.mount(); await flush()
    try {
      await v.state.selectSession('a'); await v.state.retry(); assert.equal(writes, 1); assert.equal(v.state.text.value, 'A草稿')
      await v.state.selectSession('b'); assert.equal(v.state.text.value, 'B草稿')
      assert.equal(JSON.parse(local.get(composerDraftKey('designer', 't', 'a'))!).text, 'A草稿')
    } finally { v.close() }
  }
})

test('旧pending与原会话新pending冲突时不覆盖任一原始记录', async () => {
  const f = fixture(), scoped = pendingKey('designer', 't', 'a')
  session.set(globalKey, JSON.stringify(original)); session.set(scoped, JSON.stringify({ ...original, key: 'newer-key' }))
  const v = f.mount(); await flush()
  try { assert.equal(JSON.parse(session.get(globalKey)!).key, original.key); assert.equal(v.state.pending.value?.key, 'newer-key'); assert.match(v.state.preferenceNotice.value, /另一条/) } finally { v.close() }
})

test('legacy发送API路由hint仅放query，序列化body与原键保持不变', async () => {
  const f = fixture(); let received = false
  const api = createStudioApi(async (url, options) => {
    received = true; assert.match(String(url), /turns\?conversationId=a$/)
    assert.equal(options?.body, JSON.stringify(body)); assert.equal((options?.headers as Record<string, string>)['Idempotency-Key'], original.key)
    return new Response(JSON.stringify(f.snapshot('a')))
  })
  await api.send('t', body, original.key, 'a'); assert.equal(received, true)
})

test('旧发送核实返回错误会话时保留pending与所有草稿', async () => {
  const f = fixture(); session.set(globalKey, JSON.stringify(original)); seedDraft('a', body.text); seedDraft('b', 'B草稿')
  f.api.send = async () => f.snapshot('b')
  const v = f.mount(); await flush()
  try {
    await v.state.retry(); assert.equal(v.state.pending.value?.key, original.key); assert.equal(v.state.text.value, body.text)
    assert.match(v.state.error.value, /不属于原会话/)
    await v.state.selectSession('b'); assert.equal(v.state.text.value, 'B草稿')
  } finally { v.close() }
})

test('恢复旧pending后原会话被删除，保留原草稿且不借其他会话重放', async () => {
  const f = fixture(); session.set(globalKey, JSON.stringify(original)); seedDraft('a', body.text); seedDraft('b', 'B草稿')
  const v = f.mount(); await flush()
  try {
    await v.state.selectSession('b'); f.rows.splice(0, 1); await v.state.refresh(); await flush()
    assert.ok(session.has(pendingKey('designer', 't', 'a')))
    assert.equal(JSON.parse(local.get(composerDraftKey('designer', 't', 'a'))!).text, body.text)
    assert.equal(v.state.text.value, 'B草稿'); assert.match(v.state.preferenceNotice.value, /已删除会话.*保留/)
    await v.state.retry(); assert.equal(f.calls.filter(c => c.kind === 'send').length, 0)
  } finally { v.close() }
})

test('任务后来已完成时仍可用原key核实已接受的旧发送', async () => {
  const f = fixture(); session.set(globalKey, JSON.stringify(original)); seedDraft('a', body.text)
  f.api.get = async (_t, _s, id) => ({ ...f.snapshot(id), completed: true })
  let writes = 0
  f.api.send = async (_t, sent, key, hint) => { writes++; assert.equal(key, original.key); assert.deepEqual(sent, body); assert.equal(hint, 'a'); return { ...f.snapshot('a'), completed: true } }
  const v = f.mount(); await flush()
  try { assert.equal(v.state.canSend.value, false); await v.state.retry(); assert.equal(writes, 1); assert.equal(v.state.pending.value, undefined) } finally { v.close() }
})
