import test from 'node:test'
import assert from 'node:assert/strict'
import { createRenderer, defineComponent, nextTick } from 'vue'
import { useStudio } from '../src/views/overseas/studio/use-studio'
import { composerDraftKey } from '../src/views/overseas/studio/studio-composer-draft'
import { annotationDraft } from '../src/views/hengxin/components/annotation/annotation-drafts'
import { emptyTaskDraft, type TaskDetail } from '../src/api/overseas/tasks'
import { IdentityError } from '../src/api/identity/request'
import type { Asset, Studio, StudioApi, TurnInput } from '../src/api/overseas/studio'

const local = new Map<string, string>(), session = new Map<string, string>()
let unavailable = false
for (const [name, storage] of [['localStorage', local], ['sessionStorage', session]] as const) {
  Object.defineProperty(globalThis, name, { configurable: true, value: {
    getItem: (key: string) => { if (unavailable) throw Error('storage disabled'); return storage.get(key) || null },
    setItem: (key: string, value: string) => { if (unavailable) throw Error('quota'); storage.set(key, value) },
    removeItem: (key: string) => { if (unavailable) throw Error('storage disabled'); storage.delete(key) }
  } })
}
const renderer = createRenderer<object, object>({ createElement: () => ({}), createText: () => ({}), createComment: () => ({}),
  insert() {}, remove() {}, parentNode: () => null, nextSibling: () => null, patchProp() {}, setText() {}, setElementText() {} })
const flush = async () => { for (let i = 0; i < 20; i++) await Promise.resolve(); await nextTick() }
const asset = (id: string): Asset => ({ id: `upload:${id}`, name: `${id}.txt`, contentType: 'text/plain', sizeBytes: 1,
  source: 'upload', url: `/api/overseas/v1/tasks/t/studio/files/${id}/content` })
function fixture() {
  local.clear(); session.clear(); unavailable = false
  let current: Studio = { taskId: 't', taskVersion: 1, archiveId: null, completed: false, reopened: false,
    conversationId: 'c1', materials: [asset('a'), asset('b'), asset('c')], turns: [],
    skills: [{ id: 's', name: 'skill', displayName: '测试Skill', description: '' }], activeTurnId: null }
  const calls: string[] = [], sends: { body: TurnInput; key: string }[] = []
  const api: StudioApi = { get: async () => structuredClone(current), transcript: async () => ({ items: [], cursor: 0, hasMore: false }),
    events: async () => ({ items: [], cursor: 0 }), cancel: async () => current, archive: async () => current,
    complete: async () => current, reopen: async () => current,
    newConversation: async () => { current.conversationId = 'c2'; return structuredClone(current) },
    send: async (_id, body, key) => { sends.push({ body, key }); return structuredClone(current) },
    upload: async () => asset('duplicate'),
    removeMaterial: async (_task, id) => { calls.push(id); current.materials = current.materials.filter(a => a.id !== id); return structuredClone(current) } }
  return { api, calls, sends, get current() { return current } }
}
function mount(api: StudioApi, actor = 'designer', taskId = 't', capabilities = ['task.design']) {
  const task = { ...emptyTaskDraft(), id: taskId, version: 1, capabilities } as TaskDetail
  let state!: ReturnType<typeof useStudio>
  const failures: unknown[] = []
  const app = renderer.createApp(defineComponent({ setup() {
    state = useStudio(() => task, e => failures.push(e), () => {}, api, actor); return () => null
  } })); app.mount({})
  return { state, failures, close: () => app.unmount() }
}

test('上传/引用、文字、Skill整页重建恢复；已隐藏和重复上传身份保持，移除后刷新不复活', async () => {
  const f = fixture(), first = mount(f.api); await flush()
  first.state.text.value = '未发送意见'; first.state.skill.value = 's'; first.state.add(['upload:a'])
  await first.state.receive([new File(['x'], 'duplicate.txt')]); await flush()
  await first.state.removeMaterial('upload:a'); first.close()
  const second = mount(f.api); await flush()
  try {
    assert.equal(second.state.text.value, '未发送意见'); assert.equal(second.state.skill.value, 's')
    assert.deepEqual(second.state.attachments.value.map(a => a.id), ['upload:a', 'upload:duplicate'])
    assert.equal(second.state.data.value?.materials.some(a => a.id === 'upload:a'), false)
    second.state.attachments.value.pop(); await second.state.refresh()
  } finally { second.close() }
  const third = mount(f.api); await flush()
  try { assert.deepEqual(third.state.attachments.value.map(a => a.id), ['upload:a']) } finally { third.close() }
})

test('草稿按用户、任务和对话隔离；服务端会话变化不会把旧草稿带入新对话', async () => {
  const f = fixture(), first = mount(f.api); await flush(); first.state.text.value = '私有草稿'; first.close()
  for (const [actor, task] of [['other', 't'], ['designer', 'other']]) {
    const next = mount(f.api, actor, task); await flush()
    assert.equal(next.state.text.value, ''); next.close()
  }
  f.current.conversationId = 'c2'
  const next = mount(f.api); await flush()
  try { assert.equal(next.state.text.value, ''); next.state.text.value = '新草稿'; f.current.conversationId = 'c3'; await next.state.refresh(); assert.equal(next.state.text.value, '') } finally { next.close() }
  assert.equal(JSON.parse(local.get(composerDraftKey('designer', 't', 'c1'))!).text, '私有草稿')
})

