import { test } from 'node:test'
import assert from 'node:assert/strict'
import { isSkillVersion } from '../src/utils/skill-version'
import { createMockManagement } from '../src/api/hengxin/mock-management'
import { createFixtures } from '../src/api/hengxin/fixtures'
import type { User } from '../src/types/hengxin'

const admin: User = { id: 'admin', name: '超管', role: 'super_admin', status: 'active' }
const input = { name: 'shared-skill', mode: 'text' as const, description: '' }

test('登记共享 SemVer 校验拒绝前导零、空段与非ASCII，接受构建元数据并遵守100字符上限', async () => {
  const api = createMockManagement(createFixtures(), [], () => admin)
  const invalid = ['01.0.0', '1.0.0-alpha..1', '1.0.0-01', '1.0.0-alpha.01', '1.0.0+build..1', '１.0.0', '1.0.0-中文', '1.0.0\n', '1.0.0+' + 'a'.repeat(95)]
  for (const version of invalid) {
    assert.equal(isSkillVersion(version), false, version)
    await assert.rejects(api.registerSkill({ ...input, version }), { code: 'VALIDATION' })
  }
  for (const version of ['0.0.0', '1.0.0+build.1', '1.0.0-alpha.0+001', '1.0.0-01a', '1.0.0+' + 'a'.repeat(94)]) {
    assert.equal(isSkillVersion(version), true, version)
    assert.equal((await api.registerSkill({ ...input, version })).version, version)
  }
})

test('登记唯一键包含处理类型：同标识同版本不同类型允许，同类型拒绝重复', async () => {
  const api = createMockManagement(createFixtures(), [], () => admin)
  const text = await api.registerSkill({ ...input, version: '1.0.0' })
  const wallpaper = await api.registerSkill({ ...input, mode: 'wallpaper', version: '1.0.0' })
  assert.notEqual(text.id, wallpaper.id)
  assert.equal((await api.listManagedSkills()).length, 2)
  await assert.rejects(api.registerSkill({ ...input, version: '1.0.0' }), { code: 'CONFLICT' })
})
