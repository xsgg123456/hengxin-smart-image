import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createRenderer, defineComponent, h, ref } from 'vue'
import { useTaskCreationSession } from '../src/views/hengxin/task-creation-session'
import { ApiError } from '../src/api/hengxin/http'
import type { Accepted, CreateTaskInput, HengxinService, Mode } from '../src/types/hengxin'

const input: CreateTaskInput = { mode: 'text', name: '保留的名字', sku: 'sku', sources: [{ name: 'a.png', url: '/a.png', fileId: 'a' }], note: '原始要求' }
const receipt: Accepted = { taskId: 'task-restored', roundId: 'round-restored', state: '排队中' }
// 使用 Vue 的真实组件 setup/unmount 生命周期；宿主无需浏览器 DOM。
const renderer = createRenderer<object, object>({
  createElement: () => ({}), createText: () => ({}), createComment: () => ({}), insert() {}, remove() {},
  setText() {}, setElementText() {}, parentNode: () => null, nextSibling: () => null, patchProp() {}
})
function mount(identity: () => string | undefined, send: HengxinService['createTask'], mode: () => Mode = () => 'text', query: () => unknown = () => undefined) {
  let form!: ReturnType<typeof useTaskCreationSession>
  const app = renderer.createApp(defineComponent({ setup() {
    form = useTaskCreationSession(identity, mode, query, send)
    return () => h('div', form.name.value)
  } }))
  app.mount({})
  return { form, unmount: () => app.unmount() }
}

test('首次401卸载后同用户重新挂载恢复草稿，编辑不能替换待确认原键和原快照', async () => {
  const user = ref<string | undefined>('restore-401')
  const requests: { input: CreateTaskInput; key?: string }[] = []
  const send: HengxinService['createTask'] = async (body, key) => {
    requests.push({ input: JSON.parse(JSON.stringify(body)), key })
    if (requests.length === 1) { user.value = undefined; throw new ApiError('UNAUTHORIZED', '登录过期', 401) }
    return receipt
  }
  const first = mount(() => user.value, send)
  first.form.name.value = input.name; first.form.sku.value = input.sku!
  first.form.sources.value = structuredClone(input.sources); first.form.note.value = input.note
  await assert.rejects(first.form.submission.submit(input), { status: 401 })
  first.unmount()
  user.value = 'restore-401'
  const second = mount(() => user.value, send)
  try {
    assert.equal(second.form.name.value, input.name); assert.equal(second.form.sku.value, input.sku)
    assert.deepEqual(second.form.sources.value, input.sources); assert.equal(second.form.note.value, input.note)
    assert.equal(second.form.submission.uncertain.value, true)
    second.form.note.value = '新的草稿意见'
    await assert.rejects(second.form.submission.submit({ ...input, note: second.form.note.value }), /先确认上次提交/)
    await second.form.submission.resolvePrevious()
    assert.equal(requests.length, 2); assert.equal(requests[0].key, requests[1].key)
    assert.deepEqual(requests[1].input, input); assert.equal(second.form.note.value, '新的草稿意见')
  } finally { second.unmount() }
})

test('已受理详情读取失败后重建保留回执；显式另建才发新POST', async () => {
  const keys: (string | undefined)[] = []
  const send: HengxinService['createTask'] = async (_body, key) => { keys.push(key); return receipt }
  const first = mount(() => 'restore-accepted', send)
  await first.form.submission.submit(input)
  first.unmount() // 等价于详情读取401触发 RouterView 卸载。
  const next = mount(() => 'restore-accepted', send)
  try {
    assert.deepEqual(next.form.submission.accepted.value, receipt)
    await next.form.submission.submit(input); assert.equal(keys.length, 1)
    next.form.submission.startNew(); await next.form.submission.submit(input)
    assert.equal(keys.length, 2); assert.notEqual(keys[0], keys[1])
  } finally { next.unmount() }
})

test('换用户和入口隔离草稿与请求，旧组件不能重放别人尝试', async () => {
  const user = ref<string | undefined>('owner-a'), mode = ref<Mode>('wallpaper'), query = ref('template-a')
  let posts = 0
  const first = mount(() => user.value, async () => { posts++; throw new ApiError('UNAVAILABLE', '响应丢失') }, () => mode.value, () => query.value)
  first.form.name.value = '私有草稿'
  await assert.rejects(first.form.submission.submit(input))
  user.value = 'owner-b'
  assert.equal(first.form.name.value, ''); assert.equal(first.form.submission.uncertain.value, false)
  await assert.rejects(first.form.submission.resolvePrevious(), /没有待确认/)
  user.value = undefined
  await assert.rejects(first.form.submission.submit(input), /重新登录/)
  user.value = 'owner-a'; query.value = 'template-b'
  assert.equal(first.form.name.value, ''); await assert.rejects(first.form.submission.resolvePrevious(), /没有待确认/)
  query.value = 'template-a'; mode.value = 'product'
  assert.equal(first.form.name.value, '')
  mode.value = 'wallpaper'; assert.equal(first.form.name.value, '私有草稿')
  assert.equal(first.form.submission.uncertain.value, true); assert.equal(posts, 1)
  first.unmount()
})

test('未完成请求跨卸载仍互斥，迟到回执只写原用户状态', async () => {
  let finish!: (value: Accepted) => void
  let posts = 0
  const send: HengxinService['createTask'] = async () => { posts++; return new Promise(resolve => { finish = resolve }) }
  const first = mount(() => 'inflight-a', send)
  const request = first.form.submission.submit(input); first.unmount()
  const same = mount(() => 'inflight-a', send), other = mount(() => 'inflight-b', send)
  await assert.rejects(same.form.submission.submit(input), /正在处理中/)
  finish(receipt); await request
  assert.deepEqual(same.form.submission.accepted.value, receipt)
  assert.equal(other.form.submission.accepted.value, undefined); assert.equal(posts, 1)
  same.unmount(); other.unmount()
})
