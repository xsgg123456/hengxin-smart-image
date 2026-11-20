import { OVERSEAS_PLATFORMS } from '../shared/skills/platforms'

export { OVERSEAS_PLATFORMS }

// 继续任务也能检索旧工作流使用的平台。
export const TASK_DESIGN_TYPES = [
  { value: 'custom', label: '自定义生图' },
  ...OVERSEAS_PLATFORMS,
  ...['TikTok Shop', 'Lazada', '其他'].map(value => ({ value, label: value })),
]

export function designTypeLabel(task: { designType?: string; platform: string }) {
  return task.designType === 'custom' ? '自定义生图' : task.platform
}
