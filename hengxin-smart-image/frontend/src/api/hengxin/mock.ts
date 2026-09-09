import type { Accepted, HengxinService, Task, Workspace } from '../../types/hengxin'
import { createMockCatalog, type MockScenario } from './mock-catalog'
import { ApiError } from './http'
import { createFixtures, MOCK_USER_ID, sampleImages } from './fixtures'

/** 独立内存模拟，不读写原型 localStorage，不代表后台持久化。 */
export function createMockService(options: { empty?: boolean; delayMs?: number; stepMs?: number; scenario?: MockScenario } = {}): HengxinService {
  const db: Workspace = (options.empty || options.scenario === 'empty') ? { templates: [], tasks: [], archives: [] } : createFixtures()
  const active = new Map<string, ReturnType<typeof setInterval>>()
  const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T
  const stamp = () => new Date().toISOString()
  const id = () => crypto.randomUUID()
  const wait = () => new Promise<void>(resolve => setTimeout(resolve, options.delayMs ?? 120))
  const catalog = createMockCatalog(db, wait, options.scenario ?? 'default')
  const findTask = (taskId: string) => {
    const task = db.tasks.find(t => t.id === taskId)
    if (!task) throw new ApiError('NOT_FOUND', '任务不存在', 404)
    return task
  }
  function run(task: Task, target: number | null, note: string): Accepted {
    if (active.has(task.id)) throw new ApiError('CONFLICT', '任务正在处理中，请稍后再试', 409)
    task.currentRoundId = id()
    task.state = '排队中'
    task.progress = 0
    if (note) task.feedback.unshift(`${stamp()} · ${target === null ? '整套' : `第 ${target + 1} 张`}：${note}`)
    const timer = setInterval(() => {
      task.state = '执行中'
      task.progress = (task.progress ?? 0) + 25
      if (task.progress >= 100) {
        clearInterval(timer)
        active.delete(task.id)
        task.state = '待查看'
        if (note) {
          task.images = task.images.map((picture, index) => target === null || target === index
            ? { ...picture, version: (picture.version ?? 1) + 1 } : picture)
          task.archived = false
        }
      }
    }, options.stepMs ?? 700)
    active.set(task.id, timer)
    return { taskId: task.id, roundId: task.currentRoundId, state: '排队中' }
  }
  return {
    async getUser() { await wait(); return { id: MOCK_USER_ID, name: '模拟运营', role: 'operator', status: 'active' } },
    async getWorkspace() { await wait(); return copy(db) },
    ...catalog.service,
    async createTask(input) {
      await wait()
      catalog.fail('submit')
      const template = input.mode === 'text' ? undefined : db.templates.find(t => t.id === input.templateId)
      if (!input.name.trim() || !input.sources.length || (input.mode === 'text' && !input.note.trim())) {
        throw new ApiError('VALIDATION', '请填写任务名称、素材及必要修改要求', 422)
      }
      if (input.mode !== 'text' && (!template?.active || !template.skill || template.mode !== input.mode)) {
        throw new ApiError('VALIDATION', '请选择类型匹配且 Skill 可用的模板', 422)
      }
      const sources = catalog.resolvePictures(input.sources)
      if (input.name.trim().length > 60 || (input.sku?.length ?? 0) > 80 || input.note.length > 1000) throw new ApiError('VALIDATION', '名称、SKU 或说明长度超限', 422)
      if (template && input.templateVersion !== undefined && template.version !== input.templateVersion) throw new ApiError('CONFLICT', '模板版本已更新，请重新选择模板', 409)
      const skill = catalog.resolveSkill(input.mode, template?.skillVersionId ?? input.skillVersionId)
      const task: Task = {
        id: `HX-${id()}`, name: input.name, mode: input.mode, template: template?.name ?? '无需模板',
        templateId: template?.id, templateVersion: template?.version,
        templateSnapshot: template ? copy(template) : undefined,
        skillVersionId: skill.id, sku: input.sku?.trim(), ownerId: MOCK_USER_ID, sessionId: null,
        state: '排队中', progress: 0, images: sampleImages(input.mode, template?.images.length ?? input.sources.length),
        sources, feedback: input.note ? [`初始要求：${input.note}`] : [],
        time: stamp(), archived: false, currentRoundId: ''
      }
      db.tasks.unshift(task)
      return run(task, null, '')
    },
    async revise(input) {
      await wait()
      const task = findTask(input.taskId)
      if (input.target !== null && (!Number.isInteger(input.target) || input.target < 0 || input.target >= task.images.length)) {
        throw new ApiError('VALIDATION', '目标图片不存在', 422)
      }
      return run(task, input.target, input.note)
    },
    async archive(taskId) {
      await wait()
      const task = findTask(taskId)
      if (task.state !== '待查看') throw new ApiError('CONFLICT', '完整结果可用后才能归档', 409)
      const previous = db.archives.find(a => a.taskId === taskId && JSON.stringify(a.images) === JSON.stringify(task.images))
      if (previous) return copy(previous)
      const archive = { id: `A-${id()}`, taskId, name: task.name, mode: task.mode,
        images: copy(task.images), time: stamp(), ownerId: MOCK_USER_ID, imageVersionIds: [] }
      db.archives.unshift(archive)
      task.archived = true
      return copy(archive)
    },
    async deleteArchive(archiveId) {
      await wait()
      const archive = db.archives.find(a => a.id === archiveId)
      db.archives = db.archives.filter(a => a.id !== archiveId)
      const task = db.tasks.find(t => t.id === archive?.taskId)
      if (task) task.archived = db.archives.some(a => a.taskId === task.id && JSON.stringify(a.images) === JSON.stringify(task.images))
    },
    dispose() { active.forEach(clearInterval); active.clear(); catalog.dispose() }
  }
}
