import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createMockService } from '../src/api/hengxin/mock'
import { taskPage } from '../src/api/hengxin/validate'

test('Demo我的任务按身份过滤全部集合再分页，统计保持范围且兼容旧快照', async () => {
  const seed = createMockService({ delayMs: 0 })
  const snapshot = seed.snapshot()
  seed.dispose()
  snapshot.workspace.tasks = Array.from({ length: 17 }, (_, i) => ({ ...snapshot.workspace.tasks[0], id: `task-${i}`, ownerId: i % 2 ? 'me' : 'other', ownerName: undefined, currentRoundId: `r-${i}` }))
  snapshot.slots = []; snapshot.rounds = []
  const service = createMockService({ snapshot, delayMs: 0, user: { id: 'me', name: '当前同事', role: 'operator', status: 'active' } })
  try {
    const pages = await Promise.all([1, 2].map(page => service.listTasks({ page, pageSize: 5, scope: 'mine' })))
    assert.equal(pages[0].total, 8)
    assert.equal(pages[0].stats.total, 8)
    assert.equal(pages[1].items.length, 3)
    assert.ok(pages.flatMap(page => page.items).every(task => task.ownerId === 'me' && task.ownerName === '当前同事'))
    const all = await service.listTasks({ page: 1, pageSize: 20 })
    assert.equal(all.total, 17)
    assert.ok(taskPage(all))
    const corrupted = structuredClone(all)
    Object.assign(corrupted.items[0], { ownerName: 123 })
    assert.equal(taskPage(corrupted), false)
    assert.equal((await service.getTask('task-0')).task.ownerId, 'other')
  } finally { service.dispose() }
})
