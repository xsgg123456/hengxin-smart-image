import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createMockService } from '../src/api/hengxin/mock'
import { createHttpService } from '../src/api/hengxin/http'
import { sampleImages } from '../src/api/hengxin/fixtures'
import type { HengxinService } from '../src/types/hengxin'

const input = { mode: 'wallpaper' as const, name: '状态验收', templateId: 't1', sources: sampleImages('wallpaper', 1), note: '保留边框', sku: 'SKU-P3' }
async function settled(service: HengxinService, id: string) {
  for (let attempt = 0; attempt < 100; attempt++) {
    const detail = await service.getTask(id)
    if (!['排队中', '执行中'].includes(detail.task.state)) return detail
    await new Promise(resolve => setTimeout(resolve, 3))
  }
  throw new Error('模拟任务未终止')
}

test('首次受理仅有结果槽，完成后才展示可用结果和完整轮次', async t => {
  const service = createMockService({ delayMs: 0, stepMs: 10 }); t.after(() => service.dispose())
  const accepted = await service.createTask(input)
  const queued = await service.getTask(accepted.taskId)
  assert.equal(queued.task.images.length, 0); assert.equal(queued.slots.length, 8)
  assert.ok(queued.slots.every(s => !s.currentVersionId && !s.versions.length))
  await assert.rejects(service.archive(accepted.taskId), { code: 'CONFLICT' })
  const done = await settled(service, accepted.taskId)
  assert.equal(done.task.state, '待查看'); assert.equal(done.task.images.length, 8)
  assert.ok(done.slots.every((s, i) => s.slot === i && s.versions.length === 1 && s.currentVersionId === s.versions[0].id))
  assert.equal(done.rounds[0].id, accepted.roundId); assert.equal(done.rounds[0].note, input.note)
  assert.ok(done.rounds[0].finishedAt); assert.ok(done.rounds[0].startedAt)
})

test('单图返工失败保持旧版本、重试恢复原目标，其余槽完全不变', async t => {
  const service = createMockService({ delayMs: 0, stepMs: 3, scenario: 'revision-error' }); t.after(() => service.dispose())
  const before = await service.getTask('HX0908-001')
  await service.revise({ taskId: before.task.id, target: 1, note: '仅修改第二张' })
  await assert.rejects(service.revise({ taskId: before.task.id, target: null, note: '并发' }), { code: 'CONFLICT' })
  const failed = await settled(service, before.task.id)
  assert.equal(failed.task.state, '失败'); assert.deepEqual(failed.task.images, before.task.images)
  assert.equal(failed.slots[1].versions.length, 1); assert.match(failed.slots[1].error!, /旧结果已保留/)
  await assert.rejects(service.archive(before.task.id), { code: 'CONFLICT' })
  await service.revise({ taskId: before.task.id, target: null, note: '客户端不应覆盖', retry: true })
  const done = await settled(service, before.task.id)
  assert.equal(done.task.state, '待查看'); assert.equal(done.rounds[0].target, 1); assert.equal(done.rounds[0].note, '仅修改第二张')
  assert.equal(done.slots[1].versions.length, 2); assert.equal(done.slots[1].versions[1].version, 2)
  assert.deepEqual(done.slots[1].versions[0], before.slots[1].versions[0])
  for (let i = 0; i < 8; i++) if (i !== 1) assert.deepEqual(done.slots[i], before.slots[i])
  done.slots[1].versions[0].name = '篡改历史'
  assert.notEqual((await service.getTask(before.task.id)).slots[1].versions[0].name, '篡改历史')
})

test('部分失败保留成功图片但不可归档，首次全失败无虚构结果，重试恢复', async t => {
  for (const scenario of ['partial-result', 'execution-error'] as const) {
    const service = createMockService({ delayMs: 0, stepMs: 3, scenario }); t.after(() => service.dispose())
    const accepted = await service.createTask(input)
    const failed = await settled(service, accepted.taskId)
    assert.equal(failed.task.state, scenario === 'partial-result' ? '部分失败' : '失败')
    assert.equal(failed.task.images.length, scenario === 'partial-result' ? 7 : 0)
    await assert.rejects(service.archive(accepted.taskId), { code: 'CONFLICT' })
    await service.revise({ taskId: accepted.taskId, target: null, note: '', retry: true })
    assert.equal((await settled(service, accepted.taskId)).task.state, '待查看')
    assert.equal((await service.archive(accepted.taskId)).images.length, 8)
  }
})

