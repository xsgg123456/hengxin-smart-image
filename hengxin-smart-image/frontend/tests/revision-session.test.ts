import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createRenderer, defineComponent, h, ref } from 'vue'
import { useRevisionSession } from '../src/views/hengxin/revision-session'
import { ApiError, createHttpService } from '../src/api/hengxin/http'
import type { Accepted, HengxinService, RevisionInput, TaskDetailData } from '../src/types/hengxin'
const receipt: Accepted = { taskId: 'a', roundId: 'r2', state: '排队中' }
const input: RevisionInput = { taskId: 'a', target: 1, note: '原意见' }
const renderer = createRenderer<object, object>({
  createElement: () => ({}), createText: () => ({}), createComment: () => ({}), insert() {}, remove() {},
  setText() {}, setElementText() {}, parentNode: () => null, nextSibling: () => null, patchProp() {}
})
function mount(identity: () => string | undefined, send: HengxinService['revise']) {
  let form!: ReturnType<typeof useRevisionSession>
  const app = renderer.createApp(defineComponent({ setup() {
    form = useRevisionSession(identity, () => 'a', send)
    return () => h('div', form.note.value)
  } }))
  app.mount({})
  return { form, unmount: () => app.unmount() }
}

test('返工 HTTP 带稳定幂等键及失败来源，不把请求改成首次生成', async () => {
  const requests: RequestInit[] = []
  const service = createHttpService('/api', async (url, init) => {
    assert.equal(url, '/api/tasks/a/rounds'); requests.push(init!)
    return new Response(JSON.stringify(receipt), { status: 202, headers: { 'content-type': 'application/json' } })
  })
  await service.revise({ ...input, retry: true, sourceRoundId: 'failed-1' }, 'stable-key')
  assert.equal((requests[0].headers as Record<string, string>)['Idempotency-Key'], 'stable-key')
  assert.deepEqual(JSON.parse(requests[0].body as string), { ...input, retry: true, sourceRoundId: 'failed-1' })
})

test('双击与关闭重开共享待处理提交，切换任务身份后迟到回执不污染', async () => {
  const user = ref<string | undefined>('inflight-owner'), task = ref('a')
  let finish!: (accepted: Accepted) => void, posts = 0
  const send: HengxinService['revise'] = async () => { posts++; return new Promise(resolve => { finish = resolve }) }
  const first = useRevisionSession(() => user.value, () => task.value, send)
  first.note.value = '草稿'
  const request = first.submit(input)
  const reopened = useRevisionSession(() => user.value, () => task.value, send)
  await assert.rejects(reopened.submit(input), /正在处理中/)
  task.value = 'b'; assert.equal(first.note.value, ''); assert.equal(first.session.value.pending, false)
  user.value = 'other'; finish(receipt); await request
  assert.equal(first.session.value.accepted, undefined)
  user.value = 'inflight-owner'; task.value = 'a'
  assert.deepEqual(reopened.session.value.accepted, receipt); assert.equal(first.note.value, '草稿'); assert.equal(posts, 1)
})

test('401重新登录恢复请求；未知期间编辑保留且只能重放原快照', async () => {
  const user = ref<string | undefined>('401-owner')
  const requests: { body: RevisionInput; key?: string }[] = []
  const send: HengxinService['revise'] = async (body, key) => {
    requests.push({ body, key })
    if (requests.length === 1) { user.value = undefined; throw new ApiError('UNAUTHORIZED', '登录过期', 401) }
    return receipt
  }
  const initial = mount(() => user.value, send), first = initial.form
  first.target.value = 1; first.note.value = input.note
  await assert.rejects(first.submit(input), { status: 401 })
  assert.equal(first.note.value, ''); await assert.rejects(async () => first.resolvePrevious(), /重新登录/)
  initial.unmount()
  user.value = '401-owner'
  const restored = mount(() => user.value, send), next = restored.form
  assert.equal(next.note.value, input.note); next.note.value = '新意见'
  await assert.rejects(next.submit({ ...input, note: next.note.value }), /先确认上次提交/)
  await next.resolvePrevious()
  assert.equal(requests.length, 2); assert.equal(requests[0].key, requests[1].key)
  assert.deepEqual(requests[1].body, input); assert.equal(next.note.value, '新意见')
  restored.unmount()
})

test('冲突保留意见；受理后GET失败不再POST，看到结束轮次后显式开启下一轮', async () => {
  let posts = 0
  const keys: (string | undefined)[] = []
  const form = useRevisionSession(() => 'conflict-owner', () => 'a', async (_input, key) => {
    keys.push(key); posts++
    if (posts === 1) throw new ApiError('CONFLICT', '其他人正在修改', 409)
    return receipt
  })
  form.target.value = 1; form.note.value = input.note
  await assert.rejects(form.submit(input), { status: 409 })
  assert.equal(form.note.value, input.note); assert.equal(form.session.value.uncertain, false)
  await form.submit(input); assert.equal(keys[0], keys[1]); assert.equal(form.blocked.value, true)
  // 详情请求失败意味着没有 observe，重开或再次操作只返回原回执。
  await form.submit(input); assert.equal(posts, 2); assert.equal(form.begin(), false)
  form.observe({ task: { id: 'a' }, rounds: [{ id: 'r2', state: '执行中', finishedAt: null }] } as TaskDetailData)
  assert.equal(form.blocked.value, true)
  form.observe({ task: { id: 'a' }, rounds: [{ id: 'r2', state: '待查看', finishedAt: '2026-09-10' }] } as TaskDetailData)
  assert.equal(form.begin(), true); await form.submit(input)
  assert.equal(posts, 3); assert.notEqual(keys[1], keys[2])
})

test('网络丢响应后目标切换不换键，重试来源轮次也被冻结', async () => {
  const bodies: RevisionInput[] = [], keys: (string | undefined)[] = []
  const form = useRevisionSession(() => 'unknown-owner', () => 'a', async (body, key) => {
    bodies.push(body); keys.push(key)
    if (keys.length === 1) throw new ApiError('INVALID_RESPONSE', '响应不完整')
    return receipt
  })
  const retry = { ...input, retry: true, sourceRoundId: 'failed-round' }
  await assert.rejects(form.submit(retry))
  form.target.value = null; form.note.value = '整套草稿'
  await assert.rejects(form.submit({ ...input, target: null }), /先确认上次提交/)
  await form.resolvePrevious()
  assert.deepEqual(bodies, [retry, retry]); assert.equal(keys[0], keys[1]); assert.equal(form.note.value, '整套草稿')
})
