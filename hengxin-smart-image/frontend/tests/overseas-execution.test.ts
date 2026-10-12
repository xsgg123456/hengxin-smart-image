import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createExecutionApi, isExecutionJob, isExecutionEvents } from '../src/api/overseas/execution'
const job = { id: 'j/1', taskId: 't/1', kind: 'analysis', status: 'queued', version: 1, error: null, createdAt: '2026-10-12', startedAt: null, completedAt: null }
const event = { id: 3, jobId: 'j/1', status: 'queued', message: '等待执行', createdAt: '2026-10-12' }
test('执行契约拒绝未知状态、无版本和乱序重复游标', () => {
  assert.equal(isExecutionJob(job), true)
  for (const value of [{ ...job, status: 'done' }, { ...job, version: 0 }, { ...job, kind: 'other' }, { ...job, startedAt: undefined }]) assert.equal(isExecutionJob(value), false)
  assert.equal(isExecutionEvents({ items: [event], cursor: 3 }), true)
  for (const value of [{ items: [event, event], cursor: 3 }, { items: [event], cursor: 4 }, { items: [event], cursor: 2 }]) assert.equal(isExecutionEvents(value), false)
})
test('执行API隔离路径、会话、禁缓存、游标及取消版本写保护', async () => {
  const calls: { url: string; options?: RequestInit }[] = []
  const api = createExecutionApi(async (url, options) => {
    calls.push({ url: String(url), options })
    return new Response(JSON.stringify(String(url).includes('execution-events') ? { items: [event], cursor: 3 } : String(url).endsWith('/cancel') ? job : { items: [job] }))
  })
  await api.jobs('t/1'); await api.events('t/1', 2); await api.cancel('j/1', 1)
  assert.equal(calls[0].url, '/api/overseas/v1/tasks/t%2F1/jobs')
  assert.equal(calls[1].url, '/api/overseas/v1/tasks/t%2F1/execution-events?after=2')
  assert.equal(calls[2].url, '/api/overseas/v1/jobs/j%2F1/cancel')
  assert.deepEqual(JSON.parse(String(calls[2].options?.body)), { version: 1 })
  assert.equal((calls[2].options?.headers as Record<string, string>)['X-HX-Request'], '1')
  for (const call of calls) { assert.equal(call.options?.credentials, 'include'); assert.equal(call.options?.cache, 'no-store') }
})
test('拒绝跨任务作业、游标回退/跳空与401/403/409；取消订阅读取', async () => {
  await assert.rejects(createExecutionApi(async () => new Response(JSON.stringify({ items: [job] }))).jobs('other'))
  for (const value of [{ items: [event], cursor: 3 }, { items: [], cursor: 5 }]) await assert.rejects(createExecutionApi(async () => new Response(JSON.stringify(value))).events('t/1', 4))
  for (const status of [401, 403, 409]) await assert.rejects(createExecutionApi(async () => new Response('{}', { status })).cancel('j/1', 1), (e: unknown) => typeof e === 'object' && e !== null && 'status' in e && e.status === status)
  const controller = new AbortController()
  const api = createExecutionApi(async (_url, options) => { assert.ok(options?.signal); controller.abort(); assert.equal(options.signal.aborted, true); throw Error('aborted') })
  await assert.rejects(api.jobs('t/1', controller.signal))
})