test('归档按版本幂等、后续整套返工不覆盖归档、删除任务保留成品与操作者记录', async t => {
  const service = createMockService({ delayMs: 0, stepMs: 3 }); t.after(() => service.dispose())
  const old = await service.archive('HX0908-001')
  assert.equal((await service.archive('HX0908-001')).id, old.id)
  assert.equal(old.imageVersionIds.length, 8)
  await service.revise({ taskId: 'HX0908-001', target: null, note: '整套修改' })
  const done = await settled(service, 'HX0908-001')
  assert.ok(done.slots.every(s => s.versions.length === 2))
  const newer = await service.archive('HX0908-001')
  assert.notEqual(newer.id, old.id); assert.deepEqual(await service.getArchive(old.id), old)
  const receipt = await service.deleteTask('HX0908-001')
  assert.equal(receipt.operatorId, 'mock-operator'); assert.ok(receipt.deletedAt)
  assert.deepEqual((await service.getWorkspace()).deletions, [receipt])
  await assert.rejects(service.getTask('HX0908-001'), { code: 'NOT_FOUND' })
  assert.deepEqual(await service.getArchive(old.id), old)
  await service.deleteArchive(newer.id)
  assert.equal((await service.getWorkspace()).deletions?.at(-1)?.resourceType, 'archive')
  assert.equal((await service.getWorkspace()).deletions?.at(-1)?.operatorId, 'mock-operator')
  await assert.rejects(service.getArchive(newer.id), { code: 'NOT_FOUND' })
  assert.deepEqual(await service.getArchive(old.id), old)
  await service.deleteTemplate('t1')
  assert.equal((await service.getWorkspace()).deletions?.at(-1)?.resourceType, 'template')
  assert.equal((await service.getWorkspace()).deletions?.at(-1)?.operatorId, 'mock-operator')
})

test('删除运行任务不复活；分页/搜索SKU/异常筛选与归档写失败重试', async t => {
  const service = createMockService({ delayMs: 0, stepMs: 3, scenario: 'archive-error' }); t.after(() => service.dispose())
  await assert.rejects(service.archive('HX0908-001'), { code: 'SIMULATED_FAILURE' })
  await service.archive('HX0908-001')
  const accepted = await service.createTask(input)
  assert.equal((await service.listTasks({ page: 1, pageSize: 12, search: 'SKU-P3' })).total, 1)
  await service.deleteTask(accepted.taskId)
  await new Promise(resolve => setTimeout(resolve, 25))
  await assert.rejects(service.getTask(accepted.taskId), { code: 'NOT_FOUND' })
  assert.equal((await service.listTasks({ page: 1, pageSize: 1 })).items.length, 1)
  assert.equal((await service.listTasks({ page: 1, pageSize: 12, state: 'error' })).total, 1)
  assert.equal((await service.listArchives({ page: 1, pageSize: 12, search: '秋日' })).total, 1)
  await assert.rejects(service.listTasks({ page: 0, pageSize: 12 }), { code: 'VALIDATION' })
})

test('任务HTTP新接口结构守卫、路径编码及成功读回', async t => {
  const service = createMockService({ delayMs: 0 }); t.after(() => service.dispose())
  const detail = await service.getTask('HX0908-001')
  const respond = (body: unknown) => createHttpService('/api/v1', async () => new Response(JSON.stringify(body), { headers: { 'content-type': 'application/json' } }))
  assert.deepEqual(await respond(detail).getTask(detail.task.id), detail)
  await assert.rejects(respond({ ...detail, slots: [{ slot: 0, versions: [], currentVersionId: 'missing', error: null }] }).getTask('x'), { code: 'INVALID_RESPONSE' })
  await assert.rejects(respond({}).listTasks({ page: 1, pageSize: 12 }), { code: 'INVALID_RESPONSE' })
  await assert.rejects(respond({}).listArchives({ page: 1, pageSize: 12 }), { code: 'INVALID_RESPONSE' })
  await assert.rejects(respond({}).deleteTask('x'), { code: 'INVALID_RESPONSE' })
  const http = createHttpService('/api/v1', async (url, init) => {
    assert.equal(url, '/api/v1/tasks/a%2Fb'); assert.equal(init?.method, 'DELETE')
    return new Response(JSON.stringify({ id: 'a/b', operatorId: 'u', deletedAt: '2026-09-09' }), { headers: { 'content-type': 'application/json' } })
  })
  assert.equal((await http.deleteTask('a/b')).operatorId, 'u')
})
