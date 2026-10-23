import test from 'node:test'
import assert from 'node:assert/strict'
import { createStudioApi, isStudio, type Studio, type UploadedAsset } from '../src/api/overseas/studio'
import { IdentityError } from '../src/api/identity/request'
import { sessionPreferenceKey } from '../src/views/overseas/studio/studio-session-state'
import { fixture, flush, deferred, asset, row, local } from './studio-sessions-fixture'

test('选择按身份任务恢复，草稿、Skill、附件、滚动独立，新建保留原草稿', async () => {
  const f = fixture(), v = f.mount(); await flush(); const s = v.state
  try {
    assert.equal(s.activeId.value, 'a'); s.text.value = 'A草稿'; s.skill.value = 's'; s.add(['upload:a']); s.saveScroll(180, 'a')
    await s.selectSession('b'); s.text.value = 'B草稿'; s.saveScroll(42, 'b')
    assert.deepEqual(s.attachments.value, []); assert.equal(s.skill.value, '')
    await s.selectSession('a'); assert.equal(s.text.value, 'A草稿'); assert.equal(s.scrollPosition.value, 180); assert.equal(s.skill.value, 's'); assert.equal(s.attachments.value[0].id, 'upload:a')
    await s.newConversation(); assert.equal(s.activeId.value, 'n2'); assert.equal(s.text.value, '')
    await s.selectSession('b'); assert.equal(s.text.value, 'B草稿')
  } finally { v.close() }
  const next = f.mount(); await flush()
  try { assert.equal(next.state.activeId.value, 'b'); assert.equal(next.state.text.value, 'B草稿'); assert.equal(next.state.scrollPosition.value, 42) } finally { next.close() }
  const other = f.mount('other'); await flush()
  try { assert.equal(other.state.activeId.value, 'a'); assert.equal(other.state.text.value, '') } finally { other.close() }
})

test('切换期间上传及迟到发送只更新原会话，不清新草稿或抢焦点', async () => {
  const f = fixture(), upload = deferred<UploadedAsset>(), send = deferred<Studio>()
  f.api.upload = async (_task, _file, _signal, id) => { assert.equal(id, 'a'); return upload.promise }
  f.api.send = async (_task, body) => { assert.equal(body.conversationId, 'a'); return send.promise }
  const v = f.mount(); await flush(); const s = v.state
  try {
    s.text.value = 'A意见'; const uploading = s.receive([new File(['a'], 'a.txt')]); await s.selectSession('b'); s.text.value = 'B意见'
    assert.equal(s.uploading.value, false); upload.resolve(asset('a-new')); await uploading
    assert.equal(s.activeId.value, 'b'); assert.deepEqual(s.attachments.value, []); assert.equal(s.text.value, 'B意见')
    await s.selectSession('a'); assert.equal(s.attachments.value[0].id, 'upload:a-new')
    const sending = s.send(); await s.selectSession('b'); send.resolve(f.snapshot('a')); await sending
    assert.equal(s.activeId.value, 'b'); assert.equal(s.text.value, 'B意见'); await s.selectSession('a'); assert.equal(s.text.value, ''); assert.deepEqual(s.attachments.value, [])
  } finally { v.close() }
})

test('未知发送仅锁原会话，刷新恢复原ID和幂等键核实，其他会话可发送', async () => {
  const f = fixture(); let fail = true
  const send = f.api.send
  f.api.send = async (...args) => { const result = await send(...args); if (fail && args[1].conversationId === 'a') throw new IdentityError(0, '连接中断'); return result }
  let v = f.mount(); await flush()
  v.state.text.value = 'A请求'; await v.state.send(); assert.ok(v.state.pending.value)
  await v.state.selectSession('b'); assert.equal(v.state.pending.value, undefined); v.state.text.value = 'B请求'; await v.state.send(); await v.state.selectSession('a'); v.close()
  v = f.mount(); await flush()
  try {
    assert.ok(v.state.pending.value); fail = false; await v.state.retry()
    const sends = f.calls.filter(c => c.kind === 'send' && c.id === 'a'); assert.equal(sends.length, 2); assert.equal(sends[0].key, sends[1].key); assert.deepEqual(sends[0].body, sends[1].body)
    assert.equal(v.state.text.value, '')
  } finally { v.close() }
})