test('发送未知跨刷新保留冻结请求；核实成功清草稿，明确失败保留，开始新对话成功清空', async () => {
  const f = fixture(); let lose = true
  const send = f.api.send
  f.api.send = async (...args) => { const result = await send(...args); if (lose) throw new IdentityError(503, '暂不可用'); return result }
  const first = mount(f.api); await flush(); first.state.text.value = '完整正文'; first.state.add(['upload:a']); first.state.skill.value = 's'
  await first.state.send(); assert.ok(first.state.pending.value); first.close()
  const next = mount(f.api); await flush()
  try {
    assert.equal(next.state.text.value, '完整正文'); assert.equal(next.state.attachments.value.length, 1); assert.equal(next.state.locked.value, true)
    lose = false; await next.state.retry(); assert.deepEqual(f.sends[0], f.sends[1]); assert.equal(local.size, 0)
    next.state.text.value = '冲突后留存'; f.api.send = async () => { throw new IdentityError(409, '冲突') }
    await next.state.send(); assert.equal(next.state.pending.value, undefined); assert.equal(next.state.text.value, '冲突后留存')
  } finally { next.close() }
  const third = mount(f.api); await flush()
  try { assert.equal(third.state.text.value, '冲突后留存'); await third.state.newConversation(); assert.equal(local.size, 0) } finally { third.close() }
  const final = mount(f.api); await flush(); assert.equal(final.state.text.value, ''); final.close()
})

test('新对话响应丢失，刷新见新会话后重试仍清理原会话草稿', async () => {
  const f = fixture(), original = f.api.newConversation; let lose = true
  f.api.newConversation = async (...args) => { const result = await original(...args); if (lose) throw Error('网络中断'); return result }
  const first = mount(f.api); await flush(); first.state.text.value = '旧对话待发'; await first.state.newConversation(); first.close()
  const next = mount(f.api); await flush()
  try { assert.equal(next.state.text.value, ''); assert.ok(next.state.pending.value); lose = false; await next.state.retry(); assert.equal(local.size, 0) } finally { next.close() }
})

test('图片修改引用、标注附件、意见及可再编辑的标记跨刷新恢复并发送', async () => {
  const f = fixture(), picture = { id: 'p', name: '成品', url: '/api/overseas/v1/tasks/t/studio/pictures/p/content', width: 10, height: 10, turnId: 'r', sku: null, archived: false }
  f.current.turns = [{ id: 'r', text: '旧消息', conversationId: 'c1', skillName: null, status: 'succeeded', reply: '', error: null,
    jobId: 'j', jobVersion: 1, attachments: [], pictures: [picture], referencePictures: [], createdAt: '' }]
  const first = mount(f.api); await flush()
  await first.state.confirmRevision(picture, { text: '改标注处', file: new File(['x'], 'mark.png') })
  annotationDraft(first.state.draftKey(picture)).marks = [{ id: 'mark', kind: 'rect', x: 1, y: 1, width: 2, height: 2, points: [], note: '改标注处' }]
  first.close()
  const next = mount(f.api); await flush()
  try {
    assert.equal(next.state.revisions.value.length, 1); assert.equal(annotationDraft(next.state.draftKey(picture)).marks.length, 1)
    await next.state.send(); assert.deepEqual(f.sends[0].body.imageEdits, [{ pictureId: 'p', annotationId: 'upload:duplicate', text: '改标注处' }]); assert.equal(local.size, 0)
  } finally { next.close() }
})

test('存储失败、损坏和跨任务附件不导致崩溃或恢复不可信URL；只读不发写请求', async () => {
  const f = fixture(); unavailable = true
  const first = mount(f.api); await flush(); first.state.text.value = '保持可编辑'; assert.match(first.state.draftNotice.value, /无法保存/); assert.equal(first.state.text.value, '保持可编辑'); first.close()
  unavailable = false
  for (const value of ['{broken', JSON.stringify({ version: 1, text: 'unsafe', skill: '', attachments: [{ ...asset('a'), url: 'https://evil.invalid/a' }], references: [], revisions: [] })]) {
    local.set(composerDraftKey('designer', 't', 'c1'), value)
    const next = mount(f.api); await flush(); assert.match(next.state.draftNotice.value, /无法恢复/); assert.equal(next.state.attachments.value.length, 0); next.close()
  }
  const readonly = mount(f.api, 'viewer', 't', []); await flush(); await readonly.state.removeMaterials(['upload:a']); assert.deepEqual(f.calls, []); readonly.close()
})

