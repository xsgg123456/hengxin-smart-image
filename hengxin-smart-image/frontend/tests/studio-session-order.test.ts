import test from 'node:test'
import assert from 'node:assert/strict'
import type { Studio } from '../src/api/overseas/studio'
import { composerDraftKey } from '../src/views/overseas/studio/studio-composer-draft'
import { fixture, flush, deferred, local } from './studio-sessions-fixture'
import { IdentityError } from '../src/api/identity/request'

test('新建后迟到的旧列表不能删除新会话、草稿或抢选择', async () => {
  const f = fixture(), v = f.mount(); await flush(); const s = v.state
  try {
    const old = f.snapshot('a'), late = deferred<Studio>(), original = f.api.get
    let delay = true
    f.api.get = async (...args) => { if (args[2] === 'a' && delay) { delay = false; return late.promise }; return original(...args) }
    const reading = s.refresh(); await flush()
    await s.newConversation(); s.text.value = '新会话必须保留的草稿'; await flush()
    const id = s.activeId.value, key = composerDraftKey('designer', 't', id)
    late.resolve(old); await reading; await flush()
    assert.equal(s.activeId.value, id)
    assert.ok(s.sessions.value.some(row => row.id === id))
    assert.equal(s.text.value, '新会话必须保留的草稿')
    assert.match(local.get(key) || '', /新会话必须保留的草稿/)
  } finally { v.close() }
})

test('A回执未返回时B可发送，旧A回执不回退B运行状态或清B新草稿', async () => {
  const f = fixture(), late = deferred<Studio>()
  f.api.send = async (_task, body) => {
    const row = f.rows.find(row => row.id === body.conversationId)!
    row.version++; row.activeTurnId = `job-${row.id}`; row.status = 'running'; row.turnCount++
    return row.id === 'a' ? late.promise : f.snapshot('b')
  }
  const v = f.mount(); await flush(); const s = v.state
  try {
    s.text.value = 'A发送'; const sending = s.send(); const old = f.snapshot('a')
    await s.selectSession('b'); s.text.value = 'B发送'; assert.equal(s.canSend.value, true)
    await s.send(); s.text.value = 'B下一轮草稿'; await flush()
    assert.equal(s.sessions.value.find(row => row.id === 'b')?.activeTurnId, 'job-b')
    late.resolve(old); await sending; await flush()
    assert.equal(s.activeId.value, 'b'); assert.equal(s.text.value, 'B下一轮草稿')
    assert.equal(s.runningCount.value, 2); assert.equal(s.pending.value, undefined)
    await s.selectSession('a'); assert.equal(s.pending.value, undefined); assert.equal(s.text.value, '')
  } finally { v.close() }
})

test('并发新建成功后旧发送回执不能吞掉新会话', async () => {
  const f = fixture(), late = deferred<Studio>()
  f.api.send = async () => late.promise
  const v = f.mount(); await flush(); const s = v.state
  try {
    const old = f.snapshot('a'); s.text.value = 'A发送'; const sending = s.send()
    await s.newConversation(); const id = s.activeId.value; s.text.value = '新会话草稿'
    late.resolve(old); await sending; await flush()
    assert.equal(s.activeId.value, id); assert.equal(s.sessions.value.length, 3)
    assert.equal(s.text.value, '新会话草稿')
  } finally { v.close() }
})

test('旧GET不能回退重命名、复活删除的会话或冻结已解冻任务', async () => {
  const f = fixture(), v = f.mount(); await flush(); const s = v.state
  try {
    await s.selectSession('b')
    const old = f.snapshot('a'), late = deferred<Studio>(), original = f.api.get
    let delay = true
    f.api.get = async (...args) => { if (args[2] === 'b' && delay) { delay = false; return late.promise }; return original(...args) }
    const reading = s.refresh(); await flush(); await s.selectSession('a')
    await s.renameConversation(s.sessions.value[0], '主图方案')
    await s.deleteConversation(s.sessions.value[0]); f.rows.splice(0, 1)
    // The original B read stays pending; selecting a new engine obtains fresh state.
    await s.newConversation(); s.selected.value = ['p']; await s.archive('SKU')
    await s.complete(); await s.reopen(); s.text.value = '解冻后草稿'
    late.resolve(old); await reading; await flush()
    assert.ok(!s.sessions.value.some(row => row.id === 'a'))
    assert.equal(s.data.value?.completed, false); assert.equal(s.data.value?.reopened, true)
    assert.equal(s.text.value, '解冻后草稿'); assert.equal(s.locked.value, false)
  } finally { v.close() }
})

test('迟到404经过重新核实，不把后来选择的新会话切回默认会话', async () => {
  const f = fixture(), v = f.mount(); await flush(); const s = v.state
  try {
    const late = deferred<Studio>(), original = f.api.get; let delay = true
    f.api.get = async (...args) => { if (args[2] === 'a' && delay) { delay = false; return late.promise }; return original(...args) }
    const reading = s.refresh(); await flush(); await s.newConversation()
    const id = s.activeId.value; s.text.value = '保留当前选择'
    late.reject(new IdentityError(404, '旧请求错误')); await reading; await flush()
    assert.equal(s.activeId.value, id); assert.equal(s.text.value, '保留当前选择')
    assert.equal(s.error.value, '')
  } finally { v.close() }
})

test('同一轮微任务里的读取和创建回执也不能回退共享列表', async () => {
  const f = fixture(), v = f.mount(); await flush(); const s = v.state
  try {
    const old = f.snapshot('a'), reading = deferred<Studio>(), creating = deferred<Studio>()
    const original = f.api.get; let delay = true
    f.api.get = async (...args) => { if (delay) { delay = false; return reading.promise }; return original(...args) }
    const create = f.api.newConversation; f.api.newConversation = async () => creating.promise
    const refresh = s.refresh(); const pending = s.newConversation()
    const result = await create('t', 'test-key')
    reading.resolve(old); creating.resolve(result); await Promise.all([refresh, pending]); await flush()
    assert.equal(s.sessions.value.length, 3); assert.equal(s.activeId.value, 'n2')
    assert.equal(s.data.value?.conversations?.length, 3)
  } finally { v.close() }
})

test('稳定读取可在任务版本不变时清除已删除归档并禁用完成', async () => {
  const f = fixture(), v = f.mount(); await flush(); const s = v.state
  try {
    s.selected.value = ['p']; await s.archive('SKU')
    assert.equal(s.data.value?.archiveId, 'archive'); assert.equal(s.canComplete.value, true)
    const get = f.api.get
    f.api.get = async (...args) => ({ ...await get(...args), archiveId: null })
    await s.refresh()
    assert.equal(s.data.value?.archiveId, null); assert.equal(s.canComplete.value, false)
    await s.selectSession('b'); assert.equal(s.data.value?.archiveId, null)
  } finally { v.close() }
})
