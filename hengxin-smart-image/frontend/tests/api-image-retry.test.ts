import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createApiImageClient } from '../src/api/api-image-edits'
import { channel, task as validTask } from '../src/api/api-image-edits-validate'
import { ApiError } from '../src/api/hengxin/http'
import type { ApiItem, ApiRetry, ApiTask } from '../src/types/api-image-edits'
import { createItemCommand, type PendingCommand } from '../src/views/hengxin/api-image-edits/item-command'
import { channelRetryText, itemStatusText, taskProgressText } from '../src/views/hengxin/api-image-edits/retry-status'

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

test('真实状态只展示简短进度，未知在途不冒充失败或停止', () => {
  const labels = { queued: '等待中', running: '生成中', retry_wait: '重试中', collecting: '保存中', succeeded: '已完成', failed: '未完成', uncertain: '生成中' } as const
  for (const [state, label] of Object.entries(labels)) assert.equal(itemStatusText({ ...item, state: state as ApiItem['state'] }), label)
  assert.equal(itemStatusText({ ...item, state: 'failed', retry: { ...retry, stopRequested: true } }), '已停止')
  assert.equal(itemStatusText({ ...item, state: 'uncertain', retry: { ...retry, stopRequested: true } }), '生成中')
  const progress = (state: ApiItem['state'], status: ApiTask['status'] = 'running') => taskProgressText({ ...task, status, items: [{ ...item, state }] })
  assert.match(progress('queued'), /等待处理/)
  assert.match(progress('running'), /正在生成/)
  assert.match(progress('uncertain', 'uncertain'), /正在生成/)
  assert.match(progress('retry_wait'), /自动重试/)
  assert.match(progress('collecting'), /正在保存/)
  assert.match(progress('succeeded', 'succeeded'), /已完成 1\/1 张，可以下载/)
  assert.equal(progress('failed', 'failed'), '已完成 0/1 张，1 张未完成，可点击重试。')
  assert.equal(taskProgressText({ ...task, items: [{ ...item, state: 'failed' }, item] }), '已完成 0/2 张，1 张未完成可逐张重试，其余正在处理。')
  assert.match(taskProgressText({ ...task, status: 'failed', items: [{ ...item, state: 'failed', retry: { ...retry, stopRequested: true } }] }), /已停止自动重试/)
})

test('繁忙与不可用有简短提示，不显示内部冷却原因或计时', () => {
  const base = { enabled: true, paused: false, reason: 'upstream raw secret' }
  assert.equal(channelRetryText({ ...base, cooldownUntil: retry.nextAttemptAt }), '服务繁忙，正在等待处理，请稍候。')
  assert.equal(channelRetryText({ ...base, recovering: true }), '服务繁忙，正在等待处理，请稍候。')
  assert.equal(channelRetryText({ ...base, paused: true, recovering: true }), '')
  assert.equal(channelRetryText(base), '')
  assert.match(taskProgressText(task, { ...base, paused: true }), /服务暂不可用/)
  assert.match(taskProgressText(task, { ...base, enabled: false }), /服务暂不可用/)
  assert.match(taskProgressText(task, { ...base, recovering: true }), /服务繁忙/)
  assert.match(taskProgressText({ ...task, items: [{ ...item, state: 'collecting' }] }, { ...base, recovering: true }), /正在保存/)
  assert.equal('resolve' in createApiImageClient('/api/v1'), false)
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
  assert.equal(operation.state.error, '停止操作未完成，请再试一次。')
  let finish!: () => void, count = 0
  const first = operation.submit({ kind: 'stop' }, async () => { count++; await new Promise<void>(resolve => { finish = resolve }) })
  assert.equal(operation.state.busy, true)
  assert.equal(await operation.submit({ kind: 'stop' }, async () => { count++ }), false)
  assert.equal(count, 1)
  finish(); assert.equal(await first, true)
  assert.equal(operation.state.busy, false); assert.equal(operation.state.pending, null)
})
