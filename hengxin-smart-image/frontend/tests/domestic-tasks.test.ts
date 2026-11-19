import test from 'node:test'
import assert from 'node:assert/strict'
import { effectScope, reactive } from 'vue'
import { createDomesticTasksApi, isManagedTaskDetail, type DomesticTask, type TaskList } from '../src/api/hengxin/domestic-tasks'
import { createStudioApi, isDomesticAsset, type Studio } from '../src/api/shared/studio'
import { createStudioOutputsApi } from '../src/api/shared/studio-outputs'
import { IdentityError } from '../src/api/identity/request'
import { domesticWorkspaces } from '../src/api/hengxin/domestic-workspaces'
import { safeReturnPath } from '../src/api/hengxin/session'
import { routeModules } from '../src/router/modules'
import { useTasks } from '../src/views/hengxin/domestic-studio/use-tasks'
import { restoreTaskStorage } from '../src/views/hengxin/domestic-studio/task-storage'
import { composerDraftKey } from '../src/views/shared/studio/studio-composer-draft'
import { pendingKey } from '../src/views/shared/studio/studio-pending'
import { identity } from '../src/api/hengxin/identity'
import { local, session, row, flush, deferred, fixture } from './studio-sessions-fixture'

const stamp = '2026-11-17T01:00:00Z'
const task = (id = 'task-a'): DomesticTask => ({ id, name: `设计任务${id}`, workspace: 'camera', ownerId: 'owner', ownerName: '成员', version: 1, completed: false, conversationCount: 0, activeConversationCount: 0, createdAt: stamp, updatedAt: stamp, deletionStatus: null, deletionError: null })
const listing = (id = 'task-a'): TaskList => ({ items: [task(id)], total: 1, page: 1, pageSize: 20, counters: { total: 1, active: 1, completed: 0 } })
const studio = (): Studio => ({ taskId: 'task-a', taskVersion: 1, archiveId: null, reopened: false, completed: false, turns: [], materials: [], skills: [], fixedSkillReady: false, activeTurnId: null, conversationId: null, conversations: [], activeConversationCount: 0, maxConversations: 10 })
function fakeApi(overrides: Partial<ReturnType<typeof createDomesticTasksApi>> = {}) {
  return { list: async () => listing(), detail: async (id: string) => ({ task: task(id), sessions: [] }), managedDetail: async (id: string) => ({ task: task(id), sessions: [] }),
    create: async () => task(), update: async () => task(), remove: async () => ({ status: 'deleting' as const }), deletion: async () => ({ status: 'deleted' as const }), ...overrides }
}

test('任务客户端使用真实作用域、分页筛选及幂等键，管理只读详情拒绝跨任务会话', async () => {
  const calls: { url: string; options?: RequestInit }[] = []
  const api = createDomesticTasksApi(async (url, options) => { calls.push({ url: String(url), options }); return Response.json(options?.method === 'GET' ? listing() : task()) })
  await api.list({ workspace: 'camera', ownerId: '', search: '名字 & 内容', status: 'active', page: 2, pageSize: 20 })
  await api.create({ workspace: 'camera', name: '新任务' }, 'key-create')
  await api.update('task-a', { version: 1, completed: true }, 'key-update')
  assert.equal(new URL(calls[0].url, 'http://local').searchParams.get('search'), '名字 & 内容')
  assert.equal(new URL(calls[0].url, 'http://local').searchParams.get('workspace'), 'camera')
  assert.equal(calls[1].url, '/api/v1/domestic-studio/tasks')
  assert.equal((calls[1].options?.headers as Record<string, string>)['Idempotency-Key'], 'key-create')
  assert.equal(calls[2].options?.method, 'PATCH')
  const value = { task: task(), sessions: [{ ...row('s'), ownerId: 'owner', ownerName: '成员', workspace: 'camera', taskId: 'task-a', taskName: '设计任务' }] }
  assert.equal(isManagedTaskDetail(value, 'task-a'), true)
  value.sessions[0].taskId = 'other'; assert.equal(isManagedTaskDetail(value, 'task-a'), false)
})