test('修正失效Skill或损坏草稿后清理过期提示，未修正Skill继续提示', async () => {
  const f = fixture(), key = composerDraftKey('designer', 't', 'c1')
  local.set(key, JSON.stringify({ version: 1, text: '草稿', skill: 'retired', attachments: [], references: [], revisions: [] }))
  const first = mount(f.api); await flush()
  try {
    assert.match(first.state.draftNotice.value, /Skill 已不可用/)
    assert.equal(first.state.canSend.value, false); await first.state.send(); assert.equal(f.sends.length, 0)
    first.state.text.value = '只改文字'; assert.match(first.state.draftNotice.value, /Skill 已不可用/)
    first.state.skill.value = 's'; assert.equal(first.state.draftNotice.value, '')
    assert.equal(first.state.canSend.value, true)
  } finally { first.close() }
  local.set(key, '{broken')
  const next = mount(f.api); await flush()
  try { assert.match(next.state.draftNotice.value, /无法恢复/); next.state.text.value = '重新填写'; assert.equal(next.state.draftNotice.value, '') } finally { next.close() }
})

test('同会话最新目录关闭所选Skill立即禁发，草稿附件保留，重新开启或清空后可发', async () => {
  const f = fixture(), view = mount(f.api); await flush()
  try {
    view.state.text.value = '关闭后仍保留'; view.state.skill.value = 's'; view.state.add(['upload:a'])
    const original = [...f.current.skills]
    assert.equal(view.state.canSend.value, true)
    f.current.skills = []; await view.state.refresh()
    assert.equal(view.state.skill.value, 's'); assert.equal(view.state.canSend.value, false)
    assert.match(view.state.skillError.value, /已关闭或不可用/); assert.match(view.state.draftNotice.value, /Skill 已不可用/)
    await view.state.send(); assert.equal(f.sends.length, 0)
    assert.equal(view.state.text.value, '关闭后仍保留'); assert.deepEqual(view.state.attachments.value.map(a => a.id), ['upload:a'])
    f.current.skills = original; await view.state.refresh()
    assert.equal(view.state.skillError.value, ''); assert.equal(view.state.draftNotice.value, ''); assert.equal(view.state.canSend.value, true)
    f.current.skills = []; await view.state.refresh(); view.state.skill.value = ''
    assert.equal(view.state.canSend.value, true); await view.state.send(); assert.equal(f.sends[0].body.skillId, null)
  } finally { view.close() }
})

test('已提交结果未知时关闭Skill仍可用原key核实，禁止创建新的发送', async () => {
  const f = fixture(), send = f.api.send; let lost = true
  f.api.send = async (...args) => { const result = await send(...args); if (lost) throw new IdentityError(0, '响应丢失'); return result }
  const first = mount(f.api); await flush(); first.state.text.value = '已提交'; first.state.skill.value = 's'
  await first.state.send(); first.close(); f.current.skills = []
  const next = mount(f.api); await flush()
  try {
    assert.equal(next.state.canSend.value, false); assert.ok(next.state.pending.value)
    await next.state.send(); assert.equal(f.sends.length, 1)
    lost = false; await next.state.retry(); assert.equal(f.sends.length, 2); assert.deepEqual(f.sends[0], f.sends[1])
    assert.equal(next.state.pending.value, undefined)
  } finally { next.close() }
})

test('批量顺序移除：中途失败继续处理，锁定重复操作，保留历史/草稿，未完成可重试', async () => {
  const f = fixture(), remove = f.api.removeMaterial
  let release!: () => void, fail = true
  f.api.removeMaterial = async (task, id) => {
    if (id === 'upload:a') await new Promise<void>(resolve => { release = resolve })
    if (id === 'upload:b' && fail) throw new IdentityError(500, '暂时失败')
    return remove(task, id)
  }
  const view = mount(f.api); await flush(); view.state.add(['upload:a']); view.state.text.value = '不能丢'
  try {
    const running = view.state.removeMaterials(['upload:a', 'upload:b', 'upload:c', 'upload:a'])
    assert.equal(view.state.removingMaterials.value, true); assert.equal(view.state.locked.value, true)
    assert.equal(await view.state.removeMaterials(['upload:a']), undefined); release()
    assert.deepEqual(await running, { removed: 2, remaining: 1 }); assert.deepEqual(f.calls, ['upload:a', 'upload:c'])
    assert.deepEqual(view.state.data.value?.materials.map(a => a.id), ['upload:b']); assert.equal(view.state.attachments.value[0].id, 'upload:a'); assert.equal(view.state.text.value, '不能丢')
    fail = false; assert.deepEqual(await view.state.removeMaterials(['upload:b']), { removed: 1, remaining: 0 })
    await view.state.refresh(); assert.equal(view.state.data.value?.materials.length, 0)
  } finally { view.close() }
})

test('批量遇权限丢失停止后续请求，已完成任务拒绝移除', async () => {
  const f = fixture(); let calls = 0
  f.api.removeMaterial = async () => { calls++; throw new IdentityError(403, '无权限') }
  const view = mount(f.api); await flush()
  try { assert.deepEqual(await view.state.removeMaterials(['upload:a', 'upload:b']), { removed: 0, remaining: 2 }); assert.equal(calls, 1); assert.equal(view.failures.length, 1) } finally { view.close() }
  f.current.completed = true
  const completed = mount(f.api); await flush(); await completed.state.removeMaterials(['upload:a']); assert.equal(calls, 1); completed.close()
})
