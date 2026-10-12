import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createPlansApi, isPlanContent, isPlanList } from '../src/api/overseas/plans'
const content = { skus: [{ code: 'A', pictures: [{ title: '主图', description: '描述', prompt: '完整提示词', width: 1024, height: 1024 }] }] }
const plan = { id: 'p1', taskId: 't/1', version: 1, status: 'ready', jobId: 'j1', feedback: '', content, createdAt: '2026-10-12' }
test('方案拒绝不完整、重复SKU、非法尺寸、乱序历史与伪造ready空内容', () => {
  assert.ok(isPlanContent(content)); assert.ok(isPlanList({ items: [plan], taskVersion: 2 }))
  for (const value of [null, { skus: [] }, { skus: [content.skus[0], content.skus[0]] }, { skus: [{ code: 'A', pictures: [] }] }, { skus: [{ code: 'A', pictures: [{ ...content.skus[0].pictures[0], width: 8193 }] }] }]) assert.equal(isPlanContent(value), false)
  for (const items of [[{ ...plan, content: null }], [plan, plan], [{ ...plan, status: 'bad' }], [plan, { ...plan, id: 'p2', version: 2 }]]) assert.equal(isPlanList({ items, taskVersion: 1 }), false)
  assert.ok(isPlanList({ items: [{ ...plan, status: 'failed', content: null }], taskVersion: 2 }))
})
test('方案读取隔离任务、禁缓存，写入保留版本及幂等键', async () => {
  const calls: { url: string; options?: RequestInit }[] = []
  const task = { id: 't/1', name: '', productName: '', brand: '', platform: '', market: '', remarks: '', skus: [{ code: 'A' }], status: 'analyzing', version: 3, createdAt: '', updatedAt: '', createdBy: { id: 'a', name: 'A' }, designer: { id: 'a', name: 'A', status: 'active', eligible: true }, capabilities: [], events: [] }
  const api = createPlansApi(async (url, options) => { calls.push({ url: String(url), options }); return new Response(JSON.stringify(String(url).endsWith('/plans') ? { items: [plan], taskVersion: 2 } : task)) })
  await api.list('t/1'); await api.analyze('t/1', 2, '完整意见', 'same'); await api.confirm('t/1', 'p/1', 3, 'confirm')
  assert.equal(calls[0].url, '/api/overseas/v1/tasks/t%2F1/plans')
  assert.equal(calls[2].url, '/api/overseas/v1/tasks/t%2F1/plans/p%2F1/confirm')
  assert.deepEqual(JSON.parse(String(calls[1].options?.body)), { version: 2, feedback: '完整意见' })
  for (const c of calls) { assert.equal(c.options?.cache, 'no-store'); assert.equal(c.options?.credentials, 'include') }
  assert.equal((calls[1].options?.headers as Record<string,string>)['Idempotency-Key'], 'same')
  await assert.rejects(api.list('other'))
  for (const status of [401, 403, 409, 500]) await assert.rejects(createPlansApi(async () => new Response('{}', { status })).analyze('t/1', 2, '', 'same'), (e: unknown) => !!e && typeof e === 'object' && 'status' in e && e.status === status)
})
