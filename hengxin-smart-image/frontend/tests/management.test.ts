import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createMockManagement } from '../src/api/hengxin/mock-management'
import { buildUsage } from '../src/api/hengxin/mock-management-usage'
import { createRequest } from '../src/api/hengxin/http'
import * as guard from '../src/api/hengxin/validate-management'
import { createFixtures } from '../src/api/hengxin/fixtures'
import type { User, SkillVersion } from '../src/types/hengxin'
import type { UsageAttempt } from '../src/types/management'
const admin: User = { id: 'mock-super-admin', name: '超管', role: 'super_admin', status: 'active' }
const skills = (): SkillVersion[] => ['wallpaper', 'product', 'text'].map(mode => ({ id: mode, mode: mode as SkillVersion['mode'], name: mode, version: '1.0.0', checksum: 'mock', isDefault: true, status: 'available' }))

test('管理权限每次重新判断：主管无维护权限，个人不能读取他人统计，停用立即拒绝', async () => {
  let user = { ...admin }
  const api = createMockManagement(createFixtures(), skills(), () => user)
  assert.ok((await api.listUsers({ page: 1, pageSize: 20 })).total)
  user = { ...user, role: 'design_manager' }
  assert.equal((await api.getUsage({})).scope, 'all')
  assert.equal((await api.getMonitor()).detail, null)
  await assert.rejects(api.getSettings(), { code: 'FORBIDDEN' })
  await assert.rejects(api.listManagedSkills(), { code: 'FORBIDDEN' })
  user = { ...user, role: 'operator' }
  await assert.rejects(api.getUsage({ userId: 'other' }), { code: 'FORBIDDEN' })
  assert.equal((await api.getUsage({})).scope, 'personal')
  user.status = 'disabled'
  await assert.rejects(api.getUsage({}), { code: 'UNAUTHORIZED' })
})

test('统计跨日、操作者、去重、已结束分母和缺失 usage 保真', () => {
  const db = createFixtures(); db.tasks = []
  const base: UsageAttempt = { id: 'one', taskId: 'task', taskName: '任务', creatorId: 'creator', operatorId: 'actor', operatorName: '操作者', mode: 'text', kind: 'single', startedAt: '2026-09-08T16:01:00Z', finishedAt: '2026-09-09T00:00:00Z', state: 'success', outputImages: 1, queueSeconds: 1, durationSeconds: 2, usage: { inputTokens: 10, outputTokens: 2 } }
  const report = buildUsage(db, [base, base, { ...base, id: 'two', state: 'partial', usage: null }, { ...base, id: 'three', state: 'running', finishedAt: null, durationSeconds: null }], admin, { from: '2026-09-09', to: '2026-09-09', userId: 'actor' }, [])
  assert.equal(report.summary.attempts, 3); assert.equal(report.summary.successRate, .5)
  assert.equal(report.summary.inputTokens, null); assert.equal(report.rows[0].date, '2026-09-09')
  assert.equal(report.summary.tasks, 0)
  assert.equal(buildUsage(db, [base], admin, { to: '2026-09-08' }, []).summary.attempts, 0)
})

test('Skill 异步安装失败保留旧版，成功才可发布，设置切换同源版本', async () => {
  const shared = skills()
  const api = createMockManagement(createFixtures(), shared, () => admin, { installMs: 0, scenario: 'install-error' })
  const file = new File([new Uint8Array([80, 75, 3, 4, 0])], 'skill.zip')
  const uploaded = await api.uploadSkill(file, 'text', '2.0.0')
  assert.equal(uploaded.checksum.length, 64); assert.equal(uploaded.status, 'uploaded')
  await assert.rejects(api.setSkillStatus(uploaded.id, 'available'), { code: 'CONFLICT' })
  assert.equal((await api.installSkill(uploaded.id)).status, 'installing')
  assert.equal((await api.listManagedSkills()).find(s => s.id === uploaded.id)?.status, 'failed')
  assert.equal(shared.find(s => s.id === 'text')?.status, 'available')
  const ok = createMockManagement(createFixtures(), shared, () => admin, { installMs: 0 })
  await ok.installSkill(uploaded.id)
  assert.equal((await ok.listManagedSkills()).find(s => s.id === uploaded.id)?.status, 'available')
  const config = await ok.getSettings()
  const saved = await ok.saveSettings({ ...config, defaultSkillIds: { ...config.defaultSkillIds, text: uploaded.id } })
  assert.equal(saved.version, 2); assert.equal(shared.find(s => s.id === uploaded.id)?.isDefault, true)
  assert.equal(saved.audit[0].operatorId, admin.id)
  await assert.rejects(ok.saveSettings(config), { code: 'CONFLICT' })
  await assert.rejects(ok.saveSettings({ ...saved, concurrency: 999 }), { code: 'VALIDATION' })
})

