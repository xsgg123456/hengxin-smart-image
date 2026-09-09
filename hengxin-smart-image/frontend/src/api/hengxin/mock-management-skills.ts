import type { ManagedSkill, ManagementScenario, ManagementService, SettingsInput } from '../../types/management'
import type { SkillVersion, User, Workspace } from '../../types/hengxin'
import { ApiError } from './http'

export function validateSettings(input: SettingsInput, skills: SkillVersion[]) {
  const ranges = [[input.concurrency, 1, 10], [input.timeoutSeconds, 60, 7200], [input.maxUploadBytes, 1048576, 10485760]]
  if (ranges.some(([v, min, max]) => !Number.isInteger(v) || v < min || v > max)) throw new ApiError('VALIDATION', '并发 1–10，超时 60–7200 秒，上传 1–10 MiB，必须为整数', 422)
  for (const mode of ['wallpaper', 'product', 'text'] as const) {
    const id = input.defaultSkillIds[mode]
    if (id !== null && !skills.some(s => s.id === id && s.mode === mode && s.status === 'available')) throw new ApiError('VALIDATION', '默认 Skill 必须为对应类型的可用版本', 422)
  }
  if (input.dingtalk.corpId.length > 100 || input.dingtalk.appId.length > 100) throw new ApiError('VALIDATION', '企业或应用标识过长', 422)
  if (input.dingtalk.callbackDomain) {
    let valid = false
    try { const url = new URL(input.dingtalk.callbackDomain); valid = url.protocol === 'https:' && !url.username && !url.password && url.pathname === '/' && !url.search && !url.hash } catch { /* invalid */ }
    if (!valid) throw new ApiError('VALIDATION', '回调域名需为 HTTPS 域名，不含路径或凭据', 422)
  }
}
export function createSkillManagement(db: Workspace, skills: SkillVersion[], check: (admin?: boolean, operation?: string) => Promise<User>, options: { scenario?: ManagementScenario; installMs?: number }): Pick<ManagementService, 'listManagedSkills' | 'uploadSkill' | 'installSkill' | 'setSkillStatus'> {
  const metadata = new Map<string, Omit<ManagedSkill, keyof SkillVersion>>()
  const jobs = new Map<string, number>()
  const failedOnce = new Set<string>()
  function managed(s: SkillVersion): ManagedSkill {
    const previous = metadata.get(s.id) ?? { installedAt: s.status === 'available' ? new Date().toISOString() : null, node: s.status === 'available' ? '模拟 Worker' : null, updatedAt: new Date().toISOString(), error: null, referenced: false }
    if (!metadata.has(s.id)) metadata.set(s.id, previous)
    return { ...previous, ...s, referenced: db.tasks.some(t => t.skillVersionId === s.id) || db.templates.some(t => t.skillVersionId === s.id) }
  }
  function get(id: string) { const skill = skills.find(s => s.id === id); if (!skill) throw new ApiError('NOT_FOUND', 'Skill 不存在', 404); return skill }
  function finish() {
    for (const [id, deadline] of jobs) if (deadline <= Date.now()) {
      const skill = get(id); skill.status = options.scenario === 'install-error' && !failedOnce.has(id) ? 'failed' : 'available'
      if (skill.status === 'failed') failedOnce.add(id)
      metadata.set(id, { ...managed(skill), updatedAt: new Date().toISOString(), installedAt: skill.status === 'available' ? new Date().toISOString() : null, node: '模拟 Worker', error: skill.status === 'failed' ? '模拟依赖检查失败；旧版本保持可用' : null }); jobs.delete(id)
    }
  }
  return {
    async listManagedSkills() { await check(true); finish(); return options.scenario === 'empty' ? [] : skills.map(managed) },
    async uploadSkill(file, mode, version) {
      await check(true, 'save')
      if (!['wallpaper', 'product', 'text'].includes(mode) || !/^\d+\.\d+\.\d+(?:-[\w.-]+)?$/.test(version) || !/\.zip$/i.test(file.name) || !file.size || file.size > 20 * 1048576) throw new ApiError('VALIDATION', '请选择非空且 ≤20 MiB 的 ZIP 包及合法语义版本', 422)
      if (skills.some(s => s.mode === mode && s.version === version)) throw new ApiError('CONFLICT', '该类型版本已存在', 409)
      const bytes = await file.arrayBuffer()
      const head = new Uint8Array(bytes)
      if (head[0] !== 0x50 || head[1] !== 0x4b || ![3, 5, 7].includes(head[2])) throw new ApiError('VALIDATION', 'ZIP 包头校验失败', 422)
      const checksum = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', bytes)), v => v.toString(16).padStart(2, '0')).join('')
      await check(true, 'save')
      if (skills.some(s => s.mode === mode && s.version === version)) throw new ApiError('CONFLICT', '该类型版本已存在', 409)
      const skill: SkillVersion = { id: crypto.randomUUID(), name: file.name, mode, version, checksum, status: 'uploaded', isDefault: false }
      skills.push(skill); return managed(skill)
    },
    async installSkill(id) {
      await check(true, 'save'); finish(); const skill = get(id)
      if (!['uploaded', 'failed'].includes(skill.status)) throw new ApiError('CONFLICT', '仅已上传或安装失败版本可安装', 409)
      skill.status = 'installing'; jobs.set(id, Date.now() + (options.installMs ?? 1200)); return managed(skill)
    },
    async setSkillStatus(id, status) {
      await check(true, 'save'); finish(); const skill = get(id)
      if (!['available', 'disabled'].includes(status) || !['available', 'disabled'].includes(skill.status)) throw new ApiError('CONFLICT', '只有安装完成的版本可启停', 409)
      skill.status = status; metadata.set(id, { ...managed(skill), updatedAt: new Date().toISOString() }); return managed(skill)
    }
  }
}
