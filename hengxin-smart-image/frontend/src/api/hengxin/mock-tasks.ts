import type { Accepted, HengxinService, PageQuery, Picture, ResultSlot, ResultVersion, Round, Task, Workspace } from '../../types/hengxin'
import { ApiError } from './http'
import { MOCK_USER_ID, sampleImages } from './fixtures'
import type { MockScenario } from './mock-catalog'

export function createMockTasks(db: Workspace, wait: () => Promise<void>, scenario: MockScenario, stepMs = 700) {
  const copy = <T>(value: T): T => JSON.parse(JSON.stringify(value)) as T
  const stamp = () => new Date().toISOString()
  const id = () => crypto.randomUUID()
  const active = new Map<string, ReturnType<typeof setInterval>>()
  const slots = new Map<string, ResultSlot[]>(), rounds = new Map<string, Round[]>()
  let scenarioUsed = false, archiveFailureUsed = false
  function find(taskId: string) {
    const task = db.tasks.find(t => t.id === taskId)
    if (!task) throw new ApiError('NOT_FOUND', '任务已删除或不存在', 404)
    return task
  }
  function initialize(task: Task) {
    task.outputCount ??= task.images.length
    const existing = task.state === '失败' ? [] : task.images
    const result = Array.from({ length: task.outputCount }, (_, slot): ResultSlot => {
      const picture = existing[slot]
      const version = picture ? { ...picture, id: `${task.id}-slot-${slot}-v1`, version: picture.version ?? 1, roundId: task.currentRoundId, createdAt: task.time } : undefined
      return { slot, versions: version ? [version] : [], currentVersionId: version?.id ?? null, error: task.state === '失败' ? '模拟执行失败，尚无成功结果' : null }
    })
    slots.set(task.id, result)
    rounds.set(task.id, task.currentRoundId ? [{ id: task.currentRoundId, taskId: task.id, operatorId: task.ownerId, target: null,
      note: '初始生成', state: task.state, createdAt: task.time, startedAt: task.time, finishedAt: task.time, error: task.state === '失败' ? '模拟执行失败' : null }] : [])
    if (task.state === '失败') { task.images = []; task.error = '模拟执行失败，尚无成功结果' }
    else sync(task)
  }
  function current(taskId: string): ResultVersion[] {
    return (slots.get(taskId) ?? []).flatMap(slot => slot.versions.filter(v => v.id === slot.currentVersionId))
  }
  function sync(task: Task) {
    task.images = copy(current(task.id))
    const ids = current(task.id).map(p => p.id)
    task.archived = db.archives.some(a => a.taskId === task.id && JSON.stringify(a.imageVersionIds) === JSON.stringify(ids))
  }
  db.tasks.forEach(initialize)
  function run(task: Task, target: number | null, note: string, initial = false): Accepted {
    if (active.has(task.id)) throw new ApiError('CONFLICT', '任务正在处理中，请稍后再试', 409)
    if (!slots.has(task.id)) initialize(task)
    const targets = slots.get(task.id)!.filter(s => target === null || s.slot === target)
    const failure = !scenarioUsed && ((scenario === 'execution-error' && initial) || (scenario === 'revision-error' && !initial) || scenario === 'partial-result')
    if (failure) scenarioUsed = true
    const round: Round = { id: id(), taskId: task.id, operatorId: MOCK_USER_ID, target, note,
      state: '排队中', createdAt: stamp(), startedAt: null, finishedAt: null, error: null }
    rounds.get(task.id)!.unshift(round)
    task.currentRoundId = round.id; task.state = '排队中'; task.progress = 0; task.error = null
    if (note) task.feedback.unshift(`${round.createdAt} · ${target === null ? '整套' : `第 ${target + 1} 张`}：${note}`)
    const timer = setInterval(() => {
      round.startedAt ??= stamp(); round.state = task.state = '执行中'
      task.progress = (task.progress ?? 0) + 25
      if (task.progress < 100) return
      clearInterval(timer); active.delete(task.id)
      targets.forEach((slot, index) => {
        if (failure && (scenario !== 'partial-result' || index === targets.length - 1)) {
          slot.error = '模拟生成失败，旧结果已保留'; return
        }
        const picture: Picture = sampleImages(task.mode, (task.outputCount ?? 1))[slot.slot]
        const version: ResultVersion = { ...picture, id: id(), version: Math.max(0, ...slot.versions.map(v => v.version)) + 1, roundId: round.id, createdAt: stamp() }
        slot.versions.push(version); slot.currentVersionId = version.id; slot.error = null
      })
      const allSlots = slots.get(task.id)!
      const failed = allSlots.filter(s => s.error || !s.currentVersionId).length
      task.state = failed ? (failed === allSlots.length || (failure && scenario !== 'partial-result') ? '失败' : '部分失败') : '待查看'
      task.error = failed ? '部分或全部图片执行失败；成功版本及既有结果保留，可重试失败轮次' : null
      round.state = task.state; round.error = task.error; round.finishedAt = stamp()
      sync(task)
    }, stepMs)
    active.set(task.id, timer)
    return { taskId: task.id, roundId: round.id, state: '排队中' }
  }
  function paginate<T>(items: T[], query: PageQuery) {
    if (!Number.isInteger(query.page) || query.page < 1 || !Number.isInteger(query.pageSize) || query.pageSize < 1 || query.pageSize > 100) throw new ApiError('VALIDATION', '分页参数无效', 422)
    return { items: copy(items.slice((query.page - 1) * query.pageSize, query.page * query.pageSize)), total: items.length, page: query.page, pageSize: query.pageSize }
  }
  const service: Pick<HengxinService, 'listTasks' | 'getTask' | 'deleteTask' | 'listArchives' | 'getArchive' | 'revise' | 'archive' | 'deleteArchive'> = {
    async listTasks(query) {
      await wait()
      const search = query.search?.trim().toLocaleLowerCase() ?? ''
      const items = db.tasks.filter(task => (!query.mode || task.mode === query.mode)
        && (!query.state || (query.state === 'processing' ? ['排队中', '执行中'].includes(task.state)
          : query.state === 'error' ? ['失败', '部分失败'].includes(task.state) : task.state === query.state))
        && `${task.name} ${task.id} ${task.sku ?? ''}`.toLocaleLowerCase().includes(search))
        .sort((a, b) => b.time.localeCompare(a.time) || a.id.localeCompare(b.id))
      return { ...paginate(items, query), stats: { total: db.tasks.length, processing: db.tasks.filter(t => active.has(t.id)).length,
        ready: db.tasks.filter(t => t.state === '待查看').length, archived: db.archives.length } }
    },
    async getTask(taskId) { await wait(); return copy({ task: find(taskId), slots: slots.get(taskId)!, rounds: rounds.get(taskId)! }) },
    async deleteTask(taskId) {
      await wait(); find(taskId)
      clearInterval(active.get(taskId)); active.delete(taskId)
      db.tasks = db.tasks.filter(t => t.id !== taskId); slots.delete(taskId); rounds.delete(taskId)
      const receipt = { id: taskId, operatorId: MOCK_USER_ID, deletedAt: stamp(), resourceType: 'task' as const }
      db.deletions ??= []; db.deletions.push(receipt)
      return copy(receipt)
    },
    async revise(input) {
      await wait()
      const task = find(input.taskId)
      if (active.has(task.id)) throw new ApiError('CONFLICT', '任务正在处理中，请稍后再试', 409)
      let target = input.target, note = input.note.trim()
      if (input.retry) {
        if (!['失败', '部分失败'].includes(task.state)) throw new ApiError('CONFLICT', '当前任务无需重试', 409)
        const previous = rounds.get(task.id)![0]
        target = previous?.target ?? null; note = previous?.note ?? '重试初始生成'
      } else {
        if (task.state !== '待查看') throw new ApiError('CONFLICT', '请先重试失败轮次，再提交新的修改意见', 409)
        if (!note || note.length > 1000) throw new ApiError('VALIDATION', '请填写 1–1000 字修改意见', 422)
      }
      if (target !== null && (!Number.isInteger(target) || target < 0 || target >= (task.outputCount ?? 0))) throw new ApiError('VALIDATION', '目标图片不存在', 422)
      return run(task, target, note)
    },
    async archive(taskId) {
      await wait()
      if (scenario === 'archive-error' && !archiveFailureUsed) { archiveFailureUsed = true; throw new ApiError('SIMULATED_FAILURE', '模拟归档失败，请重试；当前结果保留', 503) }
      const task = find(taskId), versions = current(taskId)
      if (task.state !== '待查看' || !versions.length || versions.length !== task.outputCount) throw new ApiError('CONFLICT', '完整结果可用后才能归档', 409)
      const imageVersionIds = versions.map(v => v.id)
      const previous = db.archives.find(a => a.taskId === taskId && JSON.stringify(a.imageVersionIds) === JSON.stringify(imageVersionIds))
      if (previous) return copy(previous)
      const archive = { id: `A-${id()}`, taskId, name: task.name, mode: task.mode, images: copy(versions), time: stamp(), ownerId: MOCK_USER_ID, imageVersionIds }
      db.archives.unshift(archive); task.archived = true
      return copy(archive)
    },
    async listArchives(query) {
      await wait()
      const search = query.search?.trim().toLocaleLowerCase() ?? ''
      return paginate(db.archives.filter(a => (!query.mode || a.mode === query.mode) && a.name.toLocaleLowerCase().includes(search))
        .sort((a, b) => b.time.localeCompare(a.time) || a.id.localeCompare(b.id)), query)
    },
    async getArchive(archiveId) {
      await wait()
      const archive = db.archives.find(a => a.id === archiveId)
      if (!archive) throw new ApiError('NOT_FOUND', '成品已删除或不存在', 404)
      return copy(archive)
    },
    async deleteArchive(archiveId) {
      await wait()
      const archive = db.archives.find(a => a.id === archiveId)
      if (archive) {
        db.deletions ??= []
        db.deletions.push({ id: archiveId, operatorId: MOCK_USER_ID, deletedAt: stamp(), resourceType: 'archive' })
      }
      db.archives = db.archives.filter(a => a.id !== archiveId)
      const task = db.tasks.find(t => t.id === archive?.taskId)
      if (task) sync(task)
    }
  }
  return { service, run, dispose() { active.forEach(clearInterval); active.clear() } }
}