test('任务工作台和取回严格使用task URL，旧业务和海外URL不能串入任务附件', async () => {
  const urls: string[] = []
  const api = createStudioApi(async url => { urls.push(String(url)); return Response.json(studio()) }, 'domestic-task')
  await api.get('task-a')
  assert.equal(urls[0], '/api/v1/domestic-studio/tasks/task-a/studio')
  const asset = { id: 'upload:f', name: 'f', contentType: 'text/plain', sizeBytes: 1, source: 'upload', url: '/api/v1/domestic-studio/tasks/task-a/studio/files/f/content' }
  assert.equal(isDomesticAsset(asset, 'task-a'), true)
  assert.equal(isDomesticAsset(asset, 'task-b'), false)
  asset.url = '/api/v1/domestic-studio/workspaces/camera/files/f/content'
  assert.equal(isDomesticAsset(asset, 'task-a'), false)
  const recovery = createStudioOutputsApi(async url => { urls.push(String(url)); return Response.json({ items: [], busy: false }) }, 'domestic-task')
  await recovery.list('task-a', 'session-a')
  assert.equal(urls[1], '/api/v1/domestic-studio/tasks/task-a/studio/conversations/session-a/recoverable-files')
})

test('任务切换与筛选的迟到响应不能覆盖新任务，返回保留筛选', async () => {
  session.clear()
  const held = deferred<DomesticTask>(), oldList = deferred<TaskList>()
  const context = reactive({ actor: 'owner', workspace: 'camera', management: false, id: 'task-a' })
  const scope = effectScope(), state = scope.run(() => useTasks(() => context, () => {}, () => {}, fakeApi({ detail: async id => ({ task: id === 'task-a' ? await held.promise : task(id), sessions: [] }), list: async filters => filters.search === 'old' ? oldList.promise : listing(filters.search) })))!
  try {
    context.id = 'task-b'; await flush(); held.resolve(task('task-a')); await flush()
    assert.equal(state.task.value?.id, 'task-b')
    context.id = ''; state.filters.search = 'old'; await flush()
    state.filters.search = 'new'; await flush(); oldList.resolve(listing('old')); await flush()
    assert.equal(state.list.value?.items[0].id, 'new')
    context.id = 'task-b'; await flush(); context.id = ''; await flush()
    assert.equal(state.filters.search, 'new')
  } finally { scope.stop() }
})

test('未知创建保留原请求和键，阻止重复创建，刷新后以原键核实', async () => {
  session.clear()
  const calls: { name: string; key: string }[] = [], entered: string[] = []
  const context = { actor: 'owner', workspace: 'camera', management: false, id: '' }
  const api = fakeApi({ create: async (body, key) => { calls.push({ name: body.name, key }); if (calls.length === 1) throw new IdentityError(503, '断线'); return task() } })
  const scope = effectScope(), state = scope.run(() => useTasks(() => context, value => entered.push(value.id), () => {}, api))!
  await flush(); assert.equal(await state.create('方案任务'), false)
  assert.equal(state.pending.value?.kind, 'create')
  await state.create('另一任务'); assert.equal(calls.length, 1)
  scope.stop()
  const nextScope = effectScope(), next = nextScope.run(() => useTasks(() => context, value => entered.push(value.id), () => {}, api))!
  try { await next.retry(); assert.deepEqual(calls[1], calls[0]); assert.equal(next.pending.value, undefined); assert.deepEqual(entered, ['task-a']) }
  finally { nextScope.stop() }
})

test('任务删除只在实际清理回执deleted后返回，删除失败保留任务和错误', async () => {
  session.clear(); let removed = 0, receipt: 'deleting' | 'delete_failed' | 'deleted' = 'delete_failed'
  const deleting = { ...task(), deletionStatus: 'delete_failed' as const, deletionError: '文件暂不可用' }
  const scope = effectScope(), state = scope.run(() => useTasks(() => ({ actor: 'owner', workspace: 'camera', management: false, id: 'task-a' }), () => {}, () => { removed++ }, fakeApi({ detail: async () => ({ task: deleting, sessions: [] }), deletion: async () => ({ status: receipt }), remove: async () => ({ status: 'delete_failed', error: '文件暂不可用' }) })))!
  try { await flush(); await state.remove(deleting); await flush(); assert.equal(removed, 0); assert.equal(state.task.value?.deletionError, '文件暂不可用'); receipt = 'deleted'; await state.refresh(); assert.equal(removed, 1) }
  finally { scope.stop() }
})

