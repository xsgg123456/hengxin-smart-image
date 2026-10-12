import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createTasksApi, createRequestKeys, isTaskDetail, emptyTaskDraft, validateDraft, cleanDraft, type TaskDetail } from '../src/api/overseas/tasks'
const task: TaskDetail = { ...emptyTaskDraft(), name: '真实任务', skus: [{ code: 'SKU-A' }], id: 'task/1', version: 1, status: 'created', createdAt: '2026-10-12', updatedAt: '2026-10-12', createdBy: { id: 'o', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: ['task.read'], events: [{ id: 'e', kind: 'task.created', actorId: 'o', actorName: '运营', title: '图需已保存', at: '2026-10-12', beforeDesignerId: null, afterDesignerId: 'd', version: 1 }] }
const json = (value: unknown) => new Response(JSON.stringify(value))
test('海外任务API严格字段、幂等头、分页参数与编码路径', async () => {
  const calls: { url: string; options?: RequestInit }[] = []
  const api = createTasksApi(async (url, options) => { calls.push({ url: String(url), options }); return json(String(url).includes('?') ? { items: [task], total: 21, page: 2, pageSize: 20 } : task) })
  const draft = { ...emptyTaskDraft(), name: '  图需  ', designerId: 'd', createdBy: '伪造', files: [] }
  await api.create(draft, 'stable-key'); await api.assign('task/1', 'd2', 1, 'assign-key')
  await api.list({ search: 'SKU-A', scope: 'mine', status: 'created', page: 2, pageSize: 20 })
  assert.equal(calls[0].options?.credentials, 'include')
  assert.equal((calls[0].options?.headers as Record<string, string>)['Idempotency-Key'], 'stable-key')
  assert.equal((calls[0].options?.headers as Record<string, string>)['X-HX-Request'], '1')
  assert.deepEqual(JSON.parse(String(calls[0].options?.body)), cleanDraft(draft))
  assert.equal(calls[1].url, '/api/overseas/v1/tasks/task%2F1/assignment')
  assert.equal(calls[1].options?.method, 'PATCH')
  assert.deepEqual(JSON.parse(String(calls[1].options?.body)), { designerId: 'd2', version: 1 })
  assert.match(calls[2].url, /search=SKU-A&scope=mine&status=created&page=2&pageSize=20/)
})
test('失败请求相同内容重试使用同key，改内容新key，成功清理', () => {
  let seq = 0; const keys = createRequestKeys(() => String(++seq))
  assert.equal(keys.for({ a: 1 }), keys.for({ a: 1 })); assert.equal(keys.for({ a: 2 }), '2')
  assert.equal(keys.for({ a: 1 }), '1'); keys.clear(); assert.equal(keys.for({ a: 1 }), '3')
})
test('必选设计、多SKU、空白与重复校验，不接受假详情', () => {
  const draft = { ...emptyTaskDraft(), name: '任务', productName: '品名', brand: '品牌', market: '美国', designerId: 'd', skus: [{ code: 'A' }, { code: 'B' }] }
  assert.doesNotThrow(() => validateDraft(draft))
  assert.throws(() => validateDraft({ ...draft, designerId: '' }), /指定设计/)
  assert.throws(() => validateDraft({ ...draft, skus: [{ code: 'A' }, { code: ' a ' }] }), /重复/)
  assert.throws(() => validateDraft({ ...draft, skus: [{ code: ' ' }] }), /SKU/)
  assert.equal(isTaskDetail(task), true)
  for (const value of [{ ...task, version: 0 }, { ...task, capabilities: null }, { ...task, events: [{}] }, { ...task, designer: { ...task.designer, eligible: undefined } }]) assert.equal(isTaskDetail(value), false)
})
