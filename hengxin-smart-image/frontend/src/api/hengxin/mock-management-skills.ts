import { isSkillVersion } from '../../utils/skill-version'
import type { ManagedSettings, ManagedSkill, ManagementScenario, ManagementService, SettingsInput } from '../../types/management'
import type { SkillVersion, User, Workspace } from '../../types/hengxin'
import { ApiError } from './http'

export function validateSettings(input: SettingsInput, skills: SkillVersion[], current: ManagedSettings) {
  const ranges = [[input.concurrency, 1, current.capacity], [input.timeoutSeconds, 60, current.timeoutCapacity], [input.maxUploadBytes, 1048576, 10485760]]
  if (ranges.some(([v, min, max]) => !Number.isInteger(v) || v < min || v > max)) throw new ApiError('VALIDATION', `并发 1–${current.capacity}，超时 60–${current.timeoutCapacity} 秒，上传 1–10 MiB，必须为整数`, 422)
  for (const mode of ['wallpaper', 'product', 'text'] as const) {
    const id = input.defaultSkillIds[mode]
    if (id !== null && !skills.some(s => s.id === id && s.mode === mode && s.status === 'available')) throw new ApiError('VALIDATION', '默认 Skill 必须为对应类型的可用版本', 422)
  }
  if ((['corpId', 'appId', 'callbackDomain'] as const).some(key => input.dingtalk[key] !== current.dingtalk[key])) {
    throw new ApiError('VALIDATION', '钉钉接入由部署环境管理，网页只读', 422)
  }
}
export function createSkillManagement(db: Workspace, skills: SkillVersion[], check: (admin?: boolean, operation?: string) => Promise<User>, options: { scenario?: ManagementScenario; installMs?: number }): Pick<ManagementService, 'listManagedSkills' | 'registerSkill' | 'checkSkill' | 'removeSkill' | 'setSkillStatus'> {
  const metadata = new Map<string, Omit<ManagedSkill, keyof SkillVersion>>()
  const jobs = new Map<string, number>()
  const failedOnce = new Set<string>()
  function managed(s: SkillVersion): ManagedSkill {
    const previous = metadata.get(s.id) ?? { sourceType: 'zip', installedAt: s.status === 'available' ? new Date().toISOString() : null, node: s.status === 'available' ? '模拟 Worker' : null, updatedAt: new Date().toISOString(), error: null, referenced: false }
    if (!metadata.has(s.id)) metadata.set(s.id, previous)
    return { ...previous, ...s, referenced: db.tasks.some(t => t.skillVersionId === s.id) || db.templates.some(t => t.skillVersionId === s.id) }
  }
  function get(id: string) { const skill = skills.find(s => s.id === id); if (!skill) throw new ApiError('NOT_FOUND', 'Skill 不存在', 404); return skill }
  function finish() {
    for (const [id, deadline] of jobs) if (deadline <= Date.now()) {
      const skill = get(id); skill.status = options.scenario === 'install-error' && !failedOnce.has(id) ? 'invalid' : 'verified'
      if (skill.status === 'invalid') failedOnce.add(id)
      if (skill.status === 'verified' && !skill.checksum) skill.checksum = 'mock-local-content-checksum'
      metadata.set(id, { ...managed(skill), updatedAt: new Date().toISOString(), installedAt: skill.status === 'verified' ? new Date().toISOString() : null, node: '模拟 Worker', error: skill.status === 'invalid' ? '模拟部署检查失败；旧版本保持可用' : null }); jobs.delete(id)
    }
  }
  return {
    async listManagedSkills() { await check(true); finish(); return options.scenario === 'empty' ? [] : skills.map(managed) },
    async registerSkill({ name, mode, version, description }) {
      await check(true, 'save')
      if (!/^[a-zA-Z0-9][a-zA-Z0-9_-]{0,99}$/.test(name) || !['wallpaper', 'product', 'text'].includes(mode) || !isSkillVersion(version) || description.length > 2000) throw new ApiError('VALIDATION', '请填写合法标识、语义版本及处理类型', 422)
      if (skills.some(s => s.name === name && s.mode === mode && s.version === version)) throw new ApiError('CONFLICT', '该 Skill 版本已存在', 409)
      const skill: SkillVersion = { id: crypto.randomUUID(), name, mode, version, checksum: '', status: 'pending', isDefault: false }
      metadata.set(skill.id, { sourceType: 'local', description, installedAt: null, node: null, updatedAt: new Date().toISOString(), error: null, referenced: false })
      skills.unshift(skill); return managed(skill)
    },
    async checkSkill(id) {
      await check(true, 'save'); finish(); const skill = get(id)
      if (managed(skill).sourceType !== 'local' || skill.status === 'checking') throw new ApiError('CONFLICT', '此版本不能检查或已有检查在途', 409)
      skill.status = 'checking'; metadata.set(id, { ...managed(skill), error: null, updatedAt: new Date().toISOString() }); jobs.set(id, Date.now() + (options.installMs ?? 1200)); return managed(skill)
    },
    async removeSkill(id) {
      await check(true, 'save'); finish(); const skill = get(id), row = managed(skill)
      if (row.sourceType !== 'local' || row.referenced || row.isDefault || row.status === 'checking') throw new ApiError('CONFLICT', '仅可移除无引用、非默认且无检查在途的本地登记', 409)
      skills.splice(skills.indexOf(skill), 1); metadata.delete(id)
    },
    async setSkillStatus(id, status) {
      await check(true, 'save'); finish(); const skill = get(id)
      if (!['available', 'disabled'].includes(status) || !['verified', 'available', 'disabled'].includes(skill.status)) throw new ApiError('CONFLICT', '只有已验证的版本可启停', 409)
      skill.status = status; metadata.set(id, { ...managed(skill), updatedAt: new Date().toISOString() }); return managed(skill)
    }
  }
}
