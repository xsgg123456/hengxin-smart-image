import type { MonitorReport } from '../../../types/management'

export const monitorCount = (value: number | null) => value === null ? '未知' : String(value)
export const elapsedTime = (value: number | null) => value === null ? '未知' : `${Math.floor(value)} 秒`

export function monitorCoverage(report: Pick<MonitorReport, 'tasks' | 'taskCount'>) {
  return {
    summary: `已显示 ${report.tasks.length} 条 / 总数 ${monitorCount(report.taskCount)}${report.taskCount === null ? '' : ' 条'}`,
    truncated: report.taskCount !== null && report.tasks.length < report.taskCount,
    emptyText: report.taskCount === null ? '任务总数未知，暂无可展示记录' : report.taskCount > 0 ? '暂无可展示记录，请刷新重试' : '暂无排队、执行或异常任务'
  }
}
