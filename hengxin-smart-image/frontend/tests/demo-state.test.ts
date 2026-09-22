import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createMockService } from '../src/api/hengxin/mock'
import { demoImages } from '../src/api/hengxin/fixtures'
const user = { id: 'mock-super-admin', name: '超管', role: 'super_admin' as const, status: 'active' as const }
const pause = (ms: number) => new Promise(resolve => setTimeout(resolve, ms))
const waitFor = async <T>(read: () => Promise<T>, done: (value: T) => boolean, timeoutMs = 1000): Promise<T> => {
  const deadline = Date.now() + timeoutMs
  while (Date.now() < deadline) {
    const value = await read()
    if (done(value)) return value
    await pause(10)
  }
  throw new Error(`等待 Demo 状态超时（${timeoutMs}ms）`)
}

test('Demo 刷新恢复原轮次，保留返工版本、归档和幂等受理', async t => {
  const first = createMockService({ demo: true, user, delayMs: 0, stepMs: 1000 })
  const input = { mode: 'wallpaper' as const, name: '持久化任务', templateId: 't1', sources: demoImages('wallpaper', 1), note: '' }
  const receipt = await first.createTask(input, 'same-request')
  const state = first.snapshot(); first.dispose()
  const restored = createMockService({ demo: true, user, snapshot: state, delayMs: 0, stepMs: 5 })
  t.after(() => restored.dispose())
  assert.deepEqual(await restored.createTask(input, 'same-request'), receipt)
  const initial = await waitFor(() => restored.getTask(receipt.taskId), value => value.task.state === '待查看')
  assert.equal(initial.rounds.length, 1)
  assert.equal(initial.rounds[0].id, receipt.roundId)
  assert.equal(initial.task.state, '待查看')
  assert.equal(initial.slots.length, 8)
  const revision = await restored.revise({ taskId: receipt.taskId, target: 0, note: '仅改首图' }, 'revision')
  const second = await waitFor(() => restored.getTask(receipt.taskId), value => value.slots[0].versions.length === 2)
  assert.equal(second.slots[0].versions.length, 2)
  assert.equal(second.slots[1].versions.length, 1)
  const archived = await restored.archive(receipt.taskId)
  const final = createMockService({ demo: true, user, snapshot: restored.snapshot(), delayMs: 0 })
  t.after(() => final.dispose())
  assert.deepEqual(await final.getTask(receipt.taskId), { ...second, task: { ...second.task, archived: true } })
  assert.equal((await final.archive(receipt.taskId)).id, archived.id)
  assert.equal((await final.revise({ taskId: receipt.taskId, target: 0, note: '仅改首图' }, 'revision')).roundId, revision.roundId)
})

test('Demo 模板历史、默认配置、角色修改在快照恢复后保持一致', async t => {
  const first = createMockService({ demo: true, user, delayMs: 0, installMs: 10 })
  t.after(() => first.dispose())
  const template = await first.saveTemplate({ name: '演示模板', mode: 'wallpaper', images: demoImages('wallpaper', 2), active: true, notes: '', skillVersionId: null })
  await first.saveTemplate({ ...template, expectedVersion: template.version, images: [...template.images].reverse(), notes: '调整顺序' })
  const defaults = await first.getSkillDefaults()
  await first.saveSkillDefaults({ ...defaults, text: null })
  await first.saveUser({ id: 'mock-operator', role: 'designer', status: 'active' })
  const restored = createMockService({ demo: true, user: { ...user, id: 'mock-operator', role: 'operator' }, snapshot: first.snapshot(), delayMs: 0 })
  t.after(() => restored.dispose())
  assert.equal((await restored.getUser()).role, 'designer')
  assert.equal((await restored.getTemplateVersions(template.id)).length, 2)
  assert.equal((await restored.listSkills('text'))[0].isDefault, false)
  await assert.rejects(restored.getSettings(), { code: 'FORBIDDEN' })
})

test('Demo 失败场景刷新继续重试，不丢掉已成功槽位', async t => {
  const first = createMockService({ demo: true, user, delayMs: 0, stepMs: 5, scenario: 'partial-result' })
  const receipt = await first.createTask({ mode: 'text', name: '部分失败', sources: demoImages('text', 2), note: '修改文案' })
  await pause(60)
  const failed = await first.getTask(receipt.taskId)
  assert.equal(failed.task.state, '部分失败')
  const restored = createMockService({ demo: true, user, delayMs: 0, stepMs: 5, scenario: 'partial-result', snapshot: first.snapshot() })
  first.dispose(); t.after(() => restored.dispose())
  await restored.revise({ taskId: receipt.taskId, target: null, note: '', retry: true, sourceRoundId: receipt.roundId })
  await pause(60)
  assert.equal((await restored.getTask(receipt.taskId)).task.state, '待查看')
})

test('Demo Skill 目录刷新保留移除登记，并能从文件源重新发现', async t => {
  const first = createMockService({ demo: true, user, delayMs: 0 })
  t.after(() => first.dispose())
  const defaults = await first.getSkillDefaults()
  await first.saveSkillDefaults({ ...defaults, wallpaper: null })
  await first.deleteTemplate('t1')
  await first.deleteTemplate('t2')
  await first.removeCatalogSkill('mock-wallpaper-1')
  const removed = first.snapshot()
  const restored = createMockService({ demo: true, user, snapshot: removed, delayMs: 0, installMs: 10 })
  t.after(() => restored.dispose())
  assert.equal((await restored.listManagedCatalog()).some(skill => skill.id === 'mock-wallpaper-1'), false)
  await restored.syncSkillCatalog()
  await pause(20)
  assert.equal((await restored.getSkillSync()).status, 'succeeded')
  const rediscovered = (await restored.listManagedCatalog()).find(skill => skill.id === 'mock-wallpaper-1')
  assert.equal(rediscovered?.isDefault, false)
})

test('Demo 未知 Skill 选择类型后刷新不回退', async t => {
  const first = createMockService({ demo: true, user, managementScenario: 'unknown', delayMs: 0, installMs: 10 })
  t.after(() => first.dispose())
  await first.setCatalogMode('mock-unknown', 'wallpaper')
  await pause(20)
  const restored = createMockService({ demo: true, user, managementScenario: 'unknown', snapshot: first.snapshot(), delayMs: 0, installMs: 10 })
  t.after(() => restored.dispose())
  assert.equal((await restored.listManagedCatalog()).find(skill => skill.id === 'mock-unknown')?.mode, 'wallpaper')
})
