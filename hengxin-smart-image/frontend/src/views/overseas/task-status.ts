import { taskStatuses } from '@/api/overseas/tasks'

type RawStatus = keyof typeof taskStatuses
export const taskGroups = { pending: '待处理', designing: '设计中', completed: '已完成' }
type Group = keyof typeof taskGroups

export function taskGroup(status: RawStatus): Group | null {
  switch (status) {
    case 'created': case 'submitted': case 'pending_review': case 'returned': return 'pending'
    case 'studio': case 'analyzing': case 'analysisFailed': case 'plan': case 'generating':
    case 'generationFailed': case 'review': case 'reworking': return 'designing'
    case 'completed': case 'archived': return 'completed'
    default: return null
  }
}
export function taskStatusLabel(status: RawStatus) {
  const group = taskGroup(status)
  return group ? taskGroups[group] : taskStatuses[status]
}
export function taskStatusNote(status: RawStatus) {
  if (status === 'created') return '待提交人提交图需'
  if (status === 'submitted') return '待开始分析'
  if (status === 'pending_review') return '待设计审核图需'
  if (status === 'returned') return '待提交人补充资料'
  return ''
}
export function taskStatusTone(status: RawStatus) {
  if (status === 'delete_failed') return 'danger'
  if (status === 'deleting' || taskGroup(status) === 'pending') return 'warning'
  return taskGroup(status) === 'completed' ? 'success' : 'primary'
}
