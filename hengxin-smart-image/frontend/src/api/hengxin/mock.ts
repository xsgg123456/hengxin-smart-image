import type { HengxinService, Task, Workspace } from '../../types/hengxin'
import { createMockCatalog, type MockScenario } from './mock-catalog'
import { createMockTasks } from './mock-tasks'
import { ApiError } from './http'
import { createFixtures, MOCK_USER_ID } from './fixtures'

/** 独立内存模拟，不读写原型 localStorage，不代表后台持久化。 */
export function createMockService(options: { empty?: boolean; delayMs?: number; stepMs?: number; scenario?: MockScenario } = {}): HengxinService {
  const db: Workspace = (options.empty || options.scenario === 'empty') ? { templates: [], tasks: [], archives: [] } : createFixtures()
  const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T
  const wait = () => new Promise<void>(resolve => setTimeout(resolve, options.delayMs ?? 120))
  const catalog = createMockCatalog(db, wait, options.scenario ?? 'default')
  const tasks = createMockTasks(db, wait, options.scenario ?? 'default', options.stepMs)
  return {
    async getUser() { await wait(); return { id: MOCK_USER_ID, name: '模拟运营', role: 'operator', status: 'active' } },
    async getWorkspace() { await wait(); return copy(db) },
    ...catalog.service, ...tasks.service,
    async createTask(input) {
      await wait(); catalog.fail('submit')
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
        skillVersionId: skill.id, sku: input.sku?.trim(), ownerId: MOCK_USER_ID, sessionId: null,
        state: '排队中', progress: 0, images: [], outputCount: template?.images.length ?? input.sources.length,
        sources, feedback: input.note ? [`初始要求：${input.note}`] : [],
        time: new Date().toISOString(), archived: false, currentRoundId: ''
      }
      db.tasks.unshift(task)
      return tasks.run(task, null, input.note, true)
    },
    dispose() { tasks.dispose(); catalog.dispose() }
  }
}