for (const management of [false, true]) for (const id of ['', 'task-a']) {
  test(`${management ? '管理' : '个人'}任务${id ? '详情' : '列表'}切页不撤权，真实身份失效仍清空`, async () => {
    session.clear()
    const scope = effectScope(), state = scope.run(() => useTasks(() => ({ actor: 'owner', workspace: 'camera', management, id }), () => {}, () => {}, fakeApi()))!
    try {
      await flush(); state.filters.search = '保留筛选'; await flush()
      const snapshot = id ? state.task.value : state.list.value
      assert.ok(snapshot)
      for (const auto of [false, true]) {
        state.autoSync.value = auto; await flush()
        identity.advance('suspended')
        assert.equal(state.denied.value, false); assert.equal(state.error.value, '')
        assert.equal(state.autoSync.value, auto); assert.equal(state.filters.search, '保留筛选')
        assert.ok(id ? state.task.value : state.list.value)
        await state.refresh(); assert.equal(state.denied.value, false)
      }
      identity.advance('invalid')
      assert.equal(state.denied.value, true); assert.equal(state.autoSync.value, false)
      assert.equal(state.task.value, undefined); assert.equal(state.list.value, undefined); assert.equal(state.managed.value, undefined)
    } finally { scope.stop() }
  })
}

test('管理任务不能写，暂停同步时撤权也立即清空任务、列表和会话内容', async () => {
  session.clear(); let writes = 0
  const scope = effectScope(), state = scope.run(() => useTasks(() => ({ actor: 'admin', workspace: '', management: true, id: 'task-a' }), () => {}, () => {}, fakeApi({ create: async () => { writes++; return task() } })))!
  try { await flush(); assert.ok(state.task.value); await state.create('拒绝'); assert.equal(writes, 0); state.autoSync.value = false; identity.advance('changed'); assert.equal(state.denied.value, true); assert.equal(state.task.value, undefined); assert.equal(state.managed.value, undefined); assert.equal(state.list.value, undefined) }
  finally { scope.stop() }
})

for (const management of [false, true]) for (const id of ['', 'task-a']) {
  test(`${management ? '管理' : '个人'}任务${id ? '详情' : '列表'}自动同步静默且去重，手动刷新可替换在途同步`, async t => {
    t.mock.timers.enable({ apis: ['setInterval'] }); session.clear()
    const requests: { value: ReturnType<typeof deferred<any>>; signal?: AbortSignal }[] = []
    const request = (signal?: AbortSignal) => { const value = deferred<any>(); requests.push({ value, signal }); return value.promise }
    const response = (name: string) => id ? { task: { ...task(id), name }, sessions: [] } : { ...listing(), items: [{ ...task(), name }] }
    const scope = effectScope(), state = scope.run(() => useTasks(() => ({ actor: 'owner', workspace: management ? '' : 'camera', management, id }), () => {}, () => {}, fakeApi({ list: async (_filters, _management, signal) => request(signal), detail: async (_id, _workspace, signal) => request(signal), managedDetail: async (_id, signal) => request(signal) })))!
    const name = () => id ? state.task.value?.name : state.list.value?.items[0].name
    try {
      assert.equal(state.loading.value, true)
      requests[0].value.resolve(response('初次')); await flush()
      t.mock.timers.tick(3000); assert.equal(requests.length, 2); assert.equal(state.loading.value, false); assert.equal(name(), '初次')
      t.mock.timers.tick(6000); assert.equal(requests.length, 2); assert.equal(requests[1].signal?.aborted, false)
      requests[1].value.resolve(response('后台更新')); await flush(); assert.equal(name(), '后台更新')
      t.mock.timers.tick(3000); assert.equal(requests.length, 3)
      const manual = state.refresh(); assert.equal(state.loading.value, true); assert.equal(requests[2].signal?.aborted, true)
      requests[2].value.resolve(response('迟到')); await flush(); assert.equal(name(), '后台更新'); assert.equal(state.loading.value, true)
      requests[3].value.resolve(response('手动更新')); await manual; assert.equal(name(), '手动更新'); assert.equal(state.loading.value, false)
      state.autoSync.value = false; t.mock.timers.tick(3000); assert.equal(requests.length, 4)
    } finally { scope.stop() }
  })
}

