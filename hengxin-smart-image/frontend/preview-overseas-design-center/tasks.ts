import type { CreateSubmission } from './form-data'

export interface PreviewTask extends Omit<CreateSubmission, 'materials'> {
  designType?: 'custom' | 'platform'
  requestKey?: string
  id: string
  createdAt: string
  materials?: CreateSubmission['materials']
}
const base = [
  ['Amazon', 'GN-0008', '落地灯客厅场景套图', '落地灯', 'OUTON'],
  ['Wayfair', 'WF-0312', '休闲椅详情页', '布艺休闲椅', 'HOMCOM'],
  ['Mercado Libre', 'ML-0206', '头戴式耳机商品主图', '无线耳机', 'SOUND'],
  ['Walmart', 'WM-0081', '珐琅锅厨房场景图', '珐琅锅', 'HEARTH'],
  ['The Home Depot', 'HD-0536', '电钻功能展示图', '充电电钻', 'TOOLBOX'],
  ['Shopee', 'SP-0118', '保温杯商品套图', '带柄保温杯', 'DAYLIFE'],
]
const seed: PreviewTask[] = base.map(([platform,sku,title,productName,brand],i) => ({
  id: 'HX-' + (2001+i), sku,title,productName,brand,platform,
  designer:i % 3 === 1 ? '林悦' : '张帅',language:'en', createdAt:new Date(Date.UTC(2026,10,18-i,2,15)).toISOString(),
}))
const key = 'hx-design-center-preview-v1'
export function readTasks(): PreviewTask[] {
  try { return [...JSON.parse(localStorage.getItem(key) || '[]'), ...seed] } catch { return [...seed] }
}
export function persistTasks(tasks: PreviewTask[]) {
  localStorage.setItem(key, JSON.stringify(tasks.filter(x => x.id.startsWith('HX-N')), (k,v) => k === 'file' ? undefined : v))
}

