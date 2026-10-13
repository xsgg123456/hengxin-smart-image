import { cleanDraft, type TaskDetail } from '@/api/overseas/tasks'
import type { Material } from '@/api/overseas/materials'
export function formatTaskTime(value: string) {
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? '—' : date.toLocaleString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hour12: false })
}
export function taskToDraft(task: TaskDetail) {
  return cleanDraft({ ...task, designerId: task.designer.id, materialIds: undefined })
}
export function resubmitMaterialIds(files: Material[], taskId: string) {
  if (!files.length || files.length > 2 || files.some(f => f.status !== 'ready' || (f.taskId !== null && f.taskId !== taskId))) throw Error('至少保留一份解析成功的资料；请移除或重试失败资料')
  if (new Set(files.map(f => f.kind)).size !== files.length || new Set(files.map(f => f.id)).size !== files.length) throw Error('每类资料仅支持一份')
  return files.map(f => f.id)
}
