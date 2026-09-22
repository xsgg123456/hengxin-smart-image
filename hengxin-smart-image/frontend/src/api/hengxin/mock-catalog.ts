import type { DemoState } from './demo-state'
import type { HengxinService, Mode, Picture, SkillVersion, Template, TemplateInput, Workspace } from '../../types/hengxin'
import { ApiError } from './http'
import { MOCK_USER_ID, sampleImages, skillNames } from './fixtures'
import { IMAGE_MIME_TYPES, MAX_IMAGE_BYTES, MAX_IMAGES } from './limits'

export type MockScenario = 'default' | 'empty' | 'no-skills' | 'upload-error' | 'save-error' | 'submit-error' | 'list-error'
  | 'execution-error' | 'partial-result' | 'revision-error' | 'archive-error'
export function createMockCatalog(db: Workspace, wait: () => Promise<void>, scenario: MockScenario, operatorId: () => string = () => MOCK_USER_ID, maxUploadBytes: () => number = () => MAX_IMAGE_BYTES, demo?: { state?: DemoState; pictures: typeof sampleImages }) {
  const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T
  const files = new Map<string, Picture>(demo?.state?.files)
  const objectUrls: string[] = []
  const consumed = new Set<string>(demo?.state?.catalogConsumed)
  const skills: SkillVersion[] = demo?.state?.skills ? copy(demo.state.skills) : scenario === 'no-skills' ? [] : (['wallpaper', 'product', 'text'] as const).map(mode => ({
    id: `mock-${mode}-1`, name: skillNames[mode], mode, version: '1.0.0',
    checksum: 'mock-checksum', isDefault: true, status: 'available'
  }))
  for (const mode of ['wallpaper', 'product', 'text'] as const) {
    (demo?.pictures ?? sampleImages)(mode, 4).forEach(picture => files.set(picture.fileId!, picture))
  }
  if (scenario === 'no-skills') db.templates.forEach(template => { template.active = false })
  const history = new Map<string, Template[]>(demo?.state?.templateHistory ?? db.templates.map(t => [t.id, [copy(t)]]))
  function fail(operation: string) {
    if (scenario === `${operation}-error` && !consumed.has(operation)) {
      consumed.add(operation)
      throw new ApiError('SIMULATED_FAILURE', '模拟服务本次接收失败，请重试；已有输入保留', 503)
    }
  }
  function resolvePictures(pictures: Picture[]): Picture[] {
    if (!pictures.length || pictures.length > MAX_IMAGES) throw new ApiError('VALIDATION', '每组图片需要 1–20 张', 422)
    return pictures.map(picture => {
      const file = picture.fileId ? files.get(picture.fileId) : undefined
      if (!file) throw new ApiError('VALIDATION', '素材未接收成功或已失效，请重新添加', 422)
      return copy(file)
    })
  }
  function resolveSkill(mode: Mode, versionId?: string | null) {
    const skill = skills.find(s => s.mode === mode && s.status === 'available' && (versionId ? s.id === versionId : s.isDefault))
    if (!skill) throw new ApiError('SKILL_UNAVAILABLE', '没有匹配且可用的 Skill，请联系超级管理员', 422)
    return skill
  }
  function get(id: string) {
    const template = db.templates.find(t => t.id === id)
    if (!template) throw new ApiError('NOT_FOUND', '模板已删除，请重新选择', 404)
    return template
  }
  const service: Pick<HengxinService, 'listTemplates' | 'getTemplate' | 'getTemplateVersions' | 'listSkills' | 'uploadFile' | 'saveTemplate' | 'deleteTemplate'> = {
    async listTemplates(query) {
      await wait(); fail('list')
      if (!Number.isInteger(query.page) || query.page < 1 || !Number.isInteger(query.pageSize) || query.pageSize < 1 || query.pageSize > 100) {
        throw new ApiError('VALIDATION', '分页参数无效', 422)
      }
      const search = query.search?.trim().toLocaleLowerCase() ?? ''
      const result = db.templates.filter(t => (!query.mode || t.mode === query.mode) && (!query.activeOnly || t.active)
        && t.name.toLocaleLowerCase().includes(search))
      result.sort((a, b) => query.sort === 'name' ? a.name.localeCompare(b.name, 'zh-CN')
        : query.sort === 'images' ? b.images.length - a.images.length || a.id.localeCompare(b.id)
        : b.updatedAt.localeCompare(a.updatedAt) || a.id.localeCompare(b.id))
      return { items: copy(result.slice((query.page - 1) * query.pageSize, query.page * query.pageSize)), page: query.page, pageSize: query.pageSize, total: result.length }
    },
    async getTemplate(id) { await wait(); return copy(get(id)) },
    async getTemplateVersions(id) { await wait(); get(id); return copy(history.get(id) ?? []) },
    async listSkills(mode) { await wait(); return copy(skills.filter(s => !mode || s.mode === mode)) },
    async uploadFile(file) {
      await wait(); fail('upload')
      const limit = Math.min(MAX_IMAGE_BYTES, maxUploadBytes())
      if (!IMAGE_MIME_TYPES.includes(file.type) || !file.size || file.size > limit) throw new ApiError('VALIDATION', `仅接收非空且不超过 ${limit / 1048576} MiB 的 JPG、PNG、WebP`, 422)
      const url = demo ? await new Promise<string>((resolve, reject) => {
        const reader = new FileReader(); reader.onload = () => resolve(String(reader.result)); reader.onerror = () => reject(new ApiError('READ_ERROR', '本地图片读取失败', 422)); reader.readAsDataURL(file)
      }) : URL.createObjectURL(file)
      if (demo) { const image = new Image(); image.src = url; try { await image.decode() } catch { throw new ApiError('VALIDATION', '图片内容无法读取，请重新选择', 422) } }
      else objectUrls.push(url)
      const picture = { fileId: `mock-file-${crypto.randomUUID()}`, name: file.name, url }
      files.set(picture.fileId, picture)
      return copy(picture)
    },
    async saveTemplate(input: TemplateInput) {
      await wait(); fail('save')
      if (!input.name.trim() || input.name.trim().length > 60) throw new ApiError('VALIDATION', '请填写 1–60 字模板名称', 422)
      if (input.mode === 'text') throw new ApiError('VALIDATION', '文字替换不使用套图模板', 422)
      const images = resolvePictures(input.images)
      const skill = input.skillVersionId
        ? skills.find(s => s.id === input.skillVersionId && s.mode === input.mode)
        : skills.find(s => s.mode === input.mode && s.isDefault && s.status === 'available')
      if (input.skillVersionId && !skill) throw new ApiError('VALIDATION', 'Skill 不存在或不适用于该模块', 422)
      const previous = input.id ? get(input.id) : undefined
      if (previous && input.expectedVersion !== previous.version) throw new ApiError('CONFLICT', '模板已被更新，请关闭后重新打开；本次输入尚未保存', 409)
      const saved: Template = { id: previous?.id ?? `T-${crypto.randomUUID()}`, name: input.name.trim(), mode: input.mode, images,
        skillBinding: input.skillVersionId ? 'specific' : 'module_default',
        skill: skill?.name ?? '', skillVersionId: skill?.id ?? null, active: skill?.status === 'available' && input.active,
        notes: input.notes.trim(), version: previous ? previous.version + 1 : 1,
        updatedAt: new Date().toISOString(), ownerId: previous?.ownerId ?? operatorId() }
      if (previous) db.templates[db.templates.indexOf(previous)] = saved
      else db.templates.unshift(saved)
      history.set(saved.id, [copy(saved), ...(history.get(saved.id) ?? [])])
      return copy(saved)
    },
    async deleteTemplate(id) {
      await wait()
      if (db.templates.some(t => t.id === id)) {
        db.deletions ??= []
        db.deletions.push({ id, operatorId: operatorId(), deletedAt: new Date().toISOString(), resourceType: 'template' })
      }
      db.templates = db.templates.filter(t => t.id !== id)
    }
  }
  return { snapshot: () => ({ files: [...files], templateHistory: [...history], skills: copy(skills), catalogConsumed: [...consumed] }), skills, service, resolvePictures, resolveSkill, fail, dispose() { objectUrls.forEach(url => URL.revokeObjectURL(url)) } }
}
