import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createMockService } from '../src/api/hengxin/mock'
import { createHttpService, ApiError } from '../src/api/hengxin/http'
import { sampleImages } from '../src/api/hengxin/fixtures'

const input = { mode: 'wallpaper' as const, name: '独立模拟任务', templateId: 't1', sources: sampleImages('wallpaper', 1), note: '保持边框' }
const pause = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))

test('模拟服务隔离快照与实例，空工作区无种子污染', async () => {
  const service = createMockService({ delayMs: 0 })
  const snapshot = await service.getWorkspace()
  snapshot.templates[0].name = '篡改'
  assert.notEqual((await service.getWorkspace()).templates[0].name, '篡改')
  const empty = createMockService({ empty: true, delayMs: 0 })
  assert.deepEqual(await empty.getWorkspace(), { templates: [], tasks: [], archives: [] })
})

test('提交异步受理保留输入，不匹配模板拒绝；不同任务有独立受理标识', async t => {
  const service = createMockService({ delayMs: 0, stepMs: 1000 })
  t.after(() => service.dispose())
  await assert.rejects(service.createTask({ ...input, mode: 'product' }), { code: 'VALIDATION' })
  const first = await service.createTask(input)
  const second = await service.createTask(input)
  assert.equal(first.state, '排队中')
  assert.notEqual(first.taskId, second.taskId)
  assert.notEqual(first.roundId, second.roundId)
  const task = (await service.getWorkspace()).tasks.find(task => task.id === first.taskId)!
  assert.equal(task.state, '排队中')
  assert.deepEqual(task.sources, input.sources)
  assert.equal(task.sessionId, null)
  assert.match(task.feedback[0], /保持边框/)
  await assert.rejects(service.archive(first.taskId), { code: 'CONFLICT' })
})

test('返工串行、单图版本隔离、归档快照和重复归档幂等', async t => {
  const service = createMockService({ delayMs: 0, stepMs: 5 })
  t.after(() => service.dispose())
  const taskId = 'HX0908-001'
  const archived = await service.archive(taskId)
  assert.equal((await service.archive(taskId)).id, archived.id)
  await assert.rejects(service.revise({ taskId, target: 100, note: '越界' }), { code: 'VALIDATION' })
  await service.revise({ taskId, target: 1, note: '调整第二张' })
  await assert.rejects(service.revise({ taskId, target: null, note: '并行' }), { code: 'CONFLICT' })
  await pause(45)
  const current = (await service.getWorkspace()).tasks.find(task => task.id === taskId)!
  assert.equal(current.state, '待查看')
  assert.equal(current.images[0].version, 1)
  assert.equal(current.images[1].version, 2)
  assert.deepEqual((await service.getWorkspace()).archives.find(a => a.id === archived.id)!.images, archived.images)
})

test('HTTP 真实模式网络断连直接报错，不返回模拟数据', async () => {
  const service = createHttpService('/api/v1', async () => { throw new TypeError('offline') })
  await assert.rejects(service.getWorkspace(), { code: 'UNAVAILABLE' })
  await assert.rejects(service.getUser(), { code: 'UNAVAILABLE' })
})

test('HTTP 拒绝 HTML fallback、无效 JSON、未授权响应', async () => {
  const html = createHttpService('/api/v1', async () => new Response('<html>SPA</html>', { headers: { 'content-type': 'text/html' } }))
  await assert.rejects(html.getWorkspace(), { code: 'INVALID_RESPONSE' })
  const broken = createHttpService('/api/v1', async () => new Response('{', { headers: { 'content-type': 'application/json' } }))
  await assert.rejects(broken.getWorkspace(), { code: 'INVALID_RESPONSE' })
  const denied = createHttpService('/api/v1', async () => new Response(JSON.stringify({ code: 'UNAUTHORIZED', message: '请重新登录' }), { status: 401 }))
  await assert.rejects(denied.getUser(), (error: unknown) => error instanceof ApiError && error.status === 401 && error.message === '请重新登录')
})

test('HTTP 写操作正确传输 Cookie、请求体和 202 受理；204 不解析 JSON', async () => {
  const accepted = { taskId: 'task-1', roundId: 'round-1', state: '排队中' }
  const service = createHttpService('/api/v1/', async (url, init) => {
    assert.equal(init?.credentials, 'include')
    if (init?.method === 'DELETE') return new Response(null, { status: 204 })
    assert.equal(url, '/api/v1/tasks')
    assert.equal(init?.method, 'POST')
    assert.deepEqual(JSON.parse(String(init?.body)), input)
    return new Response(JSON.stringify(accepted), { status: 202, headers: { 'content-type': 'application/json' } })
  })
  assert.deepEqual(await service.createTask(input), accepted)
  await service.deleteTemplate('template/1')
})


test('合法 JSON 的错误结构被拒绝，不能误受理或导致页面崩溃', async () => {
  const responder = (value: unknown) => createHttpService('/api/v1', async () => new Response(JSON.stringify(value), { headers: { 'content-type': 'application/json' } }))
  await assert.rejects(responder({}).createTask(input), { code: 'INVALID_RESPONSE' })
  await assert.rejects(responder({ taskId: '', roundId: 'r', state: '排队中' }).createTask(input), { code: 'INVALID_RESPONSE' })
  await assert.rejects(responder({ templates: [null], tasks: [], archives: [] }).getWorkspace(), { code: 'INVALID_RESPONSE' })
  await assert.rejects(responder({ id: 'u', name: '陌生身份', role: 'root', status: 'active' }).getUser(), { code: 'INVALID_RESPONSE' })
  await assert.rejects(responder(null).getUser(), { code: 'INVALID_RESPONSE' })
  await assert.rejects(responder({}).archive('t'), { code: 'INVALID_RESPONSE' })
  const seed = createMockService({ delayMs: 0 })
  const workspace = await seed.getWorkspace()
  assert.deepEqual(await responder(workspace).getWorkspace(), workspace)
})
