import { executionPollDelay, type ExecutionData } from '../../../api/hengxin/execution-data'

export interface ExecutionContext { taskId: string; roundId: string; identity: string; active: boolean; mock: boolean }
export interface ExecutionState { data?: ExecutionData; loading: boolean; error: string }
export interface ExecutionScheduler { schedule: (run: () => void, ms: number) => () => void }
const scheduler: ExecutionScheduler = { schedule(run, ms) { const timer = setTimeout(run, ms); return () => clearTimeout(timer) } }
// The same controller powers the UI and deterministic tests; each context invalidates all older work.
export function createExecutionPoller(fetcher: (taskId: string, roundId: string) => Promise<ExecutionData>,
  publish: (state: ExecutionState) => void, clock: ExecutionScheduler = scheduler) {
  let generation = 0, context: ExecutionContext | undefined, cancel: (() => void) | undefined
  let state: ExecutionState = { loading: false, error: '' }
  const send = (next: ExecutionState) => { state = next; publish(next) }
  function invalidate() { generation++; cancel?.(); cancel = undefined }
  async function load() {
    const owner = context
    if (!owner?.active || owner.mock || !owner.identity || !owner.taskId || !owner.roundId) return
    invalidate()
    const ticket = generation
    send({ ...state, loading: !state.data, error: '' })
    try {
      const data = await fetcher(owner.taskId, owner.roundId)
      if (ticket !== generation) return
      if (data.taskId !== owner.taskId || data.roundId !== owner.roundId) throw new Error('Mismatched execution')
      send({ data, loading: false, error: '' })
      const delay = executionPollDelay(data.status)
      if (delay !== null) cancel = clock.schedule(() => { if (ticket === generation) void load() }, delay)
    } catch {
      if (ticket !== generation) return
      // Never expose raw server/proxy errors, logs or machine details.
      send({ ...state, loading: false, error: '执行过程暂时无法加载，请重试。任务状态以服务端为准。' })
    }
  }
  return {
    setContext(next: ExecutionContext) { invalidate(); context = { ...next }; send({ loading: false, error: '' }); void load() },
    retry() { if (!state.loading && state.error) void load() },
    dispose() { invalidate(); context = undefined; send({ loading: false, error: '' }) }
  }
}