test('后台状态实时更新与未读，跨会话可并行，任何会话在途均禁完成', async () => {
  const f = fixture(), v = f.mount(); await flush(); const s = v.state
  try {
    f.rows[0].turnCount = 1; f.rows[0].activeTurnId = 'job'; f.rows[0].status = 'running'; f.rows[0].updatedAt = '2026-10-24T02:00:00Z'; await s.refresh()
    assert.equal(s.canNewConversation.value, true); await s.selectSession('b'); s.text.value = '并行要求'; assert.equal(s.canSend.value, true); assert.equal(s.runningCount.value, 1); assert.equal(s.canComplete.value, false)
    f.rows[0].activeTurnId = null; f.rows[0].status = 'succeeded'; f.rows[0].updatedAt = '2026-10-24T03:00:00Z'; await s.refresh()
    assert.equal(s.activeId.value, 'b'); assert.equal(s.sessions.value[0].unread, true); await s.selectSession('a'); assert.equal(s.sessions.value[0].unread, false)
  } finally { v.close() }
})

test('完成与解冻跨所有会话同步，草稿保留且没有自动发送', async () => {
  const f = fixture(), v = f.mount(); await flush(); const s = v.state
  try {
    s.text.value = 'A待发'; await s.selectSession('b'); s.text.value = 'B待发'; s.selected.value = ['p']; await s.archive('SKU'); await s.complete()
    assert.equal(s.locked.value, true); await s.selectSession('a'); assert.equal(s.text.value, 'A待发'); assert.equal(s.locked.value, true)
    assert.equal(s.canNewConversation.value, false); await s.reopen(); assert.equal(s.locked.value, false); await s.selectSession('b'); assert.equal(s.text.value, 'B待发'); assert.equal(s.locked.value, false)
    assert.equal(f.calls.filter(c => c.kind === 'send').length, 0)
  } finally { v.close() }
})

test('10上限含删除中历史，删除失败可重试且只锁目标，重命名校验', async () => {
  const f = fixture(); for (let i = 2; i < 10; i++) f.rows.push(row(String(i)))
  const v = f.mount(); await flush(); const s = v.state
  try {
    assert.equal(s.canNewConversation.value, false); await s.newConversation(); assert.equal(f.calls.filter(c => c.kind === 'create').length, 0)
    await s.renameConversation(s.sessions.value[0], ''); assert.match(s.sessionError.value, /1–30/)
    await s.renameConversation(s.sessions.value[0], '主图'); assert.equal(s.sessions.value[0].name, '主图')
    await s.deleteConversation(s.sessions.value[0]); assert.equal(s.locked.value, true); assert.equal(s.sessions.value.length, 10)
    await s.selectSession('b'); assert.equal(s.locked.value, false)
    f.rows[0].deletionStatus = 'delete_failed'; await s.refresh(); await s.deleteConversation(s.sessions.value[0]); assert.equal(f.calls.filter(c => c.kind === 'delete').length, 2)
    f.rows.splice(0, 1); await s.refresh(); assert.equal(s.sessions.value.length, 9); assert.equal(s.canNewConversation.value, true)
  } finally { v.close() }
})

