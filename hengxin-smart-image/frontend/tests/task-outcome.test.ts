import { test } from 'node:test'
import assert from 'node:assert/strict'
import { taskOutcome } from '../src/views/hengxin/task-outcome'
import type { TaskDetailData } from '../src/types/hengxin'
import { createMockService } from '../src/api/hengxin/mock'

test('返工失败不将保留旧版本计为本轮成功，重试明确原轮次范围', async () => {
  const service = createMockService({ delayMs: 0 })
  try {
    const page = await service.listTasks({ page: 1, pageSize: 10 })
    const data = await service.getTask(page.items.find(task => task.state === '待查看')!.id)
    data.task.currentRoundId = 'revision'
    data.rounds.push({ ...data.rounds[0], id: 'revision', target: 0 })
    data.slots[0].error = '失败'
    const result = taskOutcome(data)!
    assert.equal(result.total, 1)
    assert.equal(result.succeeded, 0)
    assert.equal(result.failed, 1)
    assert.match(result.retry, /第 1 张/)
    data.rounds.at(-1)!.target = null
    assert.match(taskOutcome(data)!.retry, /整套 8 张/)
    assert.equal(taskOutcome(data)!.unfinished, 7)
    data.slots[1].versions.push({ ...data.slots[1].versions[0], id: 'new', roundId: 'revision' })
    assert.equal(taskOutcome(data)!.succeeded, 1)
  } finally { service.dispose() }
})

test('当前轮次尚未同步时不虚构统计', () => {
  assert.equal(taskOutcome({ task: { currentRoundId: 'missing' }, rounds: [] } as unknown as TaskDetailData), undefined)
})
