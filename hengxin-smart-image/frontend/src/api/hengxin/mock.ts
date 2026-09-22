import type { Accepted, HengxinService, Task, User, Workspace } from '../../types/hengxin'
import type { DemoState } from './demo-state'
import { createMockCatalog, type MockScenario } from './mock-catalog'
import { createMockTasks } from './mock-tasks'
import { ApiError } from './http'
import { createFixtures, demoImages, sampleImages } from './fixtures'
import { createMockManagement } from './mock-management'
import { getPreviewUser } from './session'
import type { ManagementScenario } from '../../types/management'

/** 独立内存模拟，不读写原型 localStorage，不代表后台持久化。 */
export function createMockService(options: { demo?: boolean; snapshot?: DemoState; changed?: () => void; empty?: boolean; delayMs?: number; stepMs?: number; installMs?: number; scenario?: MockScenario; managementScenario?: ManagementScenario; user?: User } = {}): HengxinService & { snapshot: () => DemoState } {
  const db: Workspace = options.snapshot ? structuredClone(options.snapshot.workspace) : (options.empty || options.scenario === 'empty') ? { templates: [], tasks: [], archives: [] } : createFixtures(options.demo ? demoImages : sampleImages)
  const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T
  let user = copy(options.user ?? getPreviewUser())
  const storedUser = options.snapshot?.users?.find(u => u.id === user.id)
  if (storedUser) user = copy(storedUser)
  let extra: Partial<DemoState> = options.snapshot ? copy(options.snapshot) : {}
  let uploadLimit = 10 * 1048576
  const submissions = new Map<string, { fingerprint: string; accepted: Accepted }>(options.snapshot?.submissions)
  let executionConfig = { version: 1, concurrency: 1, timeoutSeconds: 600 }
  const wait = async () => { await new Promise<void>(resolve => setTimeout(resolve, options.delayMs ?? 120)); if (user.status !== 'active' || !user.role) { if (typeof window !== 'undefined') window.dispatchEvent(new Event('hengxin:unauthorized')); throw new ApiError('UNAUTHORIZED', '账号未授权或已禁用', 401) } }
  const catalog = createMockCatalog(db, wait, options.scenario ?? 'default', () => user.id, () => uploadLimit, options.demo ? { state: options.snapshot, pictures: demoImages } : undefined)
  const tasks = createMockTasks(db, wait, options.scenario ?? 'default', options.stepMs, () => user.id, () => executionConfig,
    fileId => catalog.resolvePictures([{ fileId, name: '', url: '' }])[0], options.demo ? { state: options.snapshot, pictures: demoImages, changed: options.changed } : undefined)
  const management = createMockManagement(db, catalog.skills, () => user, { snapshot: options.snapshot, capture: state => { extra = { ...extra, ...copy(state) } }, scenario: options.managementScenario, wait, installMs: options.installMs, getAttempts: tasks.getUsageAttempts, getHistoricalTasks: tasks.getHistoricalTasks, onSettingsChanged: config => { uploadLimit = config.maxUploadBytes; executionConfig = { version: config.version, concurrency: config.concurrency, timeoutSeconds: config.timeoutSeconds } }, onUserChanged: updated => { if (updated.id === user.id) { user = copy(updated); if (typeof window !== 'undefined') window.dispatchEvent(new Event('hengxin:identity-changed')) } } })
  return {
    async getUser() { return copy(user) },
    async getWorkspace() { await wait(); return copy(db) },
    ...catalog.service, ...tasks.service, ...management,
    async createTask(input, idempotencyKey = crypto.randomUUID()) {
      await wait()
      const key = `${user.id}:${idempotencyKey}`, fingerprint = JSON.stringify(input)
      const previous = submissions.get(key)
      if (previous) {
        if (previous.fingerprint !== fingerprint) throw new ApiError('CONFLICT', '同一请求标识的内容不一致', 409)
        return copy(previous.accepted)
      }
      catalog.fail('submit')
      const template = input.mode === 'text' ? undefined : db.templates.find(t => t.id === input.templateId)
      if (!input.name.trim() || !input.sources.length || (input.mode === 'text' && !input.note.trim())) throw new ApiError('VALIDATION', '请填写任务名称、素材及必要修改要求', 422)
      if (input.mode !== 'text' && (!template?.active || !template.skill || template.mode !== input.mode)) throw new ApiError('VALIDATION', '请选择类型匹配且 Skill 可用的模板', 422)
      const sources = catalog.resolvePictures(input.sources)
      if (input.name.trim().length > 60 || (input.sku?.length ?? 0) > 80 || input.note.length > 1000) throw new ApiError('VALIDATION', '名称、SKU 或说明长度超限', 422)
      if (template && input.templateVersion !== undefined && template.version !== input.templateVersion) throw new ApiError('CONFLICT', '模板版本已更新，请重新选择模板', 409)
      const skill = catalog.resolveSkill(input.mode, template?.skillVersionId ?? input.skillVersionId)
      const task: Task = {
        id: `HX-${crypto.randomUUID()}`, name: input.name.trim(), mode: input.mode, template: template?.name ?? '无需模板',
        templateId: template?.id, templateVersion: template?.version, templateSnapshot: template ? copy(template) : undefined,
        skillSnapshot: { id: skill.id, name: skill.name, version: skill.version, checksum: skill.checksum },
        skillVersionId: skill.id, sku: input.sku?.trim(), ownerId: user.id, sessionId: null,
        state: '排队中', progress: 0, images: [], outputCount: template?.images.length ?? input.sources.length,
        sources, feedback: input.note ? [`初始要求：${input.note}`] : [],
        time: new Date().toISOString(), archived: false, currentRoundId: ''
      }
      db.tasks.unshift(task)
      const accepted = tasks.run(task, null, input.note, true)
      submissions.set(key, { fingerprint, accepted })
      return copy(accepted)
    },
    dispose() { tasks.dispose(); catalog.dispose() },
    snapshot: () => copy({ ...extra, ...catalog.snapshot(), ...management.snapshot(), ...tasks.snapshot(), schema: 1, workspace: db, submissions: [...submissions] })
  }
}
