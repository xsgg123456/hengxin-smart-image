import { reactive } from 'vue'
import { useUserStore } from '@/store/modules/user'
import { previewSkillMetadata } from '@/views/overseas/admin/skill-folder-metadata'
import { workspaces, type WorkspaceId } from './workspaces'

export const skillsPath = '/management/skills'
export type SkillFile = { path: string; blob?: Blob }
export type DomesticSkill = { id: string; name: string; displayName: string; description: string; source: string; files: SkillFile[]; enabled: boolean; updatedAt: string; demo: boolean }
export const canManageSkills = () => useUserStore().info.roles?.includes('super_admin') === true
function assertAdmin() { if (!canManageSkills()) throw new Error('仅超级管理员可以管理 Skills') }
export const skills = reactive<DomesticSkill[]>(workspaces.map(item => {
  const name = `domestic-${item.id}`
  const source = `---\nname: ${name}\ndescription: ${item.description}\n---\n\n# ${item.title}\n\n这是交互预览示例，不是生产 Skill。\n\n${item.guidance}\n`
  return { id: name, name, displayName: item.title, description: item.description, source, files: [{ path: 'SKILL.md', blob: new Blob([source], { type: 'text/markdown' }) }], enabled: true, updatedAt: new Date().toISOString(), demo: true }
}))
export const bindings = reactive(Object.fromEntries(workspaces.map(item => [item.id, `domestic-${item.id}`])) as Record<WorkspaceId, string>)
export const usedBy = (id: string) => workspaces.filter(workspace => bindings[workspace.id] === id)
export const boundSkill = (id: WorkspaceId) => skills.find(skill => skill.id === bindings[id] && skill.enabled)

export function saveSkill(id: string | undefined, source: string, files?: SkillFile[]) {
  assertAdmin()
  const meta = previewSkillMetadata(source, 'new-skill')
  if (!/^[a-z0-9][a-z0-9_-]{0,63}$/.test(meta.name)) throw new Error('name 须为 1–64 位小写字母、数字、短横线或下划线')
  if (!meta.description.trim() || meta.description === '元数据待服务器校验后显示') throw new Error('请填写有效的 description')
  if (skills.some(skill => skill.id !== id && skill.name === meta.name)) throw new Error('已存在同名 Skill，请编辑原 Skill 或修改 name')
  const existing = id ? skills.find(skill => skill.id === id) : undefined
  if (id && !existing) throw new Error('该 Skill 已不存在')
  const nextFiles = [...(files || existing?.files || []).filter(file => file.path !== 'SKILL.md'), { path: 'SKILL.md', blob: new Blob([source], { type: 'text/markdown' }) }]
  const next = { ...meta, source, files: nextFiles, updatedAt: new Date().toISOString(), demo: existing?.demo ?? false }
  if (existing) Object.assign(existing, next)
  else skills.unshift({ ...next, id: crypto.randomUUID(), enabled: false })
}
export function toggleSkill(skill: DomesticSkill) {
  assertAdmin()
  if (skill.enabled && usedBy(skill.id).length) throw new Error('此 Skill 正被工作台使用，请先在「工作台绑定」更换或解除绑定')
  skill.enabled = !skill.enabled; skill.updatedAt = new Date().toISOString()
}
export function deleteSkill(skill: DomesticSkill) {
  assertAdmin()
  if (usedBy(skill.id).length) throw new Error('此 Skill 正被工作台使用，请先更换或解除绑定')
  const index = skills.findIndex(item => item.id === skill.id)
  if (index >= 0) skills.splice(index, 1)
}
export function saveBindings(draft: Record<WorkspaceId, string>) {
  assertAdmin()
  for (const workspace of workspaces) if (draft[workspace.id] && !skills.some(skill => skill.id === draft[workspace.id] && skill.enabled)) throw new Error(`${workspace.title} 的 Skill 不可用，请重新选择`)
  Object.assign(bindings, draft)
}
