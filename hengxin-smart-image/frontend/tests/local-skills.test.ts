import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createHttpManagement } from '../src/api/management'
import { createMockManagement } from '../src/api/hengxin/mock-management'
import { createFixtures } from '../src/api/hengxin/fixtures'
import { managedSkill } from '../src/api/hengxin/validate-management'
import type { ManagedSkill, SkillRegistration } from '../src/types/management'
import type { SkillVersion, User } from '../src/types/hengxin'

const admin: User = { id: 'admin', name: '超管', role: 'super_admin', status: 'active' }
const input: SkillRegistration = { name: 'replace-text', version: '2.0.0', mode: 'text', description: '' }
const row: ManagedSkill = { ...input, id: 'skill/id', sourceType: 'local', checksum: '', status: 'pending',
  isDefault: false, installedAt: null, node: null, updatedAt: '2026-09-17T00:00:00Z', error: null, referenced: false }

test('登记、检查与移除 HTTP 契约，路径编码、凭据和 204', async () => {
  const requests: { url: string; options?: RequestInit }[] = []
  const api = createHttpManagement('/api/v1', async (url, options) => {
    requests.push({ url: String(url), options })
    return options?.method === 'DELETE' ? new Response(null, { status: 204 })
      : new Response(JSON.stringify({ ...row, status: String(url).endsWith('/check') ? 'checking' : 'pending' }), { headers: { 'content-type': 'application/json' } })
  })
  assert.equal((await api.registerSkill(input)).status, 'pending')
  assert.equal((await api.checkSkill(row.id)).status, 'checking')
  await api.removeSkill(row.id)
  assert.deepEqual(requests.map(r => [r.url, r.options?.method]), [
    ['/api/v1/management/skills/register', 'POST'], ['/api/v1/management/skills/skill%2Fid/check', 'POST'], ['/api/v1/management/skills/skill%2Fid', 'DELETE']
  ])
  assert.deepEqual(JSON.parse(String(requests[0].options?.body)), input)
  assert.ok(requests.every(r => r.options?.credentials === 'include'))
})

test('HTTP 检查冲突、移除引用冲突及错误来源响应不能伪装成功', async () => {
  const api = createHttpManagement('/api', async () => new Response(JSON.stringify({ code: 'CONFLICT', message: '版本被引用' }), { status: 409, headers: { 'content-type': 'application/json' } }))
  await assert.rejects(api.checkSkill('id'), /版本被引用/)
  await assert.rejects(api.removeSkill('id'), /版本被引用/)
  for (const status of ['pending', 'checking', 'verified', 'invalid', 'available', 'disabled', 'uploaded', 'installing', 'failed']) assert.equal(managedSkill({ ...row, status }), true)
  assert.equal(managedSkill({ ...row, sourceType: 'remote' }), false)
  const malformed = createHttpManagement('/api', async () => new Response(JSON.stringify({ ...row, sourceType: null }), { headers: { 'content-type': 'application/json' } }))
  await assert.rejects(malformed.registerSkill(input), { code: 'INVALID_RESPONSE' })
})

test('本地登记重复、检查在途、任务模板引用与默认绑定均阻止移除，历史 ZIP 保留', async () => {
  const db = createFixtures(), skills: SkillVersion[] = [{ id: 'legacy', name: 'legacy', version: '1.0.0', mode: 'text', checksum: 'zip-checksum', isDefault: false, status: 'available' }]
  const api = createMockManagement(db, skills, () => admin, { installMs: 60000 })
  assert.equal((await api.listManagedSkills())[0].sourceType, 'zip')
  await assert.rejects(api.removeSkill('legacy'), { code: 'CONFLICT' })
  const local = await api.registerSkill(input)
  await assert.rejects(api.registerSkill(input), { code: 'CONFLICT' })
  await api.checkSkill(local.id)
  await assert.rejects(api.checkSkill(local.id), { code: 'CONFLICT' })
  await assert.rejects(api.removeSkill(local.id), { code: 'CONFLICT' })
  const next = await api.registerSkill({ ...input, version: '2.0.1' })
  const stored = skills.find(s => s.id === next.id)!
  stored.isDefault = true
  await assert.rejects(api.removeSkill(next.id), { code: 'CONFLICT' })
  stored.isDefault = false
  db.tasks[0].skillVersionId = next.id
  await assert.rejects(api.removeSkill(next.id), { code: 'CONFLICT' })
  db.tasks[0].skillVersionId = 'legacy'
  db.templates[0].skillVersionId = next.id
  await assert.rejects(api.removeSkill(next.id), { code: 'CONFLICT' })
  db.templates[0].skillVersionId = 'legacy'
  await api.removeSkill(next.id)
  assert.ok(!(await api.listManagedSkills()).some(s => s.id === next.id))
})

test('重新检查撤下已启用状态，校验通过仍需显式启用且校验值不覆盖', async () => {
  const api = createMockManagement(createFixtures(), [], () => admin, { installMs: 0 })
  const local = await api.registerSkill(input)
  await api.checkSkill(local.id)
  const verified = (await api.listManagedSkills())[0]
  assert.equal(verified.status, 'verified')
  await api.setSkillStatus(local.id, 'available')
  assert.equal((await api.checkSkill(local.id)).status, 'checking')
  const again = (await api.listManagedSkills())[0]
  assert.equal(again.status, 'verified'); assert.equal(again.checksum, verified.checksum)
})

test('非超管登记检查移除均拒绝，保存故障不产生登记', async () => {
  const api = createMockManagement(createFixtures(), [], () => ({ ...admin, role: 'operator' }))
  await assert.rejects(api.registerSkill(input), { code: 'FORBIDDEN' })
  await assert.rejects(api.checkSkill('id'), { code: 'FORBIDDEN' })
  await assert.rejects(api.removeSkill('id'), { code: 'FORBIDDEN' })
  const faulty = createMockManagement(createFixtures(), [], () => admin, { scenario: 'save-error' })
  await assert.rejects(faulty.registerSkill(input), { code: 'SIMULATED_FAILURE' })
  assert.deepEqual(await faulty.listManagedSkills(), [])
})
