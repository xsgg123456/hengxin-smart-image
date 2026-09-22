import { test } from 'node:test'
import assert from 'node:assert/strict'
import { preview, tick, taskState, retryFailed, type EditTask, type Scenario } from '../src/views/hengxin/api-image-edits/preview-state'
function task(scenario: Scenario): EditTask {
  return { id: 'test', name: 'test', prompt: 'test', created: '', material: { name: 'm', url: 'm' }, scenario, events: [],
    items: Array.from({ length: 4 }, (_, i) => ({ source: { name: `${i}`, url: `${i}` }, state: '等待处理', retries: 0, nextAt: 0 })) }
}
test('预览全局串行：后一项和另一任务必须等待当前项结束', () => {
  const first = task('success'), second = task('success')
  preview.tasks = [second, first]; preview.paused = false
  tick(1000)
  assert.equal(preview.tasks[1].items[0].state, '处理中')
  assert.equal(preview.tasks[1].items[1].state, '等待处理')
  assert.equal(preview.tasks[0].items[0].state, '等待处理')
  tick(3400); tick(3401)
  assert.equal(preview.tasks[1].items[0].state, '成功')
  assert.equal(preview.tasks[1].items[1].state, '处理中')
})
test('三次退避为1/2/4秒，用尽后继续下一张；手动重试保留成功图片', () => {
  preview.tasks = [task('partial')]; preview.paused = false
  const current = preview.tasks[0]
  tick(0); tick(2400); tick(2500); tick(4900); tick(5000)
  tick(7400)
  assert.equal(current.items[2].nextAt, 8400)
  tick(8400); tick(10800)
  assert.equal(current.items[2].nextAt, 12800)
  tick(12800); tick(15200)
  assert.equal(current.items[2].nextAt, 19200)
  tick(19200); tick(21600)
  assert.equal(current.items[2].state, '失败')
  tick(21700); tick(24100)
  assert.equal(taskState(current), '部分失败')
  const oldResult = current.items[0].result
  retryFailed(current); tick(25000); tick(27400)
  assert.equal(taskState(current), '全部成功')
  assert.equal(current.items[0].result, oldResult)
  assert.equal(current.items[2].result?.name, '示例结果-3.jpg')
})
test('暂停演示不推进状态', () => {
  preview.tasks = [task('retry')]; preview.paused = true
  tick(10000)
  assert.equal(preview.tasks[0].items[0].state, '等待处理')
  preview.paused = false
})
