import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createApiImageClient } from '../src/api/api-image-edits'
import { ApiError } from '../src/api/hengxin/http'
import { summary, deletion } from '../src/api/api-image-edits-validate'
import { taskLabels, isApiTaskPending, canDeleteTask, cliActivityLabel, deleteBlockedReason, isTaskActive, type ApiTaskState, type CliActivity } from '../src/types/api-image-edits'

const task = { id: 't', name: '任务', status: 'succeeded' as const, created: '2026-10-15', operator: '操作人',
  cover: null, counts: { total: 1, success: 1, failed: 0, uncertain: 0 }, batch: { total: 1, current: 1, running: 0 } }
test('状态筛选名称唯一，处理中统计包含等待结果且不混入终态或独立CLI', () => {
  const statuses = Object.keys(taskLabels) as ApiTaskState[]
  assert.equal(new Set(Object.values(taskLabels)).size, statuses.length)
  assert.equal(taskLabels.running, '处理中')
  assert.equal(taskLabels.uncertain, '等待结果')
  for (const label of Object.values(taskLabels)) assert.doesNotMatch(label, /核实|管理员|租约|探测/)
  const records = statuses.map(status => ({ ...task, status }))
  const processing = records.filter(isApiTaskPending)
  assert.equal(processing.length, 3)
  assert.deepEqual(processing.map(record => record.status), ['queued', 'running', 'uncertain'])
  const cliOnly = { ...task, cliActivity: 'running' as const }
  assert.equal(isTaskActive(cliOnly), true)
  assert.equal(isApiTaskPending(cliOnly), false)
  const waiting = records.find(record => record.status === 'uncertain')!
  assert.equal(canDeleteTask({ ...waiting, canDelete: true }), false)
})
test('CLI摘要独立于已成功API状态，未知不能视为结束；结束标签消失', () => {
  for (const cliActivity of ['queued', 'running', 'uncertain'] as CliActivity[]) {
    const active = { ...task, cliActivity, canDelete: true }
    assert.equal(isTaskActive(active), true)
    assert.equal(canDeleteTask(active), false)
    assert.ok(deleteBlockedReason(active))
    assert.equal(cliActivityLabel(cliActivity), cliActivity === 'queued' ? '等待修改' : '图片修改中')
    assert.equal(summary(active), true)
  }
  assert.equal(cliActivityLabel('idle'), '')
  assert.equal(isTaskActive({ ...task, cliActivity: 'idle' }), false)
  assert.equal(canDeleteTask({ ...task, cliActivity: 'idle', canDelete: true }), true)
})
test('旧摘要可读但未确认删除能力时禁删；新字段严格验证', () => {
  assert.equal(summary(task), true)
  assert.equal(canDeleteTask(task), false)
  assert.equal(summary({ ...task, cliActivity: 'unexpected' }), false)
  assert.equal(summary({ ...task, canDelete: 'yes' }), false)
  assert.equal(summary({ ...task, deletionState: 'done' }), false)
  assert.equal(canDeleteTask({ ...task, canDelete: true, deletionState: 'deleting' }), false)
  assert.equal(canDeleteTask({ ...task, canDelete: true, deletionState: 'failed' }), true)
  assert.equal(canDeleteTask({ ...task, canDelete: false, deleteBlockedReason: '停止待核实' }), false)
})
test('真实完整删除DTO覆盖202受理、查询中、失败、重试与成功', async () => {
  const calls: string[] = []
  const replies = [
    { method: 'DELETE', status: 202, body: { state: 'deleting', message: null } },
    { method: 'GET', status: 200, body: { state: 'deleting', message: null } },
    { method: 'GET', status: 200, body: { state: 'failed', message: '删除未完成，请重试' } },
    { method: 'DELETE', status: 202, body: { state: 'deleting', message: null } },
    { method: 'GET', status: 200, body: { state: 'deleted', message: null } }
  ]
  let index = 0
  const client = createApiImageClient('/api/v1', async (url, init) => {
    calls.push(`${init?.method || 'GET'} ${url}`)
    const reply = replies[index++]!
    assert.equal(init?.method, reply.method)
    return new Response(JSON.stringify(reply.body), { status: reply.status, headers: { 'content-type': 'application/json' } })
  })
  for (const reply of replies) {
    const result = await (reply.method === 'DELETE' ? client.remove('a/b') : client.deletion('a/b'))
    assert.deepEqual(result, reply.body)
  }
  assert.deepEqual(calls, replies.map(reply => `${reply.method} /api/v1/api-image-edits/tasks/a%2Fb${reply.method === 'GET' ? '/deletion' : ''}`))
  assert.equal(deletion({ state: 'failed', message: null }), true)
})
test('删除客户端仍拒绝缺字段、旧软删除、非法状态及非法message，不误报成功', async () => {
  const invalid = [null, [], 'deleted', { deleted: true }, { state: 'deleted' }, { message: null },
    { state: 'idle', message: null }, { state: 'delete_failed', message: null }, { state: 1, message: null },
    ...[{}, [], 0, false].map(message => ({ state: 'deleted', message }))]
  for (const payload of invalid) {
    assert.equal(deletion(payload), false, JSON.stringify(payload))
    const client = createApiImageClient('/api/v1', async () => new Response(JSON.stringify(payload), {
      status: 202, headers: { 'content-type': 'application/json' }
    }))
    for (const request of [() => client.remove('task'), () => client.deletion('task')]) {
      await assert.rejects(request, error => error instanceof ApiError && error.code === 'INVALID_RESPONSE')
    }
  }
})
