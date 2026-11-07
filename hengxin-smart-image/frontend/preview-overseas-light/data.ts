import type { TaskSummary } from '@/api/overseas/tasks'
import type { Archive, ArchiveEvent } from '@/api/overseas/archives'
import type { Job, ManagementApi, ManagementQuery, Usage } from '@/api/overseas/management'
export const people = [{ id: 'zhang', name: '张帅' }, { id: 'hu', name: '胡礼辉' }, { id: 'chen', name: '陈晓（示例）' }, { id: 'lin', name: '林悦（示例）' }]
const products = ['层架灯-正方形四层普通泡款-美规-黑色H-CJD001101-US-BK', '直杆实木布罩灯-乡村风-12W遥控灯泡-美规-胡桃木色H-ZGD000801-US-WT', 'HomeDepot IT通用测试-1106-张帅', 'WALMART IT通用测试-1104-张帅', 'WAYFAIR IT通用测试-1104-张帅', '小平台IT通用测试-1104-张帅']
export const tasks: TaskSummary[] = Array.from({ length: 47 }, (_, i) => ({
  id: `5946b5af-e39b-42fc-98fc-${String(i + 1).padStart(12, '0')}`, name: products[i % 6] + (i > 5 ? ` · ${Math.floor(i / 6) + 1}` : ''),
  productName: ['层架灯', '直杆实木布罩灯', 'HomeDepot IT通用测试-1106-张帅', 'WALMART IT通用测试-1104-张帅', 'WAYFAIR IT通用测试-1104-张帅', '小平台IT通用测试-1104-张帅'][i % 6], brand: 'OUTON', platform: ['Wayfair', 'Wayfair', 'The Home Depot', 'Walmart', 'Wayfair', 'Mercado Libre'][i % 6],
  language: 'en', market: '', remarks: '', skus: [{ code: i % 2 ? 'ZGD000801-US-WT' : 'CJD001101-US-BK' }],
  workflow: i >= 43 ? 'legacy' : 'studio',
  status: i === 1 ? 'pending_review' : i === 2 ? 'returned' : i === 6 ? 'created' : i === 43 ? 'archived' : i === 44 ? 'generationFailed' : i === 45 ? 'plan' : i === 46 ? 'review' : i === 3 || i % 11 === 8 ? 'completed' : 'studio', version: 1,
  createdAt: new Date(Date.UTC(2026, 10, 6, 8, 12) - i * 9 * 3600000).toISOString(), updatedAt: '2026-11-07T02:00:00Z',
  createdBy: people[(i + 1) % 4], designer: { ...people[i % 4], status: 'active', eligible: true }, capabilities: ['task.read'],
}))
const designTasks = tasks.filter(t => t.status === 'studio' || t.status === 'completed')
export const jobs: Job[] = Array.from({ length: 68 }, (_, i) => {
  const status = i < 3 ? 'running' : i < 5 ? 'queued' : i === 5 ? 'uncertain' : i % 13 === 0 ? 'failed' : 'succeeded'
  const at = Date.UTC(2026, 10, 7, 2, 20) - i * 4 * 3600000
  return { id: `job-${String(i + 1).padStart(4, '0')}`, taskId: designTasks[i % designTasks.length].id, taskName: designTasks[i % designTasks.length].name,
    kind: 'studio', status, executionCount: status === 'queued' ? 0 : i % 13 === 0 ? 2 : 1,
    imageCount: status === 'succeeded' ? 3 + i % 6 : 0, operatorId: people[i % 4].id, operatorName: people[i % 4].name,
    createdAt: new Date(at).toISOString(), startedAt: status === 'queued' ? null : new Date(at + 10000).toISOString(),
    completedAt: ['succeeded', 'failed'].includes(status) ? new Date(at + (6 + i % 9) * 60000).toISOString() : null,
    error: status === 'failed' ? '执行超时，未收到完整产物。可进入来源任务查看本轮会话。' : status === 'uncertain' ? '执行器心跳中断，正在核实执行结果。' : null }
})
export function selectJobs(query: Partial<ManagementQuery>) {
  return jobs.filter(j => (!query.memberId || j.operatorId === query.memberId) && (!query.status || j.status === query.status)
    && (!query.kind || j.kind === query.kind) && (!query.taskId || (j.taskId + j.taskName).toLowerCase().includes(query.taskId.toLowerCase()))
    && (!query.from || j.createdAt >= query.from) && (!query.to || j.createdAt <= query.to))
}
export function summarize(rows: Job[]): Usage {
  return { jobs: rows.length, queued: rows.filter(j => j.status === 'queued').length, running: rows.filter(j => j.status === 'running').length,
    uncertain: rows.filter(j => j.status === 'uncertain').length, succeeded: rows.filter(j => j.status === 'succeeded').length,
    failed: rows.filter(j => j.status === 'failed').length, cancelled: 0, generationImages: rows.reduce((n, j) => n + j.imageCount, 0), revisionImages: 0 }
}
const unavailable = async (): Promise<never> => { throw Error('此项不在本次预览范围内') }
export const managementApi: ManagementApi = {
  operators: async () => ({ items: people }), usage: async q => summarize(selectJobs(q)),
  people: async q => ({ items: people.map(p => { const rows = selectJobs(q).filter(j => j.operatorId === p.id); return { ...p, calls: rows.length, images: rows.reduce((n, j) => n + j.imageCount, 0), lastCall: rows[0]?.createdAt || '' } }).filter(p => p.calls) }),
  jobs: async q => { const rows = selectJobs(q); return { items: rows.slice((q.page - 1) * q.pageSize, q.page * q.pageSize), total: rows.length, page: q.page, pageSize: q.pageSize } },
  skills: unavailable, setSkillAvailability: unavailable, setSkillPlatforms: unavailable, settings: unavailable, saveSettings: unavailable,
}
export type DemoArchive = Archive & { history: ArchiveEvent[]; image: string }
const lampImages = [
  new URL('../preview-ai-studio/assets/sample-1.jpg', import.meta.url).href,
  new URL('../preview-ai-studio/assets/sample-2.jpg', import.meta.url).href,
  new URL('../preview-ai-studio/assets/sample-3.jpg', import.meta.url).href,
  new URL('../preview-ai-studio/assets/sample-4.jpg', import.meta.url).href,
]
export const archives: DemoArchive[] = designTasks.slice(0, 8).map((t, i) => {
  const history: ArchiveEvent[] = [0, 1].map((n) => ({ id: `event-${i}-${n}`, actorId: people[(i + n) % 4].id,
    actorName: people[(i + n) % 4].name, at: new Date(Date.UTC(2026, 10, 6 - i, 3 + n, 20)).toISOString(),
    pictures: [{ id: `picture-${i}-${n}`, name: n ? '场景图与细节图' : '商品主图', sku: t.skus[0].code }] }))
  return { id: `archive-${i}`, taskId: t.id, taskName: t.name, productName: t.productName, brand: t.brand, platform: t.platform,
    language: 'en', sourceDeleted: false, skus: t.skus, pictureCount: 6, createdAt: history[0].at, latestArchive: history[1], history,
    image: lampImages[i % 4] }
})
