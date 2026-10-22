import test from 'node:test'
import assert from 'node:assert/strict'
import { defineComponent } from 'vue'
import { mount, flush } from './membership-test-harness'
import { useStudio } from '../src/views/overseas/studio/use-studio'
import { createStudioApi, isStudio, type Studio, type StudioApi } from '../src/api/overseas/studio'
import { emptyTaskDraft, type TaskDetail } from '../src/api/overseas/tasks'
import { IdentityError } from '../src/api/identity/request'

const task: TaskDetail = { ...emptyTaskDraft(), id: 'task', workflow: 'studio', status: 'studio', version: 3, createdAt: '', updatedAt: '', createdBy: { id: 'u', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: ['task.design'], events: [] }
const snapshot = (): Studio => ({ taskId: task.id, taskVersion: 3, archiveId: 'real-archive', reopened: false, completed: false, conversationId: 'original', turns: [], materials: [], skills: [{ id: "skill", name: "test", displayName: "测试 Skill", description: "" }], activeTurnId: null })
const store = new Map<string, string>()
Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: { getItem: (k: string) => store.get(k) || null, setItem: (k: string, v: string) => store.set(k, v), removeItem: (k: string) => store.delete(k) } })
function fake(extra: Partial<StudioApi> = {}): StudioApi {
  return { get: async () => snapshot(), transcript: async () => ({ items: [], cursor: 0, hasMore: false }), events: async () => ({ items: [], cursor: 0 }), send: async () => snapshot(), cancel: async () => snapshot(), archive: async () => snapshot(), newConversation: async () => snapshot(), complete: async () => snapshot(), reopen: async () => snapshot(), removeMaterial: async () => snapshot(), upload: async () => { throw Error('不上传') }, ...extra }
}
function open(api: StudioApi, current = () => task) {
  let state!: ReturnType<typeof useStudio>, changes = 0
  const failures: unknown[] = []
  const view = mount(defineComponent({ setup() { state = useStudio(current, e => failures.push(e), () => changes++, api, 'designer'); return () => null } }))
  return { state, failures, changes: () => changes, close: view.close }
}

test('完成与解冻API提交冻结版本、身份和幂等键，新对话仍为空对象', async () => {
  const calls: { url: string; options?: RequestInit }[] = []
  const api = createStudioApi(async (u, o) => { calls.push({ url: String(u), options: o }); return new Response(JSON.stringify(snapshot())) })
  await api.complete('task', 3, 'complete-key'); await api.reopen('task', 4, 'reopen-key'); await api.newConversation('task', 'new-key')
  assert.deepEqual(calls.map(c => JSON.parse(String(c.options?.body))), [{ version: 3 }, { version: 4 }, {}])
  assert.deepEqual(calls.map(c => c.url.split('/').pop()), ['complete', 'reopen', 'conversations'])
  assert.deepEqual(calls.map(c => (c.options?.headers as Record<string, string>)['Idempotency-Key']), ['complete-key', 'reopen-key', 'new-key'])
  assert.ok(calls.every(c => c.options?.credentials === 'include'))
  for (const value of [0, -1, 1.5, undefined]) assert.equal(isStudio({ ...snapshot(), taskVersion: value }, task.id), false)
  assert.equal(isStudio({ ...snapshot(), archiveId: '' }, task.id), false)
  assert.equal(isStudio({ ...snapshot(), reopened: undefined }, task.id), false)
  assert.equal(isStudio({ ...snapshot(), archiveId: null }, task.id), true)
})

test('完成锁定、解冻回原会话，草稿引用和历史保留，随后可发送再完成', async () => {
  store.clear(); let current = snapshot(); const actions: string[] = []
  const view = open(fake({ get: async () => current,
    complete: async (_id, version) => { assert.equal(version, current.taskVersion); actions.push('complete'); current = { ...current, completed: true, taskVersion: version + 1 }; return current },
    reopen: async (_id, version) => { assert.equal(version, current.taskVersion); actions.push('reopen'); current = { ...current, completed: false, reopened: true, taskVersion: version + 1 }; return current },
    send: async () => { actions.push('send'); return current }
  }))
  try {
    await flush(); const s = view.state
    s.text.value = '继续修图'; s.skill.value = 'skill'; s.selected.value = ['picture']
    s.attachments.value = [{ id: 'upload:f', name: '素材', url: '/file', source: 'upload', contentType: 'image/png', sizeBytes: 1 }]
    const before = { attachments: [...s.attachments.value], materials: [...s.data.value!.materials] }
    assert.equal(await s.complete(), true); assert.equal(s.locked.value, true); assert.equal(s.canReopen.value, true)
    assert.equal(await s.reopen(), true); assert.equal(s.data.value?.conversationId, 'original'); assert.equal(s.data.value?.reopened, true)
    assert.equal(s.text.value, '继续修图'); assert.equal(s.skill.value, 'skill'); assert.deepEqual(s.attachments.value, before.attachments); assert.deepEqual(s.data.value?.materials, before.materials)
    assert.equal(s.canSend.value, true); await s.send(); await s.complete()
    assert.deepEqual(actions, ['complete', 'reopen', 'send', 'complete']); assert.ok(view.changes() >= 4)
  } finally { view.close() }
})

