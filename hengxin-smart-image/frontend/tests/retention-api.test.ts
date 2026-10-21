import test from 'node:test'
import assert from 'node:assert/strict'
import { createRetentionApi, isRetentionSummary, isRetentionRow, isRetentionRecords } from '../src/api/retention'
import { identity } from '../src/api/hengxin/identity'
import { safeReturnPath } from '../src/api/hengxin/session'
import { routeModules } from '../src/router/modules'
import { apiWorkspaceRedirect } from '../src/router/business-route-access'
import { summary, row, records } from './retention-fixtures'

test('清理合同完整校验 nullable、枚举、计数、时区和详情来源', () => {
  assert.ok(isRetentionSummary(summary())); assert.ok(isRetentionRow(row())); assert.ok(isRetentionRecords(records()))
  assert.ok(isRetentionSummary({ ...summary(), counts: { ...summary().counts, retry: null } }))
  for (const counts of [{ ...summary().counts, retry: -1 }, { ...summary().counts, historyToday: undefined }, { ...summary().counts, retry: '0' }]) assert.equal(isRetentionSummary({ ...summary(), counts }), false)
  assert.equal(isRetentionSummary({ ...summary(), service: { ...summary().service, state: 'ready' } }), false)
  assert.equal(isRetentionSummary({ ...summary(), checkedAt: '2026-10-21 15:00:00' }), false)
  for (const patch of [{ detailTab: undefined }, { result: 'done' }, { dueAt: null }, { objectsPending: -1 }, { taskDeleted: undefined }]) assert.equal(isRetentionRow({ ...row(), ...patch }), false)
  assert.equal(isRetentionRecords({ ...records(), pageSize: 101 }), false)
})
test('清理 GET 编码筛选/分页并沿用 identity epoch；旧身份响应不可接受', async () => {
  const urls: string[] = []
  const api = createRetentionApi('/api/v1', async (input, init) => {
    urls.push(String(input)); assert.equal(init?.method, 'GET'); assert.equal(init?.credentials, 'include')
    return new Response(JSON.stringify(String(input).includes('/records/') ? row() : records()), { headers: { 'content-type': 'application/json' } })
  })
  await api.records({ tab: 'pending', keyword: '名称 & 编号', kind: '', result: 'retry', page: 2, pageSize: 50, dateFrom: '2026-10-20', dateTo: '2026-10-21' })
  const q = new URL(urls[0], 'https://test.invalid').searchParams
  assert.equal(q.get('keyword'), '名称 & 编号'); assert.equal(q.has('kind'), false); assert.equal(q.get('dateFrom'), '2026-10-20'); assert.equal(q.get('page'), '2')
  await api.detail('a/b', 'history'); assert.match(urls[1], /a%2Fb\?tab=history$/)
  let resolve!: (response: Response) => void
  const pending = createRetentionApi('/api', () => new Promise(done => { resolve = done })).summary()
  identity.advance('changed')
  resolve(new Response(JSON.stringify(summary()), { headers: { 'content-type': 'application/json' } }))
  await assert.rejects(pending, { code: 'STALE_IDENTITY' })
})
test('服务失败与不完整数据不伪造成功；导航仅管理角色且登录回跳有效', async () => {
  await assert.rejects(createRetentionApi('/api', async () => new Response('{}', { status: 503 })).summary(), { status: 503 })
  await assert.rejects(createRetentionApi('/api', async () => new Response('{}', { headers: { 'content-type': 'application/json' } })).summary(), { code: 'INVALID_RESPONSE' })
  const route = routeModules.find(r => r.path === '/management')!.children!.find(r => r.path === 'retention')!
  assert.deepEqual(route.meta.roles, ['super_admin', 'design_manager']); assert.equal(route.component, '/hengxin/admin/retention')
  assert.equal(safeReturnPath('/management/retention?tab=pending'), '/management/retention?tab=pending')
  for (const role of ['operator', 'designer']) assert.equal(apiWorkspaceRedirect('/management/retention', [role]), '/api-image-edits/create')
})