test('后台任务同步错误保留快照，筛选有反馈，后台撤权立即清空且阻止后续同步', async t => {
  t.mock.timers.enable({ apis: ['setInterval'] }); session.clear()
  let failure = 0, count = 0
  const scope = effectScope(), state = scope.run(() => useTasks(() => ({ actor: 'admin', workspace: '', management: true, id: '' }), () => {}, () => {}, fakeApi({ list: async () => { count++; if (failure) throw new IdentityError(failure, '同步异常'); return listing() } })))!
  try {
    await flush(); const success = state.lastSuccess.value
    failure = 503; t.mock.timers.tick(3000); await flush()
    assert.ok(state.list.value); assert.equal(state.lastSuccess.value, success); assert.equal(state.error.value, '同步异常'); assert.equal(state.loading.value, false)
    failure = 0; state.filters.search = '新筛选'; await Promise.resolve(); assert.equal(state.loading.value, true); await flush(); assert.equal(state.error.value, '')
    failure = 403; t.mock.timers.tick(3000); await flush()
    assert.equal(state.list.value, undefined); assert.equal(state.denied.value, true); assert.equal(state.autoSync.value, false)
    const previous = count; t.mock.timers.tick(6000); assert.equal(count, previous)
  } finally { scope.stop() }
})

test('历史草稿只迁移已确认所属会话，保留内容、参考关系和原请求键，不覆盖新草稿', () => {
  local.clear(); session.clear()
  const saved = { version: 1, text: '旧方案未发送要求', skill: '', attachments: [{ id: 'upload:f', name: '素材', source: 'upload', contentType: 'image/png', sizeBytes: 1, url: '/api/v1/domestic-studio/workspaces/camera/files/f/content' }], references: ['picture'], revisions: [{ pictureId: 'picture', text: '标注', marks: [] }] }
  local.set(composerDraftKey('owner', 'camera', 's'), JSON.stringify(saved))
  local.set(composerDraftKey('owner', 'camera', 'foreign'), JSON.stringify(saved))
  session.set(pendingKey('owner', 'camera', 's'), JSON.stringify({ kind: 'send', key: 'original-key', body: { conversationId: 's', text: '未确认' }, draftConversationId: 's' }))
  const value = { ...studio(), conversations: [row('s')] }
  restoreTaskStorage('owner', 'camera', value)
  const migrated = JSON.parse(local.get(composerDraftKey('owner', 'task-a', 's'))!)
  assert.equal(migrated.text, saved.text); assert.deepEqual(migrated.references, saved.references); assert.deepEqual(migrated.revisions, saved.revisions)
  assert.equal(migrated.attachments[0].url, '/api/v1/domestic-studio/tasks/task-a/studio/files/f/content')
  assert.ok(local.has(composerDraftKey('owner', 'camera', 'foreign')))
  assert.equal(JSON.parse(session.get(pendingKey('owner', 'task-a', 's'))!).key, 'original-key')
  local.set(composerDraftKey('owner', 'camera', 's'), JSON.stringify({ ...saved, text: '不能覆盖' }))
  restoreTaskStorage('owner', 'camera', value)
  assert.equal(JSON.parse(local.get(composerDraftKey('owner', 'task-a', 's'))!).text, saved.text)
  assert.ok(local.has(composerDraftKey('owner', 'camera', 's')))
})

