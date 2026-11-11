import { ref } from 'vue'
export const scenes = { normal: '正常数据', empty: '空数据', loading: '加载中', error: '加载失败', degraded: '服务异常' }
export const scene = ref<keyof typeof scenes>('normal')
export const people = ['陈佳', '林晓', '王宁', '李晴', '周晨', '赵悦'].map((name, i) => ({ id: `person-${i}`, name }))
export const kinds = { initial: '首次生成', api_edit: 'API 修改', cli_edit: 'CLI 修改' }
export type Kind = keyof typeof kinds
export const statuses = { queued: '排队中', running: '执行中', retry_wait: '等待重试', collecting: '收图中', cancelling: '取消中', uncertain: '待核实', failed: '失败', succeeded: '已完成', cancelled: '已取消' }
export type Status = keyof typeof statuses
export interface RecordItem { id: string; task: string; personId: string; person: string; kind: Kind; status: Status; createdAt: string; startedAt: string | null; finishedAt: string | null; images: number; seconds: number | null; retry: boolean; error: string }
const stateList: Status[] = ['queued', 'running', 'uncertain', 'failed', 'collecting', 'retry_wait', 'cancelling', 'cancelled']
const titles = ['落地灯客厅场景', '床头灯主图优化', '落地灯尺寸说明', '台灯细节展示', '边桌灯生活方式图', '客厅灯组合展示']
export const records: RecordItem[] = Array.from({ length: 48 }, (_, i) => {
  const person = people[i % people.length]!
  const kind: Kind = i % 4 === 1 ? 'cli_edit' : i % 4 === 2 ? 'api_edit' : 'initial'
  const status = i < 8 ? stateList[i]! : 'succeeded'
  const day = 11 - Math.floor(i / 8), hour = 16 - i % 8
  const createdAt = `2026-11-${String(day).padStart(2, '0')}T${String(hour).padStart(2, '0')}:20:00+08:00`
  const started = !['queued', 'cancelled'].includes(status)
  const seconds = status === 'succeeded' || status === 'failed' ? 42 + i * 3 : null
  return { id: `DEMO-${1048 - i}`, task: titles[i % titles.length]!, personId: person.id, person: person.name, kind, status, createdAt,
    startedAt: started ? createdAt : null, finishedAt: seconds === null ? null : new Date(Date.parse(createdAt) + seconds * 1000).toISOString(),
    images: status === 'succeeded' ? kind === 'cli_edit' ? 2 : 1 : 0, seconds, retry: kind !== 'cli_edit' && i % 7 === 0,
    error: status === 'failed' ? '上游图片服务返回失败，本次未产生新图片。' : status === 'uncertain' ? '尚未确认最终执行结果，请核对后再决定是否重试。' : '' }
})
export function groupStatus(row: RecordItem) { return ['running', 'collecting', 'cancelling', 'retry_wait'].includes(row.status) ? 'running' : row.status }
export function summary(rows: RecordItem[]) { return { images: rows.reduce((sum, row) => sum + row.images, 0), api: rows.filter(row => row.kind !== 'cli_edit').length, cli: rows.filter(row => row.kind === 'cli_edit' && row.startedAt).length } }
export function filterRecords(rows: RecordItem[], person = '', dates: string[] | null = null, kind = '') {
  return rows.filter(row => (!person || row.personId === person) && (!kind || row.kind === kind) && (!dates?.length || (row.createdAt.slice(0, 10) >= dates[0]! && row.createdAt.slice(0, 10) <= dates[1]!)))
}
