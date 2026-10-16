import { test } from 'node:test'
import assert from 'node:assert/strict'
import { createMockManagement } from '../src/api/hengxin/mock-management'
import * as guard from '../src/api/hengxin/validate-management'
import type { User } from '../src/types/hengxin'
const admin: User = { id: 'mock-super-admin', name: '超管', role: 'super_admin', status: 'active' }

test('角色修改通知共享会话且禁止降权当前超级管理员', async () => {
  let updated: User | null = null
  const api = createMockManagement(() => admin, { onUserChanged: user => { updated = user } })
  await api.saveUser({ id: 'mock-operator', role: 'designer', status: 'active' })
  assert.deepEqual(updated && (updated as User).role, 'designer')
  await assert.rejects(api.saveUser({ id: admin.id, role: 'operator', status: 'active' }), { code: 'CONFLICT' })
})

test('配置遵守并发10、超时60秒和图片10MiB边界', async () => {
  const api = createMockManagement(() => admin)
  const config = await api.getSettings()
  for (const patch of [{ concurrency: 11 }, { timeoutSeconds: 59 }, { maxUploadBytes: 10485761 }]) {
    await assert.rejects(api.saveSettings({ ...config, ...patch }), { code: 'VALIDATION' })
  }
  assert.equal((await api.saveSettings({ ...config, concurrency: 10, timeoutSeconds: 60, maxUploadBytes: 10485760 })).version, 2)
})


test('管理权限每次重新判断，读取失败可重试、停用立即拒绝', async () => {
  let user = { ...admin }
  const api = createMockManagement(() => user, { scenario: 'list-error' })
  await assert.rejects(api.getSettings(), { code: 'SIMULATED_FAILURE' })
  assert.ok(guard.settings(await api.getSettings()))
  user.role = 'design_manager'
  await assert.rejects(api.getSettings(), { code: 'FORBIDDEN' })
  user.status = 'disabled'
  await assert.rejects(api.getSettings(), { code: 'UNAUTHORIZED' })
})
