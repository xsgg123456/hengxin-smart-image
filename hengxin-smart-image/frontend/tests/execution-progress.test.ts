import { test } from 'node:test'
import assert from 'node:assert/strict'
import { activityIsStale, elapsedSeconds, executionPollDelay, executionStageLabel, isExecutionData, type ExecutionData, type ExecutionStatus } from '../src/api/hengxin/execution-data'
import { createExecutionPoller, type ExecutionContext, type ExecutionState } from '../src/views/hengxin/components/execution-poller'
import { createRequest } from '../src/api/hengxin/http'
import { CURRENT_EXECUTION_ROUND, executionRoundSelection } from '../src/api/hengxin/execution-data'

const at = '2026-09-11T00:00:00Z', now = Date.parse(at)
function dto(patch: Partial<ExecutionData> = {}): ExecutionData {
  return { taskId: 'task', roundId: 'round', source: 'cli', status: 'running', diagnosticId: null,
    stage: 'generating', label: '模型处理', startedAt: at, finishedAt: null, updatedAt: at, lastActivityAt: at,
    totalImages: 3, detectedImages: null, legacy: false, events: [], failure: null, ...patch }
}
const context: ExecutionContext = { taskId: 'task', roundId: 'round', identity: 'user-a', active: true, mock: false }
const flush = async () => { await Promise.resolve(); await Promise.resolve() }
function harness() {
  let state: ExecutionState = { loading: false, error: '' }
  const requests: { task: string; round: string; resolve: (data: ExecutionData) => void; reject: (error: Error) => void }[] = []
  const timers: { run: () => void; delay: number; cancelled: boolean }[] = []
  const poller = createExecutionPoller((task, round) => new Promise((resolve, reject) => requests.push({ task, round, resolve, reject })),
    value => { state = value }, { schedule(run, delay) { const timer = { run, delay, cancelled: false }; timers.push(timer); return () => { timer.cancelled = true } } })
  return { poller, requests, timers, state: () => state }
}
test('current sentinel resolves actual round and historical selection remains isolated', async () => {
  assert.equal(CURRENT_EXECUTION_ROUND, 'current')
  assert.deepEqual(executionRoundSelection(CURRENT_EXECUTION_ROUND, 'round'), { historical: false, roundId: 'round' })
  assert.deepEqual(executionRoundSelection(CURRENT_EXECUTION_ROUND, 'next'), { historical: false, roundId: 'next' })
  assert.deepEqual(executionRoundSelection(CURRENT_EXECUTION_ROUND, null), { historical: false, roundId: '' })
  assert.deepEqual(executionRoundSelection('history', 'next'), { historical: true, roundId: 'history' })
  const h = harness()
  h.poller.setContext({ ...context, roundId: executionRoundSelection('history', 'round').roundId })
  h.poller.setContext({ ...context, roundId: executionRoundSelection(CURRENT_EXECUTION_ROUND, 'round').roundId })
  assert.deepEqual(h.requests.map(request => request.round), ['history', 'round'])
  h.requests[0].resolve(dto({ roundId: 'history' })); await flush()
  assert.equal(h.state().data, undefined)
  h.requests[1].resolve(dto({ status: 'failed' })); await flush()
  assert.equal(h.state().data?.roundId, 'round')
  h.poller.dispose()
})
test('DTO validates nested failure, ISO times and numeric fields without coercion', () => {
  assert.equal(isExecutionData(dto()), true)
  assert.equal(isExecutionData(dto({ source: 'fixture', legacy: true, startedAt: null })), true)
  const failure = { code: 'SIZE', message: '图片尺寸不符', action: '检查输入尺寸后重试', stage: 'validating' as const,
    slotErrors: [{ slot: 0, code: 'SIZE', message: '尺寸不符' }] }
  assert.equal(isExecutionData(dto({ failure })), true)
  for (const patch of [{ source: 'unknown' }, { source: null }, { status: 'unknown' }, { stage: '__proto__' }, { startedAt: 'yesterday' }, { updatedAt: undefined },
    { totalImages: -1 }, { totalImages: '3' }, { detectedImages: NaN }, { diagnosticId: '/tmp/private' },
    { events: [null] }, { events: [{ sequence: 0.5, stage: 'generating', message: '处理', at }] },
    { failure: { ...failure, slotErrors: [{ slot: -1, code: 'SIZE', message: '尺寸' }] } }, { failure: { ...failure, action: null } }]) {
    assert.equal(isExecutionData({ ...dto(), ...patch }), false, JSON.stringify(patch))
  }
})
test('historical unavailable executor passes HTTP guard and retains failure without polling', async () => {
  const historical = dto({ source: 'unavailable', legacy: true, status: 'failed', stage: 'failed',
    startedAt: null, finishedAt: null, lastActivityAt: null,
    failure: { code: 'EXECUTOR_UNAVAILABLE', message: '本轮执行器不可用', action: '请联系管理员检查执行器配置', stage: 'starting', slotErrors: [] } })
  const request = createRequest('/api/v1', async () => new Response(JSON.stringify(historical),
    { headers: { 'content-type': 'application/json' } }))
  const result = await request('/tasks/task/execution?roundId=round', isExecutionData)
  assert.deepEqual(result, historical)
  const h = harness(); h.poller.setContext(context); h.requests[0].resolve(result); await flush()
  assert.equal(h.state().error, '')
  assert.equal(h.state().data?.source, 'unavailable')
  assert.equal(h.state().data?.failure?.message, '本轮执行器不可用')
  assert.equal(h.timers.length, 0)
  assert.equal(elapsedSeconds(result, now), null)
  h.poller.dispose()
})
test('authorized HTTP client rejects malformed execution payloads', async () => {
  let credentials: RequestCredentials | undefined
  const request = createRequest('/api/v1', async (_url, options) => {
    credentials = options?.credentials
    return new Response(JSON.stringify({ ...dto(), events: 'raw logs' }), { headers: { 'content-type': 'application/json' } })
  })
  await assert.rejects(request('/tasks/task/execution?roundId=round', isExecutionData), { code: 'INVALID_RESPONSE' })
  assert.equal(credentials, 'include')
})
test('time math handles null, future clock, inactivity threshold and frozen terminal duration', () => {
  assert.equal(elapsedSeconds(dto(), now + 61000), 61)
  assert.equal(elapsedSeconds(dto({ startedAt: null }), now), null)
  assert.equal(elapsedSeconds(dto(), now - 1000), 0)
  assert.equal(elapsedSeconds(dto({ status: 'failed', finishedAt: '2026-09-11T00:00:30Z' }), now + 900000), 30)
  assert.equal(elapsedSeconds(dto({ status: 'failed', updatedAt: null }), now + 900000), null)
  assert.equal(activityIsStale(dto(), now + 59999), false)
  assert.equal(activityIsStale(dto(), now + 60000), true)
  assert.equal(activityIsStale(dto({ status: 'failed' }), now + 900000), false)
  assert.equal(executionStageLabel(dto({ status: 'failed' })), '执行失败')
})
test('all active statuses schedule correctly, all terminal statuses stop in real controller', async () => {
  for (const status of ['queued', 'running', 'collecting', 'cancelling', 'uncertain', 'failed', 'cancelled', 'succeeded', 'partial'] as ExecutionStatus[]) {
    const h = harness(); h.poller.setContext(context)
    assert.equal(h.state().loading, true)
    h.requests[0].resolve(dto({ status })); await flush()
    const delay = executionPollDelay(status)
    assert.equal(h.timers.length, delay === null ? 0 : 1)
    if (delay !== null) {
      assert.equal(h.timers[0].delay, status === 'uncertain' ? 5000 : 2000)
      h.timers[0].run(); assert.equal(h.requests.length, 2)
      h.requests[1].resolve(dto({ status: 'succeeded' })); await flush()
      assert.equal(h.timers.length, 1)
    }
    h.poller.retry(); assert.equal(h.requests.length, delay === null ? 1 : 2)
    h.poller.dispose()
  }
})
test('task, round and identity changes invalidate actual pending responses', async () => {
  for (const patch of [{ taskId: 'new-task' }, { roundId: 'history' }, { identity: 'user-b' }]) {
    const h = harness(); h.poller.setContext(context); h.poller.setContext({ ...context, ...patch })
    assert.equal(h.state().data, undefined)
    h.requests[0].resolve(dto({ failure: { code: 'FAIL', message: '旧用户错误', stage: 'failed', action: '检查', slotErrors: [] } })); await flush()
    assert.equal(h.state().data, undefined); assert.equal(h.timers.length, 0)
    h.requests[1].resolve(dto({ taskId: patch.taskId ?? 'task', roundId: patch.roundId ?? 'round', status: 'failed' })); await flush()
    assert.equal(h.state().data?.taskId, patch.taskId ?? 'task')
    h.poller.dispose()
  }
})
test('close, logout, mock and dispose clear data, cancel timers and ignore late success/error', async () => {
  for (const patch of [{ active: false }, { identity: '' }, { mock: true }]) {
    const h = harness(); h.poller.setContext(context)
    h.requests[0].resolve(dto()); await flush()
    h.timers[0].run()
    h.poller.setContext({ ...context, ...patch })
    h.requests[1].reject(new Error('private raw stderr')); await flush()
    assert.deepEqual(h.state(), { loading: false, error: '' })
    h.timers[0].run() // A callback already queued before cancellation must also be inert.
    assert.equal(h.requests.length, 2); assert.equal(h.timers[0].cancelled, true)
  }
  const h = harness(); h.poller.setContext(context); h.poller.dispose()
  h.requests[0].resolve(dto()); await flush()
  assert.equal(h.state().data, undefined); assert.equal(h.timers.length, 0)
})
test('initial mock mode never fetches; error retry and mismatch are safe', async () => {
  const h = harness(); h.poller.setContext({ ...context, mock: true }); assert.equal(h.requests.length, 0)
  h.poller.setContext(context); h.requests[0].reject(new Error('/home/private session=secret')); await flush()
  assert.ok(h.state().error); assert.equal(h.state().error.includes('secret'), false)
  h.poller.retry(); h.poller.retry(); assert.equal(h.requests.length, 2)
  h.requests[1].resolve(dto({ roundId: 'other-task-round' })); await flush()
  assert.equal(h.state().data, undefined); assert.ok(h.state().error)
  h.poller.retry(); h.requests[2].resolve(dto({ status: 'succeeded' })); await flush()
  assert.equal(h.state().error, ''); assert.equal(h.timers.length, 0)
})