test('完成和解冻未知结果跨卸载保存同一版本与key；读到较新状态也不改请求', async () => {
  for (const kind of ['complete', 'reopen'] as const) {
    store.clear(); let current = { ...snapshot(), completed: kind === 'reopen' }, failed = true
    const calls: unknown[] = []
    const api = fake({ get: async () => current, [kind]: async (_id: string, version: number, key: string) => {
      calls.push({ version, key }); if (failed) throw new IdentityError(0, '连接中断')
      return { ...snapshot(), completed: kind === 'complete', taskVersion: 4 }
    } })
    const first = open(api)
    try { await flush(); await first.state[kind](); assert.ok(first.state.pending.value); assert.equal(first.state.locked.value, true) } finally { first.close() }
    current = { ...current, taskVersion: 7, completed: kind !== 'complete' }
    const second = open(api)
    try {
      await flush(); failed = false; await second.state.retry()
      assert.deepEqual(calls[0], calls[1]); assert.equal(second.state.pending.value, undefined)
      assert.equal(second.state.data.value?.taskVersion, 7, '旧幂等结果不能回退较新状态')
      assert.equal(second.state.data.value?.completed, current.completed)
    } finally { second.close() }
  }
})

test('409不误切状态，刷新恢复版本；无权限、活动、上传及无归档禁用对应操作', async () => {
  store.clear(); let current = snapshot(), writes = 0
  const view = open(fake({ get: async () => current, complete: async () => { writes++; throw new IdentityError(409, '冲突', '任务已变化，请刷新后重试') } }))
  try {
    await flush(); const s = view.state
    await s.complete(); assert.equal(s.data.value?.completed, false); assert.equal(s.pending.value, undefined); assert.match(s.error.value, /刷新/)
    current = { ...current, taskVersion: 4 }; await s.refresh(); assert.equal(s.data.value?.taskVersion, 4)
    s.data.value!.archiveId = null; assert.equal(s.canComplete.value, false); await s.complete(); assert.equal(writes, 1)
    s.data.value!.completed = true; assert.equal(s.canReopen.value, true, '归档删除仍可解冻')
    s.data.value!.activeTurnId = 'active'; assert.equal(s.canReopen.value, false)
    s.data.value!.activeTurnId = null; s.uploading.value = true; assert.equal(s.canReopen.value, false)
  } finally { view.close() }
  const readonly = open(fake({ get: async () => ({ ...snapshot(), completed: true }) }), () => ({ ...task, capabilities: [] }))
  try { await flush(); assert.equal(readonly.state.canReopen.value, false); await readonly.state.reopen() } finally { readonly.close() }
})

test('完成页低频感知其他成员解冻并刷新任务详情，保留当前草稿', async t => {
  store.clear(); t.mock.timers.enable({ apis: ['setTimeout'] })
  let current = { ...snapshot(), completed: true }, reads = 0
  const view = open(fake({ get: async () => { reads++; return current } }))
  try {
    await flush(); view.state.text.value = '保留草稿'
    current = { ...current, completed: false, reopened: true, taskVersion: 4 }
    t.mock.timers.tick(29999); await flush(); assert.equal(reads, 1)
    t.mock.timers.tick(1); await flush(); assert.equal(reads, 2); assert.equal(view.state.data.value?.completed, false)
    assert.equal(view.changes(), 1); assert.equal(view.state.canSend.value, true); assert.equal(view.state.text.value, '保留草稿')
  } finally { view.close() }
})

test('旧版本遗留完成请求不能补最新版本静默执行，清除后要求重新确认', async () => {
  store.clear(); store.set('hx-studio-pending:designer:task', JSON.stringify({ kind: 'complete', key: 'legacy' }))
  let writes = 0
  const view = open(fake({ complete: async () => { writes++; return snapshot() } }))
  try { await flush(); await view.state.retry(); assert.equal(writes, 0); assert.equal(view.state.pending.value, undefined); assert.match(view.state.error.value, /缺少任务版本/) } finally { view.close() }
})
