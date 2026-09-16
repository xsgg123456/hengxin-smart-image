import type { ManagedSkill } from '@/types/management'

export interface SkillGroup {
  key: string
  name: string
  mode: ManagedSkill['mode']
  recent: ManagedSkill
  versions: ManagedSkill[]
  defaultVersion?: ManagedSkill
}

// The API lists versions by creation time descending; do not sort by update time
// (enabling an old version must not make it the most recently uploaded version).
export function groupSkills(rows: ManagedSkill[]): SkillGroup[] {
  const groups = new Map<string, SkillGroup>()
  for (const row of rows) {
    const key = JSON.stringify([row.mode, row.name])
    let group = groups.get(key)
    if (!group) {
      group = { key, name: row.name, mode: row.mode, recent: row, versions: [] }
      groups.set(key, group)
    }
    group.versions.push(row)
    if (row.isDefault) group.defaultVersion = row
  }
  return [...groups.values()]
}
