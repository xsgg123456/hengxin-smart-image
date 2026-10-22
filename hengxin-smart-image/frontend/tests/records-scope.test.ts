import test from 'node:test'
import assert from 'node:assert/strict'
import { recordsDateRange } from '../src/views/hengxin/api-image-edits/records-filters'
import { createApiImageClient } from '../src/api/api-image-edits'
import { page, creators } from '../src/api/api-image-edits-validate'

test('日期快捷范围按北京时间自然日且含今天，不随浏览器时区变化', () => {
  const now = new Date('2026-10-21T16:00:01Z')
  assert.deepEqual(recordsDateRange('today', null, now), { dateFrom: '2026-10-22', dateTo: '2026-10-22' })
  assert.deepEqual(recordsDateRange('week', null, now), { dateFrom: '2026-10-16', dateTo: '2026-10-22' })
  assert.deepEqual(recordsDateRange('month', null, now), { dateFrom: '2026-09-23', dateTo: '2026-10-22' })
  assert.deepEqual(recordsDateRange('week', null, new Date('2026-01-01T00:00:00Z')), { dateFrom: '2025-12-26', dateTo: '2026-01-01' })
  assert.deepEqual(recordsDateRange('custom', ['2026-10-01', '2026-10-22'], now), { dateFrom: '2026-10-01', dateTo: '2026-10-22' })
  assert.deepEqual(recordsDateRange('custom', null, now), {})
  assert.deepEqual(recordsDateRange('all', null, now), {})
})

test('正式列表传默认本人、指定人员与日期，不发送undefined，不调用管理用户接口', async () => {
  const calls: string[] = []
  const client = createApiImageClient('/api/v1', async (url, init) => {
    calls.push(String(url)); assert.equal(init?.credentials, 'include')
    return new Response(JSON.stringify(String(url).endsWith('/creators') ? { items: [{ id: 'person', name: '同名用户' }] } : { items: [], total: 0, page: 1, pageSize: 20, stats: { tasks: 0, pendingTasks: 0, successImages: 0, failedImages: 0 } }), { headers: { 'content-type': 'application/json' } })
  })
  await client.list({ page: 1, pageSize: 20, search: '', status: '' })
  assert.equal(new URL(calls[0], 'http://localhost').searchParams.get('scope'), 'mine')
  await client.list({ page: 1, pageSize: 20, search: '红米 & 主图', status: 'succeeded', scope: 'all', creatorId: 'person', dateFrom: '2026-10-22', dateTo: '2026-10-22' })
  const query = new URL(calls[1], 'http://localhost').searchParams
  assert.equal(query.get('creatorId'), 'person'); assert.equal(query.get('search'), '红米 & 主图')
  assert.equal(query.get('dateFrom'), '2026-10-22'); assert.equal(query.get('scope'), 'all')
  assert(!calls.join('').includes('undefined'))
  assert.equal((await client.creators()).items[0].id, 'person')
  assert.equal(calls[2], '/api/v1/api-image-edits/creators')
})

test('拒绝损坏的统计、重复人员ID，历史无统计响应保持未知而不伪造零', () => {
  const value = { items: [], total: 25, page: 1, pageSize: 20, stats: { tasks: 25, pendingTasks: 3, successImages: 100, failedImages: 2 } }
  assert(page(value))
  assert(!page({ ...value, stats: { ...value.stats, tasks: 20 } }))
  assert(!page({ ...value, stats: { ...value.stats, successImages: -1 } }))
  assert(!page({ ...value, stats: { ...value.stats, pendingTasks: 26 } }))
  assert(page({ ...value, stats: undefined }))
  assert(creators({ items: [{ id: 'a', name: '同名' }, { id: 'b', name: '同名' }] }))
  assert(!creators({ items: [{ id: 'a', name: '同名' }, { id: 'a', name: '重复' }] }))
})
