import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createTasksApi, createRequestKeys, isTaskDetail, emptyTaskDraft, validateDraft, cleanDraft, type TaskDetail } from '../src/api/overseas/tasks'
const task: TaskDetail = { ...emptyTaskDraft(), remarks: '', name: '真实任务', skus: [{ code: 'SKU-A' }], id: 'task/1', version: 1, status: 'created', createdAt: '2026-10-12', updatedAt: '2026-10-12', createdBy: { id: 'o', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: ['task.read'], events: [{ id: 'e', kind: 'task.created', actorId: 'o', actorName: '运营', title: '图需已保存', at: '2026-10-12', beforeDesignerId: null, afterDesignerId: 'd', version: 1 }] }
const json = (value: unknown) => new Response(JSON.stringify(value))
test('海外任务API严格字段、幂等头、分页参数与编码路径', async () => {
  const calls: { url: string; options?: RequestInit }[] = []
  const api = createTasksApi(async (url, options) => { calls.push({ url: String(url), options }); return json(String(url).includes('?') ? { items: [task], total: 21, page: 2, pageSize: 20 } : task) })
  const draft = { ...emptyTaskDraft(), remarks: '', name: '  图需  ', designerId: 'd', createdBy: '伪造', files: [] }
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
  const draft = { ...emptyTaskDraft(), remarks: '', name: '任务', productName: '品名', platform: 'Amazon', language: 'en', brand: '品牌', market: '美国', designerId: 'd', skus: [{ code: 'A' }, { code: 'B' }] }
  assert.doesNotThrow(() => validateDraft(draft))
  assert.throws(() => validateDraft({ ...draft, designerId: '' }), /指定设计/)
  assert.throws(() => validateDraft({ ...draft, skus: [{ code: 'A' }, { code: ' a ' }] }), /重复/)
  assert.throws(() => validateDraft({ ...draft, skus: [{ code: ' ' }] }), /SKU/)
  assert.equal(isTaskDetail(task), true)
  for (const value of [{ ...task, version: 0 }, { ...task, capabilities: null }, { ...task, events: [{}] }, { ...task, designer: { ...task.designer, eligible: undefined } }]) assert.equal(isTaskDetail(value), false)
})
test('新建无需站点，目标平台仍必填，修改请求保留历史站点', async () => {
  const draft = { ...emptyTaskDraft(), remarks: '', name: '任务', productName: '品名', platform: 'Amazon', language: 'en', brand: 'OUTON', designerId: 'd', skus: [{ code: 'A' }] }
  assert.doesNotThrow(() => validateDraft(draft))
  assert.throws(() => validateDraft({ ...draft, platform: '' }), /必填/)
  const bodies: Record<string, unknown>[] = []
  const api = createTasksApi(async (_url, options) => {
    bodies.push(JSON.parse(String(options?.body)))
    return json(task)
  })
  await api.create(draft, 'create-empty-market')
  await api.resubmit('task/1', { ...draft, market: '美国', materialIds: ['m'] }, 2, 'keep-market')
  await api.resubmit('task/1', { ...draft, materialIds: ['m'] }, 2, 'empty-market')
  assert.deepEqual(bodies.map(body => body.market), ['', '美国', ''])
  assert.ok(bodies.every(body => body.platform === 'Amazon'))
})


test('新建与重提请求不发送历史补充说明，响应仍保留历史值', async () => {
  const bodies: Record<string, unknown>[] = []
  const api = createTasksApi(async (_url, options) => { bodies.push(JSON.parse(String(options?.body))); return json({ ...task, remarks: '旧资料' }) })
  const draft = { ...emptyTaskDraft(), remarks: '历史字段不回传' }
  assert.equal((await api.create(draft, 'new')).remarks, '旧资料')
  assert.equal((await api.resubmit('task/1', draft, 1, 'edit')).remarks, '旧资料')
  assert.ok(bodies.every(body => !Object.hasOwn(body, 'remarks')))
})

test('语言四值写入与历史读取兼容；缺省、空和非法写入不可提交', async () => {
  const draft = { ...emptyTaskDraft(), name: '任务', productName: '品名', platform: 'Amazon', brand: 'OUTON', designerId: 'd', skus: [{ code: 'A' }] }
  assert.equal(emptyTaskDraft().language, ''); assert.equal(emptyTaskDraft().platform, '')
  const bodies: Record<string, unknown>[] = []
  const api = createTasksApi(async (_url, options) => { bodies.push(JSON.parse(String(options?.body))); return json(task) })
  for (const language of ['en', 'de', 'fr', 'es']) {
    assert.doesNotThrow(() => validateDraft({ ...draft, language }))
    await api.create({ ...draft, language }, language)
    await api.resubmit(task.id, { ...draft, language }, 1, language)
  }
  assert.deepEqual(bodies.map(body => body.language), ['en','en','de','de','fr','fr','es','es'])
  for (const language of ['', 'zh', 'EN', ' en ', null, undefined]) assert.throws(() => validateDraft({ ...draft, language } as typeof draft), /请选择语言/)
  for (const language of [null, undefined, 'en']) assert.equal(isTaskDetail({ ...task, language }), true)
  for (const language of [3, {}, []]) assert.equal(isTaskDetail({ ...task, language }), false)
})
