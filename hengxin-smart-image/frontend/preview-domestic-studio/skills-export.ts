import { sha256 } from '@/views/overseas/admin/skill-folder-read'
import { downloadSkillZip } from '@/views/overseas/admin/skill-folder-zip'
import type { SkillPackage, FolderEntry } from '@/api/overseas/skill-transfers'
import type { DomesticSkill } from './skills-state'
export async function exportSkill(skill: DomesticSkill) {
  const files = new Map(skill.files.map(file => [file.path, file.blob]))
  const entries: Record<string, FolderEntry> = {}
  for (const [path, blob] of files) entries[path] = blob ? { size: blob.size, sha256: await sha256(await blob.arrayBuffer()) } : { directory: true }
  const descriptor: SkillPackage = { rootName: skill.name, name: skill.name, displayName: skill.displayName, description: skill.description, entries, checksum: '', release: 'local-preview' }
  const api = { file: async (_id: string, _release: string, path: string) => { const file = files.get(path); if (!file) throw new Error(`文件不存在：${path}`); return file.arrayBuffer() } }
  await downloadSkillZip(skill.id, descriptor, api, () => {})
}
