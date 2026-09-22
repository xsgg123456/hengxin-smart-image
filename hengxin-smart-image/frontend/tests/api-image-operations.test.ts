import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createApiImageClient } from '../src/api/api-image-edits'
import { ApiError } from '../src/api/hengxin/http'
import { task as validTask } from '../src/api/api-image-edits-validate'
import { createItemCommand, type ItemCommand, type PendingCommand } from '../src/views/hengxin/api-image-edits/item-command'
const json = (value: unknown) => new Response(JSON.stringify(value), { headers: { 'content-type': 'application/json' } })
const picture = { fileId: 'file', name: 'x.png', url: '/image' }
const revision: ItemCommand = { kind: 'revise', input: { baseVersion: 3, text: '调整', annotationFileId: 'mark' }, annotation: { ...picture, fileId: 'mark' } }
test('单图三个写接口带原幂等键、认证、精确冻结输入；ZIP拒绝假文件', async () => {
  const calls: { url: string; init?: RequestInit }[] = []
  const api = createApiImageClient('/api/v1', async (url, init) => { calls.push({ url: String(url), init }); return json({ taskId: 'task' }) })
  await api.revise('task', 'a/b', revision.input, 'key-1'); await api.restore('task', 'a/b', 2, 'key-2'); await api.retryItem('task', 'a/b', 'key-3')
  assert.deepEqual(calls.map(c => c.url.split('/').at(-1)), ['revise', 'restore', 'retry'])
  assert.ok(calls.every(c => c.url.includes('/items/a%2Fb/') && c.init?.credentials === 'include'))
  assert.deepEqual(calls.map(c => new Headers(c.init?.headers).get('Idempotency-Key')), ['key-1', 'key-2', 'key-3'])
  assert.deepEqual(JSON.parse(String(calls[0].init?.body)), revision.input)
  assert.deepEqual(JSON.parse(String(calls[1].init?.body)), { version: 2 })
  await assert.rejects(api.zip('task'), /不是 ZIP/)
  const zipped = createApiImageClient('/api/v1', async (_url, init) => { assert.equal(init?.credentials, 'include'); return new Response('zip', { headers: { 'content-type': 'application/zip' } }) })
  assert.equal((await zipped.zip('task')).type, 'application/zip')
})
test('断网后修改输入/操作类型不能更换原请求；重新挂载恢复原键和标注引用', async () => {
  let persisted: PendingCommand | null = null
  const storage = { load: () => persisted, save: (p: PendingCommand | null) => { persisted = p ? JSON.parse(JSON.stringify(p)) as PendingCommand : null } }
  const first = createItemCommand(storage, () => 'original-key')
  assert.equal(await first.submit(revision, async () => { throw new ApiError('UNAVAILABLE', '断网') }), false)
  assert.ok(first.state.pending?.uncertain)
  const reopened = createItemCommand(storage, () => 'wrong-key')
  const seen: { command: ItemCommand; key: string }[] = []
  assert.equal(await reopened.submit({ kind: 'restore', version: 1 }, async (command, key) => { seen.push({ command, key }); throw new ApiError('CONFLICT', '冲突', 409) }), false)
  assert.deepEqual(seen[0], { command: revision, key: 'original-key' })
  assert.ok(reopened.state.pending, '未知请求后即使4xx也不能抛弃原键')
  assert.equal(await reopened.submit(revision, async () => {}), true)
  assert.equal(reopened.state.pending, null); assert.equal(persisted, null)
})
test('明确拒绝释放输入；双击只有一个POST；确认受理先清待确认状态，与后续GET分离', async () => {
  const operation = createItemCommand(undefined, () => 'key')
  assert.equal(await operation.submit(revision, async () => { throw new ApiError('INVALID', '无效', 422) }), false)
  assert.equal(operation.state.pending, null)
  let resolve!: () => void, calls = 0
  const first = operation.submit(revision, () => { calls++; return new Promise<void>(r => { resolve = r }) })
  assert.equal(await operation.submit(revision, async () => { calls++ }), false)
  assert.equal(calls, 1); resolve(); assert.equal(await first, true)
  assert.equal(operation.state.pending, null); assert.equal(operation.state.busy, false)
  await assert.rejects(async () => { throw new Error('GET failed') })
  assert.equal(calls, 1); assert.equal(operation.state.pending, null)
})
test('严格验证版本DTO：拒绝当前指针错配/重复编号/缺操作人，容许修改失败保留成功旧版', () => {
  const value = { id: 't', name: '任务', prompt: '要求', created: '2026-09-22', operator: '张三', batch: { current: 2, total: 2, running: 0 }, status: 'failed', material: picture,
    items: [{ id: 'i', position: 1, source: picture, state: 'failed', retries: 3, nextAttemptAt: null, error: '失败', result: picture, currentVersion: 1,
      versions: [{ number: 1, picture, created: '2026-09-22', operator: '张三', text: '', annotation: null, baseVersion: null }],
      revision: { state: 'failed', text: '调整', annotation: null, operator: '李四', baseVersion: 1, retries: 3, error: '失败' } }], events: [], error: null, metrics: { requestCount: 4, retryCount: 3, elapsedSeconds: 10 } }
  assert.equal(validTask(value), true)
  assert.equal(validTask({ ...value, operator: undefined }), false)
  assert.equal(validTask({ ...value, items: [{ ...value.items[0], currentVersion: 2 }] }), false)
  assert.equal(validTask({ ...value, items: [{ ...value.items[0], versions: [...value.items[0].versions, ...value.items[0].versions] }] }), false)
})
