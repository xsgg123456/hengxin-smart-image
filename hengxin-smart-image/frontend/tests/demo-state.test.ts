import test from 'node:test'
import assert from 'node:assert/strict'
import { createMockService } from '../src/api/hengxin/mock'
import { migrateDemoState } from '../src/api/hengxin/demo-state'
import { getPreviewUser } from '../src/api/hengxin/session'

test('旧Demo迁移丢弃业务快照与默认Skill，保留用户和系统配置', async () => {
  const user = getPreviewUser('?role=super_admin')
  const first = createMockService({ user, delayMs: 0 })
  const config = await first.getSettings()
  await first.saveUser({ id: 'mock-operator', role: 'designer', status: 'active' })
  const old = { ...first.snapshot(), schema: 1, workspace: { tasks: [{ id: 'old' }] }, skills: ['old'], settings: { ...config, defaultSkillIds: { wallpaper: 'old' } } }
  const migrated = migrateDemoState(old)!
  assert.deepEqual(Object.keys(migrated).sort(), ['schema', 'settings', 'users'])
  assert.equal(migrated.schema, 2)
  assert.equal('defaultSkillIds' in migrated.settings!, false)
  const restored = createMockService({ user, snapshot: migrated, delayMs: 0 })
  assert.equal((await restored.listUsers({ page: 1, pageSize: 20 })).items.find(u => u.id === 'mock-operator')?.role, 'designer')
  assert.equal((await restored.getSettings()).concurrency, config.concurrency)
  assert.deepEqual(migrateDemoState(migrated), migrated)
  first.dispose(); restored.dispose()
})