test('空、未知、空闲与请求失败可复现，HTTP 拒绝畸形管理响应', async () => {
  const db = createFixtures()
  const empty = createMockManagement(db, skills(), () => admin, { scenario: 'empty' })
  assert.equal((await empty.getUsage({})).summary.successRate, null)
  for (const scenario of ['idle', 'unknown'] as const) {
    const report = await createMockManagement(db, skills(), () => admin, { scenario }).getMonitor()
    assert.equal(report.state, scenario); assert.ok(guard.monitor(report))
  }
  const faulty = createMockManagement(db, skills(), () => admin, { scenario: 'list-error' })
  await assert.rejects(faulty.getSettings(), { code: 'SIMULATED_FAILURE' })
  assert.ok(guard.settings(await faulty.getSettings()))
  const request = createRequest('/api', async () => new Response(JSON.stringify({ detail: {}, state: 'idle' }), { headers: { 'content-type': 'application/json' } }))
  await assert.rejects(request('/management/monitor', guard.monitor), { code: 'INVALID_RESPONSE' })
  assert.equal(guard.usage({ summary: {} }), false)
  assert.ok(guard.usage(await empty.getUsage({})))
})


test('角色修改通知共享会话；非法日期和安装包拒绝且没有副作用', async () => {
  let updated: User | null = null
  const shared = skills()
  const api = createMockManagement(createFixtures(), shared, () => admin, { onUserChanged: user => { updated = user } })
  await api.saveUser({ id: 'mock-operator', role: 'designer', status: 'active' })
  assert.deepEqual(updated && (updated as User).role, 'designer')
  await assert.rejects(api.saveUser({ id: admin.id, role: 'operator', status: 'active' }), { code: 'CONFLICT' })
  await assert.rejects(api.getUsage({ from: '2026-02-30' }), { code: 'VALIDATION' })
  await assert.rejects(api.uploadSkill(new File(['invalid'], 'bad.zip'), 'text', '3.0.0'), { code: 'VALIDATION' })
  assert.equal(shared.length, 3)
})

test('配置遵守并发10、超时60秒和图片10MiB边界', async () => {
  const api = createMockManagement(createFixtures(), skills(), () => admin)
  const config = await api.getSettings()
  for (const patch of [{ concurrency: 11 }, { timeoutSeconds: 59 }, { maxUploadBytes: 10485761 }]) {
    await assert.rejects(api.saveSettings({ ...config, ...patch }), { code: 'VALIDATION' })
  }
  assert.equal((await api.saveSettings({ ...config, concurrency: 10, timeoutSeconds: 60, maxUploadBytes: 10485760 })).version, 2)
})

test('安装故障首次失败后可重试；统计使用实时 attempt getter', async () => {
  let reads = 0
  const api = createMockManagement(createFixtures(), skills(), () => admin, { installMs: 0, scenario: 'install-error', getAttempts: () => { reads++; return [] } })
  await api.getUsage({}); await api.getUsage({}); assert.equal(reads, 2)
  const uploaded = await api.uploadSkill(new File([new Uint8Array([80, 75, 3, 4])], 'ok.zip'), 'text', '4.0.0')
  await api.installSkill(uploaded.id)
  assert.equal((await api.listManagedSkills()).find(s => s.id === uploaded.id)?.status, 'failed')
  await api.installSkill(uploaded.id)
  const first = (await api.listManagedSkills()).find(s => s.id === uploaded.id)!
  const second = (await api.listManagedSkills()).find(s => s.id === uploaded.id)!
  assert.equal(first.status, 'available'); assert.equal(first.installedAt, second.installedAt)
})
