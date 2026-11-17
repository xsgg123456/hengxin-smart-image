import test from 'node:test'
import assert from 'node:assert/strict'
import { effectScope } from 'vue'
import { createWorkspaceSessionsApi, isSessionDetail, readManagedAsset, type SessionDetail, type SessionList } from '../src/api/hengxin/workspace-sessions'
import { IdentityError } from '../src/api/identity/request'
import { useMonitor } from '../src/views/hengxin/admin/workspace-sessions/use-monitor'
import { identity } from '../src/api/hengxin/identity'

const stamp = '2026-11-17T01:00:00Z'
const summary = (id: string) => ({ id, name: id, ownerId: 'owner', ownerName: '成员', workspace: 'camera' as const, status: 'running' as const, turnCount: 1, createdAt: stamp, updatedAt: stamp, activeTurnId: 'turn', version: 1 })
const detail = (id: string): SessionDetail => ({ session: summary(id), siblingSessions: [summary(id)], workspace: { taskId: 'camera', taskVersion: 1, conversationId: id, archiveId: null, completed: false, reopened: false, fixedSkillReady: false, activeTurnId: null, turns: [], skills: [], materials: [] } })
const listing = (id: string): SessionList => ({ items: [summary(id)], total: 1, page: 1, pageSize: 10, members: [{ id: 'owner', name: '成员' }], counters: { total: 1, running: 1, queued: 0, succeeded: 0, failed: 0, empty: 0, cancelled: 0, unknown: 0 } })
const settle = () => new Promise(resolve => setTimeout(resolve, 0))
const entry = (id: number, text: string) => ({ id, turnId: 'turn', itemId: 'item', kind: 'tool' as const, text, state: 'running' as const, createdAt: stamp })

test('管理接口仅GET、查询参数编码且拒绝个人/跨会话/海外文件地址', async () => {
  const calls: { url: string; method?: string }[] = []
  const api = createWorkspaceSessionsApi(async (url, options) => { calls.push({ url: String(url), method: options?.method }); return new Response(JSON.stringify(listing('a'))) })
  await api.list({ ownerId: 'owner', workspace: 'camera', status: '', search: '名字 & 内容', page: 2, pageSize: 10 })
  assert.equal(calls[0].method, 'GET'); assert.equal(new URL(calls[0].url, 'http://local').searchParams.get('search'), '名字 & 内容')
  const value = detail('a')
  value.workspace.materials = [{ id: 'upload:file', name: '附件', contentType: 'text/plain', sizeBytes: 1, source: 'upload', url: '/api/v1/management/domestic-studio/sessions/a/files/file/content' }]
  assert.equal(isSessionDetail(value, 'a'), true)
  value.workspace.materials[0].url = '/api/v1/management/domestic-studio/sessions/b/files/file/content'
  assert.equal(isSessionDetail(value, 'a'), false)
  await assert.rejects(readManagedAsset('/api/overseas/v1/materials/foreign/content', new AbortController().signal), /文件地址无效/)
})

test('切换与筛选拒绝迟到响应、返回保留筛选', async () => {
  let release: ((value: SessionDetail) => void) | undefined
  let releaseList: ((value: SessionList) => void) | undefined
  const scope = effectScope()
  const state = scope.run(() => useMonitor({
    detail: async id => id === 'a' ? new Promise(resolve => { release = resolve }) : detail(id),
    transcript: async () => ({ items: [], cursor: 0, hasMore: false }),
    list: async filters => filters.search === 'old' ? new Promise(resolve => { releaseList = resolve }) : listing(filters.search)
  }))!
  try {
    state.select('a'); state.select('b'); await settle(); release?.(detail('a')); await settle()
    assert.equal(state.detail.value?.session.id, 'b')
    state.filters.search = 'old'; state.select(''); await settle()
    state.filters.search = 'new'; state.filterChanged(); await settle(); releaseList?.(listing('old')); await settle()
    assert.equal(state.list.value?.items[0].id, 'new')
    state.select('b'); await settle(); state.select(''); await settle()
    assert.equal(state.filters.search, 'new')
  } finally { scope.stop() }
})

test('增量分页全量读完、过程项替换、断线保留快照、403清空所有敏感状态', async () => {
  let failure = 0, revision = 0
  const scope = effectScope()
  const state = scope.run(() => useMonitor({
    detail: async id => { if (failure) throw new IdentityError(failure, '断线'); return detail(id) },
    list: async () => listing('a'),
    transcript: async (_id, after) => after === 0 ? { items: [entry(1, '初始过程')], cursor: 1, hasMore: true }
      : after === 1 ? { items: [entry(2, '完整过程')], cursor: 2, hasMore: false }
        : { items: revision ? [entry(3, '最新过程')] : [], cursor: revision ? 3 : 2, hasMore: false }
  }))!
  try {
    state.select('a'); await settle()
    assert.equal(state.transcript.value.length, 1); assert.equal(state.transcript.value[0].text, '完整过程')
    revision = 1; await state.refresh(); assert.equal(state.transcript.value[0].text, '最新过程')
    const success = state.lastSuccess.value; failure = 503; await state.refresh()
    assert.equal(state.detail.value?.session.id, 'a'); assert.equal(state.lastSuccess.value, success); assert.ok(state.error.value)
    failure = 403; await state.refresh()
    assert.equal(state.denied.value, true); assert.equal(state.detail.value, undefined); assert.equal(state.list.value, undefined)
    assert.equal(state.transcript.value.length, 0); assert.equal(state.lastSuccess.value, ''); assert.equal(state.autoSync.value, false)
    failure = 0; await state.refresh(); assert.equal(state.detail.value, undefined)
  } finally { scope.stop() }
})

test('源会话删除清空详情且不可留下已删除消息', async () => {
  let deleted = false
  const scope = effectScope()
  const state = scope.run(() => useMonitor({ detail: async id => { if (deleted) throw new IdentityError(404, '已删除'); return detail(id) }, list: async () => listing('a'), transcript: async () => ({ items: [entry(1, '消息')], cursor: 1, hasMore: false }) }))!
  try { state.select('a'); await settle(); deleted = true; await state.refresh(); assert.equal(state.detail.value, undefined); assert.deepEqual(state.transcript.value, []); assert.match(state.error.value, /已删除/) }
  finally { scope.stop() }
})

test('下载真实受限地址，403传播给撤权处理且不接受重定向', async () => {
  let options: RequestInit | undefined
  await assert.rejects(readManagedAsset('/api/v1/management/domestic-studio/sessions/a/files/f/content', new AbortController().signal, async (_url, init) => { options = init; return new Response('', { status: 403 }) }), (error: unknown) => error instanceof IdentityError && error.status === 403)
  assert.equal(options?.cache, 'no-store'); assert.equal(options?.redirect, 'error')
  let thumbnailUrl = ''
  await readManagedAsset('/api/v1/management/domestic-studio/sessions/a/pictures/p/content', new AbortController().signal, async url => { thumbnailUrl = String(url); return new Response('image') }, true)
  assert.equal(new URL(thumbnailUrl, 'http://local').searchParams.get('thumbnail'), 'true')
})

test('自动同步暂停时身份变化仍立即清敏感数据', async () => {
  const scope = effectScope()
  const state = scope.run(() => useMonitor({ detail: async id => detail(id), list: async () => listing('a'), transcript: async () => ({ items: [], cursor: 0, hasMore: false }) }))!
  try { state.select('a'); await settle(); state.autoSync.value = false; identity.advance('changed'); assert.equal(state.denied.value, true); assert.equal(state.detail.value, undefined) }
  finally { scope.stop() }
})