test('零会话不隐式创建，显式新建可用；任何方案执行、上传或删除阻止任务完成', async () => {
  const f = fixture(); f.rows.splice(0)
  const view = f.mount('owner', ['task.design'], false)
  try {
    await flush(); assert.equal(f.calls.some(call => call.kind === 'create'), false); assert.equal(view.state.canNewConversation.value, true)
    await view.state.newConversation(); await flush(); assert.equal(view.state.sessions.value.length, 1); assert.equal(view.state.canMutateTask.value, true)
    view.state.uploading.value = true; assert.equal(view.state.canMutateTask.value, false); view.state.uploading.value = false
    f.rows[0].deletionStatus = 'deleting'; await view.state.refresh(); await flush(); assert.equal(view.state.canMutateTask.value, false)
  } finally { view.close() }
})

test('业务菜单按确认顺序注册入口、登录返回地址和管理详情，管理筛选携带相同标识', async () => {
  assert.deepEqual(domesticWorkspaces.map(item => item.key), [
    'general', 'camera', 'case', 'film', 'cable', 'earbud', 'accessory', 'edit', 'product', 'scene', 'phone',
  ])
  assert.equal(domesticWorkspaces.find(item => item.path === '/new-product/screen-protector')?.title, '所有膜生成')
  assert.equal(domesticWorkspaces[0].title, '新品通用生成')
  const distinctPaths = new Set(domesticWorkspaces.map(workspace => workspace.path))
  assert.equal(distinctPaths.size, domesticWorkspaces.length)
  for (const workspace of domesticWorkspaces) {
    const group = routeModules.find(menu => menu.meta.title === workspace.group)!
    const menu = group.children?.find(item => group.path + '/' + item.path === workspace.path)
    assert.equal(menu?.meta.title, workspace.title)
    assert.equal(menu?.component, '/hengxin/domestic-studio/workspace')
    assert.equal(safeReturnPath(workspace.path + '?task=task-a'), workspace.path + '?task=task-a')
    const currentTask = { ...task(), workspace: workspace.key }
    const api = createDomesticTasksApi(async url => {
      const endpoint = new URL(String(url), 'http://local')
      assert.equal(endpoint.pathname, '/api/v1/management/domestic-studio/tasks')
      assert.equal(endpoint.searchParams.get('workspace'), workspace.key)
      return Response.json({ ...listing(), items: [currentTask] })
    })
    assert.equal((await api.list({ workspace: workspace.key, ownerId: '', search: '', status: '', page: 1, pageSize: 20 }, true)).items[0].workspace, workspace.key)
    const session = { ...row('s'), ownerId: currentTask.ownerId, ownerName: currentTask.ownerName, workspace: workspace.key, taskId: currentTask.id }
    assert.equal(isManagedTaskDetail({ task: currentTask, sessions: [session] }, currentTask.id), true)
    assert.equal(isManagedTaskDetail({ task: currentTask, sessions: [{ ...session, workspace: 'other' }] }, currentTask.id), false)
  }
})

test('成员查看他人任务始终使用业务只读详情，不能修改或核实他人删除回执', async () => {
  session.clear()
  const peerTask = { ...task(), deletionStatus: 'delete_failed' as const }
  const calls: string[] = []
  const api = fakeApi({
    detail: async (id, workspace) => { calls.push(workspace + '/' + id); return { task: peerTask, sessions: [] } },
    managedDetail: async () => { throw Error('不能使用管理接口') },
    deletion: async () => { throw Error('不能查看创建人的删除回执') },
    update: async () => { throw Error('不能修改他人任务') },
    remove: async () => { throw Error('不能删除他人任务') }
  })
  const scope = effectScope(), state = scope.run(() => useTasks(() => ({ actor: 'peer', workspace: 'camera', management: false, id: peerTask.id }), () => {}, () => {}, api))!
  try {
    await flush()
    assert.equal(state.managed.value?.task.ownerId, 'owner')
    assert.equal(await state.update(peerTask, { completed: true }), false)
    assert.equal(await state.remove(peerTask), false)
    await state.refresh()
    assert.equal(state.error.value, '')
    assert.deepEqual(calls, ['camera/task-a', 'camera/task-a'])
    assert.equal(session.size, 0)
  } finally { scope.stop() }
})
