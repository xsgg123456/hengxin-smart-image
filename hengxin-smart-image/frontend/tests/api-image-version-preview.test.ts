import { test } from 'node:test'
import assert from 'node:assert/strict'
import { preview, startScenario, startVersionExample, getVersions, restoreVersion, requestRevision, tick } from '../src/views/hengxin/api-image-edits/preview-state'

test('初始成功版本记录实际生成时间而非任务受理时间', () => {
  startScenario('success'); preview.paused = false
  const task = preview.tasks[0]
  preview.tasks = [task]
  task.created = '2000/1/1 00:00:00'
  tick(0); tick(2400)
  assert.equal(task.items[0].state, '成功')
  assert.notEqual(getVersions(task, 0)[0].created, task.created)
})

test('历史保留，恢复后再修改递增V4且基于V1，其他图片不变', () => {
  startVersionExample(); preview.paused = false
  const task = preview.tasks[0], item = task.items[0], neighbor = task.items[1].result
  const history = JSON.stringify(getVersions(task, 0))
  restoreVersion(task, 0, 1)
  assert.equal(item.result?.version, 1)
  assert.equal(JSON.stringify(getVersions(task, 0)), history)
  const annotation = { name: '标注.png', url: '/demo-images/sample-4.jpg' }
  requestRevision(task, 0, '调整边缘', annotation)
  assert.equal(item.revision?.base.version, 1)
  assert.throws(() => restoreVersion(task, 0, 2), /等待/)
  tick(item.revision!.nextAt)
  assert.equal(item.result?.version, 4)
  const versions = getVersions(task, 0)
  assert.equal(JSON.stringify(versions.slice(0, 3)), history)
  assert.equal(versions[3].baseVersion, 1)
  assert.equal(versions[3].text, '调整边缘')
  assert.deepEqual(versions[3].annotation, annotation)
  assert.equal(task.items[1].result, neighbor)
  restoreVersion(task, 0, 2)
  assert.equal(item.result?.url, versions[1].picture.url)
  const count = task.events.length
  restoreVersion(task, 0, 2)
  assert.equal(task.events.length, count)
  assert.throws(() => restoreVersion(task, 0, 99), /不存在/)
})

test('失败修改不新增成功历史且保留当前版本；初始单版可正常查看', () => {
  startVersionExample(); preview.paused = false
  const task = preview.tasks[0], item = task.items[0]
  assert.equal(getVersions(task, 1).length, 1)
  assert.deepEqual(getVersions(task, 99), [])
  const old = item.result, history = JSON.stringify(getVersions(task, 0))
  requestRevision(task, 0, '失败示例', undefined, 'partial')
  for (let i = 0; i < 7; i++) tick(item.revision!.nextAt)
  assert.equal(item.revision?.state, '失败')
  assert.equal(item.result, old)
  assert.equal(JSON.stringify(getVersions(task, 0)), history)
  assert.throws(() => restoreVersion(task, 0, 1), /等待/)
})
