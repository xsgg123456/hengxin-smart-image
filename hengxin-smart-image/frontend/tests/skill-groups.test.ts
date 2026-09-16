import { test } from 'node:test'
import assert from 'node:assert/strict'
import { groupSkills } from '../src/views/hengxin/admin/skill-groups'
import type { ManagedSkill } from '../src/types/management'

function skill(id: string, patch: Partial<ManagedSkill> = {}): ManagedSkill {
  return { id, name: 'wallpaper', mode: 'wallpaper', version: '1.0.0', checksum: 'sum',
    status: 'available', isDefault: false, installedAt: null, node: null,
    updatedAt: '2026-09-11T00:00:00Z', error: null, referenced: false, ...patch }
}

test('同名同类型合并，保留各版本身份与引用，默认可以是旧版本', () => {
  const recent = skill('new', { version: '1.0.1', status: 'failed' })
  const old = skill('old', { isDefault: true, referenced: true, updatedAt: '2026-09-12T00:00:00Z' })
  const rows = [recent, old], groups = groupSkills(rows)
  assert.equal(groups.length, 1)
  assert.equal(groups[0].recent, recent)
  assert.equal(groups[0].defaultVersion, old)
  assert.deepEqual(groups[0].versions.map(row => row.id), ['new', 'old'])
  assert.equal(groups[0].versions[1].referenced, true)
  assert.deepEqual(rows, [recent, old])
})

test('同名不同类型分开，组key刷新稳定，无默认不从可用版本推断', () => {
  const rows = [skill('a'), skill('b', { mode: 'text' })]
  const groups = groupSkills(rows)
  assert.equal(groups.length, 2)
  assert.notEqual(groups[0].key, groups[1].key)
  assert.equal(groups[0].defaultVersion, undefined)
  assert.deepEqual(groupSkills(rows.map(row => ({ ...row }))).map(g => g.key), groups.map(g => g.key))
  assert.deepEqual(groupSkills([]), [])
})
