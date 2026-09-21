import type { CatalogSkill, ManagementService, ManagementScenario, SkillSync } from '../../types/management'
import type { SkillVersion, User, Workspace } from '../../types/hengxin'
import { ApiError } from './http'

type CatalogMethods = Pick<ManagementService, 'listSkillCatalog' | 'listManagedCatalog' | 'syncSkillCatalog' | 'getSkillSync' | 'setCatalogMode' | 'setCatalogStatus' | 'removeCatalogSkill'>
/** 模拟目录保留文件源；移除登记后再次同步会重新发现，不改变历史任务快照。 */
export function createMockSkillCatalog(db: Workspace, skills: SkillVersion[], check: (admin?: boolean, operation?: string) => Promise<User>, options: { scenario?: ManagementScenario; installMs?: number }): CatalogMethods {
  const copy = <T>(v: T): T => JSON.parse(JSON.stringify(v)) as T
  const metadata = new Map<string, CatalogSkill>()
  const source = copy(skills)
  let failedOnce = false
  const disabled = new Set(skills.filter(s => s.status === 'disabled').map(s => s.id))
  let sync: SkillSync = { jobId: null, status: 'idle', error: null }, deadline = 0
  const dto = (s: SkillVersion): CatalogSkill => ({ id: s.id, name: s.name,
    description: s.mode === 'wallpaper' ? "将每批新上传的4张京东手机商品主图JPG中的屏幕壁纸、屏内前置镜头或开孔及其位置，按1张JPG手机屏幕素材同步替换，保留其他设计元素，产出并展示4张800×800像素的最终修改图片。用户要求“把这张手机屏幕素材替换掉图片的壁纸与镜头，其他一律不允许有任何改变”或同义任务时使用；适用于每批上传4张底图加1张素材，不使用内置固定底图。" : `${s.name}：根据上传的图片和修改要求处理内容，保留其他设计元素。`, mode: s.mode,
    status: s.status === 'available' ? 'available' : s.status === 'disabled' ? 'disabled' : 'invalid',
    isDefault: s.isDefault, error: null, updatedAt: new Date().toISOString(), referenced: false })
  if (options.scenario !== 'empty') skills.forEach(s => metadata.set(s.id, dto(s)))
  if (options.scenario === 'unknown') metadata.set('mock-unknown', { id: 'mock-unknown', name: '新同步 Skill', description: '这是目录中的完整描述。请选择它适用的处理类型后重新同步。', mode: null, status: 'needs_type', isDefault: false, error: '请选择处理类型', updatedAt: new Date().toISOString(), referenced: false })
  function refresh() {
    if (!['queued', 'running'].includes(sync.status)) return
    if (Date.now() < deadline) { sync.status = 'running'; return }
    if (options.scenario !== 'empty') for (const item of source) if (!metadata.has(item.id)) { metadata.set(item.id, dto(item)); if (!skills.some(s => s.id === item.id)) skills.push(copy(item)) }
    for (const row of metadata.values()) {
      if (!row.mode) { row.status = 'needs_type'; row.error = '请选择处理类型'; continue }
      row.error = options.scenario === 'install-error' && !failedOnce && row.id === metadata.keys().next().value ? 'SKILL.md 无法读取，请检查目录后重新同步' : null
      row.status = row.error ? 'invalid' : disabled.has(row.id) ? 'disabled' : 'available'
      row.updatedAt = new Date().toISOString()
      let skill = skills.find(s => s.id === row.id)
      if (!skill) { skill = { id: row.id, name: row.name, mode: row.mode, status: row.status, version: '1.0.0', checksum: '', isDefault: false }; skills.push(skill) }
      skill.status = row.status; skill.mode = row.mode
      if (!row.error) skill.checksum = `mock-snapshot-${sync.jobId}`
    }
    sync.status = [...metadata.values()].some(item => item.status === 'invalid') ? 'failed' : 'succeeded'
    if (sync.status === 'failed') failedOnce = true
    sync.error = sync.status === 'failed' ? '部分 Skill 同步失败，请查看异常原因' : null
  }
  function row(id: string) { const item = metadata.get(id); if (!item) throw new ApiError('NOT_FOUND', 'Skill 不存在', 404); return item }
  function present(item: CatalogSkill): CatalogSkill {
    const live = skills.find(s => s.id === item.id)
    return { ...item, isDefault: live?.isDefault ?? false, referenced: !!live?.isDefault || db.templates.some(t => t.skillVersionId === item.id) }
  }
  function start() {
    refresh()
    if (!['queued', 'running'].includes(sync.status)) {
      sync = { jobId: crypto.randomUUID(), status: 'queued', error: null }; deadline = Date.now() + (options.installMs ?? 1200)
      metadata.forEach(r => { if (r.mode) r.status = 'syncing' })
    }
    return { jobId: sync.jobId!, status: sync.status as 'queued' | 'running' }
  }
  return {
    async listSkillCatalog(mode) { await check(); refresh(); return copy([...metadata.values()].map(present).filter(s => s.status === 'available' && (!mode || s.mode === mode))) },
    async listManagedCatalog() { await check(true); refresh(); return copy([...metadata.values()].map(present)) },
    async getSkillSync() { await check(true); refresh(); return copy(sync) },
    async syncSkillCatalog() { await check(true, 'save'); return start() },
    async setCatalogMode(id, mode) {
      await check(true, 'save'); refresh(); const item = row(id)
      if (!['wallpaper', 'product', 'text'].includes(mode)) throw new ApiError('VALIDATION', '请选择处理类型', 422)
      if (present(item).referenced && item.mode !== mode) throw new ApiError('CONFLICT', '请先解除模板和默认绑定', 409)
      item.mode = mode; start(); return copy(present(item))
    },
    async setCatalogStatus(id, status) {
      await check(true, 'save'); refresh(); const item = row(id)
      if (!['available', 'disabled'].includes(status)) throw new ApiError('VALIDATION', '状态无效', 422)
      if (!['available', 'disabled'].includes(item.status)) throw new ApiError('CONFLICT', '请先完成同步并修复异常', 409)
      item.status = status; status === 'disabled' ? disabled.add(id) : disabled.delete(id)
      const skill = skills.find(s => s.id === id); if (skill) skill.status = status
      return copy(present(item))
    },
    async removeCatalogSkill(id) {
      await check(true, 'save'); refresh(); const item = row(id)
      if (present(item).referenced || ['queued', 'running'].includes(sync.status)) throw new ApiError('CONFLICT', '请先解除模板/默认绑定并等待同步结束', 409)
      metadata.delete(id); disabled.delete(id); const index = skills.findIndex(s => s.id === id); if (index >= 0) skills.splice(index, 1)
    }
  }
}