test('选择读取迟到不覆盖当前会话，旧ID已删除恢复可用会话且只读身份不写', async () => {
  const f = fixture(), late = deferred<Studio>(), original = f.api.get; let delay = false
  f.api.get = async (...args) => { if (args[2] === 'a' && delay) return late.promise; return original(...args) }
  const v = f.mount(); await flush()
  try {
    delay = true; const refreshing = v.state.refresh(); await v.state.selectSession('b'); v.state.text.value = 'B草稿'; late.resolve(f.snapshot('a')); await refreshing
    assert.equal(v.state.activeId.value, 'b'); assert.equal(v.state.data.value?.conversationId, 'b'); assert.equal(v.state.text.value, 'B草稿')
  } finally { v.close() }
  local.set(sessionPreferenceKey('designer', 't'), JSON.stringify({ activeId: 'deleted' })); delay = false
  f.api.get = async (...args) => { if (args[2] === 'deleted') throw new IdentityError(410, '已删除'); return original(...args) }
  const next = f.mount(); await flush()
  try { assert.equal(next.state.activeId.value, 'a'); assert.equal(next.state.data.value?.conversationId, 'a') } finally { next.close() }
  const readonly = f.mount('viewer', []); await flush()
  try { assert.equal(readonly.state.canNewConversation.value, false); assert.equal(readonly.state.locked.value, true) } finally { readonly.close() }
})

test('会话API显式绑定读取/上传/移除及管理版本幂等，DTO拒绝畸形状态', async () => {
  const f = fixture(), calls: { url: string; init?: RequestInit }[] = []
  const api = createStudioApi(async (url, init) => { calls.push({ url: String(url), init }); return new Response(JSON.stringify(String(url).includes('/transcript') ? { items: [], cursor: 0, hasMore: false } : init?.body instanceof FormData ? asset('x') : f.snapshot('a'))) })
  const signal = new AbortController().signal
  await api.get('t', signal, 'a'); await api.transcript('t', 4, signal, 'a'); await api.upload('t', new File(['x'], 'x'), signal, 'a'); await api.removeMaterial('t', 'upload:x', 'a')
  for (const call of calls) assert.match(call.url, /conversationId=a/)
  await api.renameConversation('t', 'a', '主图', 2, 'rename-key'); await api.deleteConversation('t', 'a', 3, 'delete-key')
  assert.equal(calls[4].init?.method, 'PATCH'); assert.deepEqual(JSON.parse(String(calls[4].init?.body)), { name: '主图', version: 2 })
  assert.equal(calls[5].init?.method, 'DELETE'); assert.equal((calls[5].init?.headers as Record<string, string>)['Idempotency-Key'], 'delete-key')
  const bad = f.snapshot(); bad.conversations![0].status = 'secret'; assert.equal(isStudio(bad, 't'), false)
})


test('后台重命名不伪报新结果，零会话保留任务归档与完成能力', async () => {
  const f = fixture(); f.rows[0].status = 'succeeded'; f.rows[0].turnCount = 1
  const v = f.mount(); await flush(); const s = v.state
  try {
    await s.selectSession('b'); f.rows[0].name = '后台改名'; f.rows[0].updatedAt = '2026-10-24T04:00:00Z'; await s.refresh()
    assert.equal(s.sessions.value[0].unread, false)
    s.selected.value = ['p']; await s.archive('SKU'); f.rows.splice(0); await s.refresh(); await flush()
    assert.equal(s.activeId.value, ''); assert.equal(s.sessions.value.length, 0); assert.equal(s.canSend.value, false); assert.equal(s.canComplete.value, true)
    await s.complete(); assert.equal(s.data.value?.completed, true)
  } finally { v.close() }
})

test('未知新建管理请求保留同一幂等键，后台创建结果不抢后来选择', async () => {
  const f = fixture(), creating = deferred<Studio>(), original = f.api.newConversation
  let first = true
  f.api.newConversation = async (...args) => { const response = await original(...args); if (first) { first = false; throw new IdentityError(0, '响应中断') }; return response }
  const v = f.mount(); await flush()
  try {
    await v.state.newConversation(); assert.ok(v.state.sessionPending.value); assert.equal(v.state.canNewConversation.value, false)
    await v.state.retrySession(); const creates = f.calls.filter(c => c.kind === 'create'); assert.equal(creates[0].key, creates[1].key)
    f.api.newConversation = async () => creating.promise
    const request = v.state.newConversation(); await v.state.selectSession('b'); f.rows.push(row('late')); creating.resolve(f.snapshot('late')); await request
    assert.equal(v.state.activeId.value, 'b')
  } finally { v.close() }
})
