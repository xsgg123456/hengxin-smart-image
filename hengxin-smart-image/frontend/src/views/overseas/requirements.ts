import { formatBeijingTime } from '@/utils/beijing-time'
import { cleanDraft, type TaskDetail } from '@/api/overseas/tasks'
import type { Material } from '@/api/overseas/materials'
export function formatTaskTime(value: string) { return formatBeijingTime(value, '—') }
export function taskToDraft(task: TaskDetail) {
  return cleanDraft({ ...task, language: task.language ?? '', designerId: task.designer.id, materialIds: undefined })
}
export function resubmitMaterialIds(files: Material[], taskId: string) {
  if (!files.length || files.length > 100 || files.some(f => (f.taskId !== null && f.taskId !== taskId))) throw Error('请保留 1–100 份已上传且属于当前任务的资料')
  if (new Set(files.map(f => f.id)).size !== files.length) throw Error('资料不能重复')
  return files.map(f => f.id)
}
