import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createApiImageClient } from '../src/api/api-image-edits'
import { channel, task as validTask } from '../src/api/api-image-edits-validate'
import { ApiError } from '../src/api/hengxin/http'
import type { ApiItem, ApiRetry, ApiTask } from '../src/types/api-image-edits'
import { createItemCommand, type PendingCommand } from '../src/views/hengxin/api-image-edits/item-command'
import { channelRetryText, itemRetryText, remainingSeconds } from '../src/views/hengxin/api-image-edits/retry-status'

const now = Date.parse('2026-10-20T00:00:00Z')
const retry: ApiRetry = { cycleId: 'cycle', attempts: 7, maxAttempts: 20, startedAt: '2026-10-19T23:55:00Z', deadlineAt: '2026-10-20T00:40:00Z', nextAttemptAt: '2026-10-20T00:00:10Z', stopRequested: false, canStop: true, reason: '等待发送名额' }
const item: ApiItem = { id: 'i', position: 1, source: null, state: 'retry_wait', retries: 6, nextAttemptAt: null, result: null, error: null, currentVersion: null, versions: [], revision: null, retry }
const task: ApiTask = { id: 't', name: '测试', prompt: '', created: '', status: 'running', operator: '测试', batch: { current: 1, total: 1, running: 0 }, material: null, items: [item], events: [], error: null, metrics: { requestCount: 7, retryCount: 6, elapsedSeconds: null } }

test('新轮次20次与历史4次都严格解析，缺少扩展字段的旧记录兼容', () => {
  assert.equal(validTask(task), true)
  assert.equal(validTask({ ...task, items: [{ ...item, retry: undefined }] }), true)
  assert.equal(validTask({ ...task, items: [{ ...item, retry: { ...retry, attempts: 4, maxAttempts: 4 } }] }), true)
  for (const invalid of [null, {}, { ...retry, attempts: 21 }, { ...retry, maxAttempts: 0 }, { ...retry, attempts: 1.5 }, { ...retry, canStop: 'true' }, { ...retry, stopRequested: undefined }, { ...retry, reason: {} }]) {
    assert.equal(validTask({ ...task, items: [{ ...item, retry: invalid }] }), false)
  }
  assert.equal(channel({ enabled: true, paused: false, reason: null }), true)
  assert.equal(channel({ enabled: true, paused: false, reason: null, cooldownUntil: retry.nextAttemptAt, recovering: true }), true)
  assert.equal(channel({ enabled: true, paused: false, reason: null, cooldownUntil: 10 }), false)
  assert.equal(channel({ enabled: true, paused: false, reason: null, recovering: 1 }), false)
})

test('倒计时只读取服务端时刻，覆盖等待名额、未知、停止中、终止、成功及旧数据', () => {
  assert.equal(remainingSeconds(retry.nextAttemptAt, now), 10)
  assert.equal(remainingSeconds(retry.nextAttemptAt, now + 1001), 9)
  assert.equal(remainingSeconds(retry.nextAttemptAt, now + 20000), 0)
  assert.equal(remainingSeconds('invalid', now), null)
  assert.match(itemRetryText(item, now), /至少 10 秒/)
  assert.match(itemRetryText(item, now + 10000), /等待后台分配发送名额/)
  assert.match(itemRetryText({ ...item, retry: undefined, nextAttemptAt: retry.nextAttemptAt }, now), /至少 10 秒/)
  assert.match(itemRetryText({ ...item, retry: undefined, state: 'queued' }, now), /等待后台/)
  assert.match(itemRetryText({ ...item, state: 'running', retry: { ...retry, stopRequested: true } }, now), /已发出的请求继续收取结果/)
  assert.match(itemRetryText({ ...item, state: 'uncertain', retry: { ...retry, stopRequested: true } }, now), /已请求停止后续重试.*需核实/)
  assert.match(itemRetryText({ ...item, state: 'failed', retry: { ...retry, stopRequested: true } }, now), /本轮已停止重试/)
  assert.equal(itemRetryText({ ...item, state: 'failed' }, now), '')
  assert.equal(itemRetryText({ ...item, state: 'succeeded', retry: { ...retry, stopRequested: true } }, now), '')
})

test('自动冷却与恢复仅提示等待，人工暂停由原有流程呈现', () => {
  const base = { enabled: true, paused: false, reason: null }
  assert.match(channelRetryText({ ...base, cooldownUntil: retry.nextAttemptAt }, now), /至少 10 秒后探测恢复/)
  assert.match(channelRetryText({ ...base, cooldownUntil: retry.nextAttemptAt }, now + 10000), /恢复探测中/)
  assert.match(channelRetryText({ ...base, recovering: true }, now), /发送速度逐步恢复/)
  assert.equal(channelRetryText({ ...base, paused: true, recovering: true }, now), '')
  assert.equal(channelRetryText(base, now), '')
})

test('停止网络未知后持久保留同一键，刷新后确认也不能变成重试或CLI停止', async () => {
  let saved: PendingCommand | null = null
  const storage = { load: () => saved, save: (value: PendingCommand | null) => { saved = value ? structuredClone(JSON.parse(JSON.stringify(value))) as PendingCommand : null } }
  const calls: { url: string; key: string | null; method?: string; body?: BodyInit | null }[] = []
  const client = createApiImageClient('/api/v1', async (url, init) => {
    assert.equal(init?.credentials, 'include')
    calls.push({ url: String(url), key: new Headers(init?.headers).get('Idempotency-Key'), method: init?.method, body: init?.body })
    if (calls.length === 1) throw new Error('断网')
    return new Response(JSON.stringify({ taskId: 't/1' }), { headers: { 'content-type': 'application/json' } })
  })
  const first = createItemCommand(storage, () => 'stop-key')
  const send = (_command: unknown, key: string) => client.stopItem('t/1', 'i/1', key)
  assert.equal(await first.submit({ kind: 'stop' }, send), false)
  assert.equal(first.state.pending?.uncertain, true)
  const reopened = createItemCommand(storage, () => 'wrong-key')
  assert.equal(await reopened.submit({ kind: 'retry' }, (command, key) => {
    assert.equal(command.kind, 'stop'); return send(command, key)
  }), true)
  assert.deepEqual(calls, Array(2).fill({ url: '/api/v1/api-image-edits/tasks/t%2F1/items/i%2F1/stop', key: 'stop-key', method: 'POST', body: undefined }))
  assert.equal(saved, null)
})

test('停止明确失败可恢复且双击只发送一次，成功后清除原待确认状态', async () => {
  const operation = createItemCommand(undefined, () => 'stop-key')
  assert.equal(await operation.submit({ kind: 'stop' }, async () => { throw new ApiError('CONFLICT', '当前图片不可停止', 409) }), false)
  assert.equal(operation.state.pending, null)
  assert.equal(operation.state.busy, false)
  assert.match(operation.state.error, /不可停止/)
  let finish!: () => void, count = 0
  const first = operation.submit({ kind: 'stop' }, async () => { count++; await new Promise<void>(resolve => { finish = resolve }) })
  assert.equal(operation.state.busy, true)
  assert.equal(await operation.submit({ kind: 'stop' }, async () => { count++ }), false)
  assert.equal(count, 1)
  finish(); assert.equal(await first, true)
  assert.equal(operation.state.busy, false); assert.equal(operation.state.pending, null)
})
