import type { Task, TaskDetailData } from '../../types/hengxin'

export const taskPollDelay = (tasks: Task[]) => tasks.some(task => ['排队中', '执行中'].includes(task.state)) ? 3000 : 10000
export const fixtureNotice = (task: Task) => task.executionSource === 'fixture'
  ? '测试执行器：本任务及以下结果仅用于验证队列与文件流程，未调用真实 Skill 生成。' : ''
export function taskActions(data: TaskDetailData | undefined, busy: boolean, error: string) {
  return {
    canRevise: !!data?.executionControl.canRevise && !busy && !error,
    canRetry: !!data?.executionControl.canRetry && !busy && !error
  }
}
