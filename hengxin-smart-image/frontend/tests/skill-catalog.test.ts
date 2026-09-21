import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createMockManagement } from '../src/api/hengxin/mock-management'
import { createMockService } from '../src/api/hengxin/mock'
import { createHttpManagement } from '../src/api/management'
import * as guard from '../src/api/hengxin/validate-skill-catalog'
import type { SkillVersion, User, Workspace } from '../src/types/hengxin'
const admin: User = { id: 'admin', name: '管理员', role: 'super_admin', status: 'active' }
const seed = (): SkillVersion[] => [{ id: 'stable-id', name: '技能', mode: 'text', version: '1.0.0', checksum: 'old', status: 'available', isDefault: false }]
const db = (): Workspace => ({ templates: [], tasks: [], archives: [] })
test('同步互斥、描述保留、手动停用不恢复，移除后重新发现', async () => {
  const skills = seed(), api = createMockManagement(db(), skills, () => admin, { installMs: 100 })
  const row = (await api.listManagedCatalog())[0]
  assert.ok(row.description.length > 10)
  await api.setCatalogStatus(row.id, 'disabled')
  const first = await api.syncSkillCatalog(), second = await api.syncSkillCatalog()
  assert.equal(first.jobId, second.jobId)
  await assert.rejects(api.removeCatalogSkill(row.id), { code: 'CONFLICT' })
  await new Promise(resolve => setTimeout(resolve, 110))
  assert.equal((await api.getSkillSync()).status, 'succeeded')
  assert.equal((await api.listManagedCatalog())[0].status, 'disabled')
  assert.deepEqual(await api.listSkillCatalog(), [])
  await api.setCatalogStatus(row.id, 'available')
  await api.removeCatalogSkill(row.id)
  assert.deepEqual(await api.listManagedCatalog(), [])
  await api.syncSkillCatalog(); await new Promise(resolve => setTimeout(resolve, 110))
  assert.equal((await api.listSkillCatalog())[0].id, row.id)
})
test('类型未知需显式选择；失败同步显示异常，不能启用或作为默认', async () => {
  const api = createMockManagement(db(), seed(), () => admin, { scenario: 'unknown', installMs: 0 })
  const unknown = (await api.listManagedCatalog()).find(s => !s.mode)!
  assert.equal(unknown.status, 'needs_type')
  await assert.rejects(api.setCatalogStatus(unknown.id, 'available'), { code: 'CONFLICT' })
  await api.setCatalogMode(unknown.id, 'wallpaper')
  assert.equal((await api.listSkillCatalog('wallpaper'))[0].id, unknown.id)
  const failure = createMockManagement(db(), seed(), () => admin, { scenario: 'install-error', installMs: 0 })
  await failure.syncSkillCatalog()
  assert.equal((await failure.getSkillSync()).status, 'failed')
  assert.ok((await failure.listManagedCatalog())[0].error)
  await assert.rejects(failure.saveCatalogDefaults({ text: 'stable-id', wallpaper: null, product: null }), { code: 'VALIDATION' })
  await failure.syncSkillCatalog()
  assert.equal((await failure.getSkillSync()).status, 'succeeded')
  assert.equal((await failure.listManagedCatalog())[0].status, 'available')
})
test('默认和模板引用保护、权限变化、空态和请求失败', async () => {
  let user = admin
  const api = createMockManagement(db(), seed(), () => user)
  await api.saveCatalogDefaults({ text: 'stable-id', wallpaper: null, product: null })
  assert.equal((await api.listManagedCatalog())[0].isDefault, true)
  await assert.rejects(api.removeCatalogSkill('stable-id'), { code: 'CONFLICT' })
  user = { ...admin, role: 'operator' }
  await assert.rejects(api.syncSkillCatalog(), { code: 'FORBIDDEN' })
  await assert.rejects(api.listManagedCatalog(), { code: 'FORBIDDEN' })
  assert.equal((await api.listSkillCatalog()).length, 1)
  assert.deepEqual(await createMockManagement(db(), seed(), () => admin, { scenario: 'empty' }).listManagedCatalog(), [])
  const failure = createMockManagement(db(), seed(), () => admin, { scenario: 'list-error' })
  await assert.rejects(failure.listManagedCatalog(), { code: 'SIMULATED_FAILURE' })
  assert.equal((await failure.listManagedCatalog()).length, 1)
})
test('模板按Skill身份绑定，同步替换内容但不改已提交任务快照', async t => {
  const api = createMockService({ user: admin, delayMs: 0, stepMs: 100000 })
  t.after(() => api.dispose())
  const row = (await api.listSkillCatalog('text'))[0]
  const picture = await api.uploadFile(new File(['image'], 'a.png', { type: 'image/png' }))
  const receipt = await api.createTask({ name: '冻结', mode: 'text', note: '修改文字', skillVersionId: row.id, sources: [picture] })
  const before = (await api.getTask(receipt.taskId)).task.skillSnapshot
  await api.syncSkillCatalog()
  await new Promise(resolve => setTimeout(resolve, 1250))
  assert.equal((await api.getSkillSync()).status, 'succeeded')
  assert.notEqual((await api.listSkills('text'))[0].checksum, before?.checksum)
  await api.setCatalogStatus(row.id, 'disabled')
  assert.deepEqual((await api.getTask(receipt.taskId)).task.skillSnapshot, before)
  await assert.rejects(api.createTask({ name: '不能静默替换', mode: 'text', note: '修改文字', skillVersionId: row.id, sources: [picture] }), { code: 'SKILL_UNAVAILABLE' })
  const defaults = await api.getCatalogDefaults()
  await api.saveCatalogDefaults({ ...defaults, text: null })
  await api.removeCatalogSkill(row.id)
  assert.deepEqual((await api.getTask(receipt.taskId)).task.skillSnapshot, before)
  const bound = (await api.listSkillCatalog('wallpaper'))[0]
  await api.saveCatalogDefaults({ ...defaults, text: null, wallpaper: null })
  await assert.rejects(api.removeCatalogSkill(bound.id), { code: 'CONFLICT' })
})
test('目录HTTP契约校验、路径编码和错误保真', async () => {
  const row = (await createMockManagement(db(), seed(), () => admin).listManagedCatalog())[0]
  assert.ok(guard.catalogList([row])); assert.equal(guard.catalogList([{ ...row, description: null }]), false)
  assert.ok(guard.syncState({ jobId: null, status: 'idle', error: null }))
  assert.equal(guard.syncAccepted({ jobId: null, status: 'queued' }), false)
  const paths: string[] = []
  const api = createHttpManagement('/api/v1', async (url, options) => {
    paths.push(`${options?.method} ${url}`)
    return new Response(JSON.stringify(String(url).endsWith('/mode') ? row : [row]), { headers: { 'content-type': 'application/json' } })
  })
  await api.listSkillCatalog('text'); await api.setCatalogMode('a/b', 'text')
  assert.equal(guard.catalogSkill({ ...row, mode: ['text'] }), false)
  assert.deepEqual(paths, ['GET /api/v1/skill-catalog?mode=text', 'PUT /api/v1/management/skill-catalog/a%2Fb/mode'])
  const bad = createHttpManagement('', async () => new Response('{}', { headers: { 'content-type': 'application/json' } }))
  await assert.rejects(bad.listManagedCatalog(), { code: 'INVALID_RESPONSE' })
})
