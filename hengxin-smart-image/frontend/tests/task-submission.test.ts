import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createHttpService, ApiError } from '../src/api/hengxin/http'
import { createMockService } from '../src/api/hengxin/mock'
import { sampleImages } from '../src/api/hengxin/fixtures'
import { useTaskSubmission } from '../src/views/hengxin/task-submission'
import { fixtureNotice, taskActions, taskPollDelay } from '../src/views/hengxin/task-state'
import type { Accepted, CreateTaskInput } from '../src/types/hengxin'

const input: CreateTaskInput = { mode: 'text', name: '文字任务', sources: [{ name: 'a.png', url: '/a.png', fileId: 'file-a' }], note: '改为新品' }
const receipt: Accepted = { taskId: 'task-a', roundId: 'round-a', state: '排队中' }
const response = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status, headers: { 'content-type': 'application/json' } })

test('响应丢失后重放同键原快照，变更输入保留且不能静默创建第二任务', async () => {
  const requests: { key: string; body: unknown }[] = []
  const service = createHttpService('/api/v1', async (_url, init) => {
    requests.push({ key: new Headers(init?.headers).get('Idempotency-Key')!, body: JSON.parse(String(init?.body)) })
    if (requests.length === 1) throw new TypeError('response lost after commit')
    return response(receipt, 202)
  })
  const submission = useTaskSubmission(service.createTask)
  const draft = structuredClone(input)
  await assert.rejects(submission.submit(draft), { code: 'UNAVAILABLE' })
  draft.note = '保留这个新意见'
  await assert.rejects(submission.submit(draft), /先确认上次提交/)
  assert.equal(requests.length, 1)
  assert.equal(draft.note, '保留这个新意见')
  assert.deepEqual(await submission.resolvePrevious(), receipt)
  assert.equal(requests[0].key, requests[1].key)
  assert.deepEqual(requests[1].body, input)
  assert.deepEqual(await submission.submit(draft), receipt)
  assert.equal(requests.length, 2)
})

test('202 后详情读取失败仍保留原任务 ID，不再次 POST；重复点击不并行受理', async () => {
  let posts = 0
  const service = createHttpService('/api/v1', async (_url, init) => {
    if (init?.method !== 'POST') throw new Error('detail unavailable')
    posts++
    await new Promise(resolve => setTimeout(resolve, 5))
    return response(receipt, 202)
  })
  const submission = useTaskSubmission(service.createTask)
  const first = submission.submit(input)
  await assert.rejects(submission.submit(input), /正在处理中/)
  await first
  await assert.rejects(service.getTask(receipt.taskId), { code: 'UNAVAILABLE' })
  assert.equal(submission.accepted.value?.taskId, receipt.taskId)
  await submission.submit(input)
  assert.equal(posts, 1)
  submission.startNew()
  await submission.submit(input)
  assert.equal(posts, 2)
})

test('明确校验拒绝后编辑采用新键；503 不伪成功且不清空表单', async () => {
  const keys: (string | undefined)[] = []
  const submission = useTaskSubmission(async (_input, key) => {
    keys.push(key)
    if (keys.length === 1) throw new ApiError('VALIDATION', '素材无效', 422)
    throw new ApiError('EXECUTOR_UNAVAILABLE', '执行器不可用', 503)
  })
  const draft = structuredClone(input)
  await assert.rejects(submission.submit(draft), { status: 422 })
  draft.note = '修正后的要求'
  await assert.rejects(submission.submit(draft), { status: 503 })
  assert.notEqual(keys[0], keys[1])
  assert.equal(draft.sources[0].fileId, 'file-a')
  assert.equal(draft.note, '修正后的要求')
  assert.equal(submission.accepted.value, undefined)
})

test('不确定请求重放被401拒绝仍须保留原键，不能因重新认证静默重复创建', async () => {
  let calls = 0
  const submission = useTaskSubmission(async () => {
    if (++calls === 1) throw new ApiError('UNAVAILABLE', '响应丢失')
    throw new ApiError('UNAUTHORIZED', '登录过期', 401)
  })
  await assert.rejects(submission.submit(input))
  await assert.rejects(submission.resolvePrevious(), { status: 401 })
  await assert.rejects(submission.submit({ ...input, note: '新内容' }), /先确认上次提交/)
  assert.equal(calls, 2)
})

test('操作资格坏 DTO 拒绝；失败状态不能覆盖服务端禁用，fixture 与轮询来源准确', async t => {
  const mock = createMockService({ delayMs: 0 }); t.after(() => mock.dispose())
  const detail = await mock.getTask('HX0908-001')
  assert.equal(taskActions(detail, false, '').canRevise, true)
  const blocked = { ...detail, task: { ...detail.task, state: '失败' as const, executionSource: 'fixture' as const },
    executionControl: { canRevise: false, canRetry: false, blockedReason: '执行状态待核实' } }
  assert.deepEqual(taskActions(blocked, false, ''), { canRevise: false, canRetry: false })
  assert.match(fixtureNotice(blocked.task), /未调用真实 Skill/)
  assert.equal(fixtureNotice(detail.task), '')
  assert.equal(taskPollDelay([blocked.task]), 10000)
  assert.equal(taskPollDelay([{ ...blocked.task, state: '执行中' }]), 3000)
  for (const body of [{ ...detail, executionControl: undefined }, { ...detail, executionControl: { canRevise: 'false', canRetry: false, blockedReason: null } },
    { ...detail, task: { ...detail.task, executionSource: 'fake' } }]) {
    await assert.rejects(createHttpService('/api', async () => response(body)).getTask('t'), { code: 'INVALID_RESPONSE' })
  }
  assert.deepEqual(await createHttpService('/api', async () => response(blocked)).getTask('t'), blocked)
})

test('模拟同键重放只创建一个任务，同键异内容拒绝且保留返工资格', async t => {
  const mock = createMockService({ delayMs: 0, stepMs: 1000 }); t.after(() => mock.dispose())
  const before = (await mock.listTasks({ page: 1, pageSize: 100 })).total
  const sample = { ...input, sources: sampleImages('text', 1) }
  const first = await mock.createTask(sample, 'same-request')
  assert.deepEqual(await mock.createTask(sample, 'same-request'), first)
  await assert.rejects(mock.createTask({ ...sample, note: 'changed' }, 'same-request'), { code: 'CONFLICT' })
  assert.equal((await mock.listTasks({ page: 1, pageSize: 100 })).total, before + 1)
  assert.equal((await mock.getTask(first.taskId)).executionControl.canRevise, false)
})
