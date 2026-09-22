import { test } from 'node:test'
import assert from 'node:assert/strict'
import { preview, tick, taskState, retryFailed, batchInfo, requestRevision, retryRevision, ensureExamples, startScenario, type EditTask, type Scenario } from '../src/views/hengxin/api-image-edits/preview-state'
function task(scenario: Scenario, count = 11): EditTask {
  return { id: 'test', name: 'test', prompt: 'test', created: '', material: { name: 'm', url: 'm' }, scenario, events: [],
    items: Array.from({ length: count }, (_, i) => ({ source: { name: `${i}`, url: `${i}` }, state: '等待处理', retries: 0, nextAt: 0 })) }
}
function setup(scenario: Scenario = 'success') {
  preview.tasks = [task(scenario)]; preview.paused = false
  return preview.tasks[0]
}
test('11张按10+1严格分批，后一任务等待', () => {
  const current = setup()
  preview.tasks.unshift(task('success'))
  tick(0)
  assert.deepEqual(batchInfo(current), { current: 1, total: 2, running: 10 })
  assert.equal(current.items[10].state, '等待处理')
  assert.equal(preview.tasks[0].items[0].state, '等待处理')
  tick(2400)
  assert.equal(current.items[10].state, '等待处理')
  tick(2401)
  assert.deepEqual(batchInfo(current), { current: 2, total: 2, running: 1 })
  tick(4801)
  assert.equal(taskState(current), '全部成功')
})
test('首调+三次1/2/4秒退避，等待失败图终态才开始下一批；重试保留成功项', () => {
  const current = setup('partial')
  tick(0); tick(2400)
  assert.equal(current.items[2].nextAt, 3400)
  tick(3400); tick(5800)
  assert.equal(current.items[2].nextAt, 7800)
  tick(7800); tick(10200)
  assert.equal(current.items[2].nextAt, 14200)
  assert.equal(current.items[10].state, '等待处理')
  tick(14200); tick(16600)
  assert.equal(current.items[2].state, '失败')
  tick(16601); tick(19001)
  assert.equal(taskState(current), '部分失败')
  const oldItem = current.items[0], oldResult = oldItem.result
  retryFailed(current); tick(20000); tick(22400)
  assert.equal(taskState(current), '全部成功')
  assert.equal(current.items[0], oldItem)
  assert.equal(current.items[0].result, oldResult)
})
test('暂停不推进；恢复后自动重试成功', () => {
  const current = setup('retry')
  preview.paused = true; tick(10000)
  assert.equal(current.items[0].state, '等待处理')
  preview.paused = false
  tick(0); tick(2400); tick(3400); tick(5800); tick(5801); tick(8201)
  assert.equal(taskState(current), '全部成功')
  assert.equal(current.items[2].retries, 1)
})
test('单图修改保留旧结果；失败禁ZIP、可继续重试，成功仅更新目标图', () => {
  const current = setup()
  tick(0); tick(2400); tick(2401); tick(4801)
  const original = current.items[0].result, neighbor = current.items[1].result
  assert.throws(() => requestRevision(current, 0, '  '), /意见/)
  requestRevision(current, 0, '调整壁纸', undefined, 'partial')
  assert.throws(() => requestRevision(current, 0, '重复'), /未完成/)
  assert.equal(current.items[0].result, original)
  assert.equal(taskState(current), '处理中')
  const start = current.items[0].revision!.nextAt
  tick(start); tick(start + 1000); tick(start + 3400); tick(start + 5400)
  tick(start + 7800); tick(start + 11800); tick(start + 14200)
  assert.equal(current.items[0].revision!.state, '失败')
  assert.equal(current.items[0].result, original)
  assert.equal(taskState(current), '部分失败')
  retryRevision(current, 0)
  tick(current.items[0].revision!.nextAt)
  assert.equal(taskState(current), '全部成功')
  assert.notEqual(current.items[0].result?.url, original?.url)
  assert.equal(current.items[1].result, neighbor)
  assert.match(current.events[0], /张三（演示）/)
})
test('示例初始化幂等并保留用户任务；场景可重复创建唯一ID', () => {
  const existing = setup()
  ensureExamples(); ensureExamples()
  assert.equal(preview.tasks.length, 4)
  assert.ok(preview.tasks.includes(existing))
  const first = startScenario('success'), second = startScenario('success')
  assert.notEqual(first, second)
  assert.equal(preview.tasks[0].items.length, 11)
})
