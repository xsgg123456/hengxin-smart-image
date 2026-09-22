import { reactive } from 'vue'
import type { Picture } from '@/types/hengxin'

export type Scenario = 'success' | 'retry' | 'partial'
export type ItemState = '等待处理' | '处理中' | '等待重试' | '成功' | '失败'
export interface Revision {
  state: Exclude<ItemState, '等待处理'>; text: string; annotation?: Picture; operator: string
  retries: number; nextAt: number; scenario: Scenario; base: Picture
}
export interface ResultVersion {
  number: number; picture: Picture; created: string; operator: string; text: string
  annotation?: Picture; baseVersion?: number
}
export interface EditItem {
  source: Picture; state: ItemState; retries: number; nextAt: number; result?: Picture; revision?: Revision; versions?: ResultVersion[]
}
export interface EditTask {
  id: string; name: string; prompt: string; material: Picture; items: EditItem[]
  created: string; scenario: Scenario; events: string[]; operator?: string
}
export const currentOperator = '张三（演示）'
export const preview = reactive({
  images: [] as Picture[], name: '', prompt: '', scenario: 'retry' as Scenario,
  tasks: [] as EditTask[], paused: false, pendingUploads: 0
})
let serial = 0
let seeded = false
const active = (state: ItemState) => ['等待处理', '处理中', '等待重试'].includes(state)
const stamp = () => new Date().toLocaleString('zh-CN', { hour12: false })
function record(task: EditTask, message: string) {
  task.events.unshift(`${stamp()} · ${currentOperator} · ${message}`)
}
export const examplePictures = (count = 5): Picture[] => Array.from({ length: count }, (_, i) => ({
  name: `手机主图-${String(i + 1).padStart(2, '0')}.jpg`, url: `/demo-images/sample-${i % 4 + 1}.jpg`
}))
export function fillExample() {
  preview.images = [...examplePictures(11), { name: '共用壁纸素材.svg', url: '/samples/api-material.svg' }]
  preview.name = '秋日上新 · 手机屏幕套图'
  preview.prompt = '将原图中所有手机屏幕内的壁纸替换为素材图，保持手机外观、文案、布局、背景和其他设计元素不变。'
}
export function taskState(task: EditTask) {
  if (task.items.some(item => ['处理中', '等待重试'].includes(item.state) ||
    (item.revision && active(item.revision.state)))) return '处理中'
  if (task.items.some(item => item.state === '等待处理')) return '排队中'
  const count = task.items.filter(item => item.state === '成功' && item.revision?.state !== '失败').length
  return count === task.items.length && count > 0 ? '全部成功' : count ? '部分失败' : '全部失败'
}
function makeTask(pictures: Picture[], scenario: Scenario, name: string, prompt: string): EditTask {
  return {
    id: `API-${Date.now()}-${++serial}`, name, prompt, material: pictures.pop()!,
    items: pictures.map(source => ({ source, state: '等待处理', retries: 0, nextAt: 0 })),
    created: stamp(), scenario, operator: currentOperator, events: [`${stamp()} · ${currentOperator} · 演示任务已受理，每批最多10张。`]
  }
}
export function submitPreview() {
  if (!['demo', 'mock'].includes(import.meta.env?.MODE || '')) throw new Error('此功能仅用于交互预览')
  if (preview.pendingUploads || preview.images.length < 2 || !preview.name.trim() || !preview.prompt.trim()) throw new Error('请补全任务信息，并等待图片读取完成')
  const task = makeTask(preview.images.map(image => ({ ...image })), preview.scenario, preview.name.trim(), preview.prompt.trim())
  preview.tasks.unshift(task)
  preview.images = []; preview.name = ''; preview.prompt = ''
  return task.id
}
export function startScenario(scenario: Scenario): string {
  const task = makeTask([...examplePictures(11), { name: '共用素材.svg', url: '/samples/api-material.svg' }],
    scenario, `11张套图 · ${scenario === 'success' ? '全部成功' : scenario === 'retry' ? '自动重试' : '重试耗尽'}演示`, '示例提示词，仅本地模拟。')
  preview.tasks.unshift(task)
  return task.id
}
export function ensureExamples(): void {
  if (seeded) return
  seeded = true
  for (const scenario of ['partial', 'success', 'retry'] as const) {
    startScenario(scenario)
    const task = preview.tasks[0]
    if (scenario === 'retry') continue
    task.items.forEach((item, index) => {
      item.state = scenario === 'partial' && index === 2 ? '失败' : '成功'
      if (item.state === '成功') item.result = sampleResult(index)
      else item.retries = 3
    })
    record(task, scenario === 'success' ? '全部示例结果已就绪，可下载ZIP。' : '原图3重试3次耗尽；其余成功结果已保留。')
  }
}
export function batchInfo(task: EditTask): { current: number; total: number; running: number } {
  const first = task.items.findIndex(item => active(item.state))
  const total = Math.ceil(task.items.length / 10)
  return { current: first < 0 ? total : Math.floor(first / 10) + 1, total,
    running: task.items.filter(item => item.state === '处理中' || item.revision?.state === '处理中').length }
}
export function retryFailed(task: EditTask) {
  if (['处理中', '排队中'].includes(taskState(task))) return
  task.scenario = 'success'
  task.items.forEach((item, index) => {
    if (item.state === '失败') { item.state = '等待处理'; item.retries = 0; item.nextAt = 0 }
    if (item.revision?.state === '失败') retryRevision(task, index)
  })
  record(task, '已重新排入失败图片；本轮演示成功恢复，成功项保持不变。')
}
export function requestRevision(task: EditTask, index: number, text: string, annotation?: Picture, scenario: Scenario = 'success'): void {
  const item = task.items[index]
  if (!item || item.state !== '成功' || !item.result) throw new Error('仅成功图片可修改')
  if (item.revision && item.revision.state !== '成功') throw new Error('当前修改未完成，请等待或继续重试')
  if (!text.trim() && !annotation) throw new Error('请填写修改意见或上传标注图')
  getVersions(task, index)
  item.revision = { state: '处理中', text: text.trim(), annotation, operator: currentOperator,
    retries: 0, nextAt: Date.now() + 2400, scenario, base: { ...item.result } }
  record(task, `原图 ${index + 1}：提交单图修改，保留当前结果。`)
}
export function retryRevision(task: EditTask, index: number): void {
  const revision = task.items[index]?.revision
  if (!revision || revision.state !== '失败') return
  revision.state = '处理中'; revision.retries = 0; revision.nextAt = Date.now() + 2400
  revision.scenario = 'success'; revision.operator = currentOperator
  record(task, `原图 ${index + 1}：继续重试单图修改，保留旧结果。`)
}
function sampleResult(index: number): Picture {
  return { name: `示例结果-${index + 1}.jpg`, url: `/demo-images/sample-${index % 4 + 1}.jpg`, version: 1 }
}
export function getVersions(task: EditTask, index: number): ResultVersion[] {
  const item = task.items[index]
  if (!item) return []
  if (!item.versions && item.result) item.versions = [{ number: item.result.version || 1,
    picture: { ...item.result }, created: task.created, operator: task.operator || currentOperator, text: '首次生成' }]
  return item.versions || []
}
export function restoreVersion(task: EditTask, index: number, number: number): void {
  const item = task.items[index]
  if (!item?.result || item.state !== '成功') throw new Error('此图还没有可用结果')
  if (item.revision && item.revision.state !== '成功') throw new Error('请等待修改完成或重试失败的修改')
  const version = getVersions(task, index).find(version => version.number === number)
  if (!version) throw new Error('版本不存在')
  if ((item.result.version || 1) === number) return
  item.result = { ...version.picture, version: number }
  record(task, `原图 ${index + 1}：将 V${number} 设为当前结果，其他版本保留。`)
}
export function startVersionExample(): string {
  const id = startScenario('success'), task = preview.tasks[0]
  task.name = '单图版本管理 · 三版对比演示'
  task.items.forEach((item, index) => { item.state = '成功'; item.result = sampleResult(index); getVersions(task, index) })
  const item = task.items[0], versions = getVersions(task, 0)
  for (const number of [2, 3]) {
    const picture = { name: `示例修改结果-1-v${number}.jpg`, url: `/demo-images/sample-${number}.jpg`, version: number }
    versions.push({ number, picture, created: stamp(), operator: currentOperator, baseVersion: number - 1,
      text: number === 2 ? '请调整屏幕区域，保留其他内容。（演示说明）' : '请再检查屏幕边缘的贴合效果。（演示说明）' })
    item.result = { ...picture }
  }
  record(task, '三版示例已就绪，图片仅用于演示版本切换，不代表真实修改效果。')
  return id
}
function advance(task: EditTask, index: number, now: number, revision?: Revision) {
  const item = task.items[index], work = revision || item
  if (work.state === '等待处理' || (work.state === '等待重试' && now >= work.nextAt)) {
    work.state = '处理中'; work.nextAt = now + 2400
    record(task, `原图 ${index + 1}${revision ? '修改' : ''}：${work.retries ? `开始第 ${work.retries} 次重试` : '开始处理'}。`)
  } else if (work.state === '处理中' && now >= work.nextAt) {
    const scenario = revision?.scenario || task.scenario
    const fails = (revision || index === Math.min(2, task.items.length - 1)) &&
      (scenario === 'partial' || (scenario === 'retry' && work.retries === 0))
    if (fails && work.retries < 3) {
      const delay = 2 ** work.retries
      work.retries++; work.state = '等待重试'; work.nextAt = now + delay * 1000
      record(task, `原图 ${index + 1}${revision ? '修改' : ''}：模拟服务暂不可用，${delay} 秒后第 ${work.retries}/3 次重试。`)
    } else if (fails) {
      work.state = '失败'
      record(task, `原图 ${index + 1}${revision ? '修改' : ''}：3次重试已用尽，${revision ? '旧结果已保留，可继续重试' : '保留其他成功图片'}。`)
    } else {
      work.state = '成功'
      if (revision) {
        const previous = Number(revision.base.url.match(/sample-(\d)/)?.[1] || 0)
        const versions = getVersions(task, index)
        const version = Math.max(...versions.map(version => version.number), 0) + 1
        item.result = { name: `示例修改结果-${index + 1}-v${version}.jpg`,
          url: `/demo-images/sample-${previous % 4 + 1}.jpg`, version }
        versions.push({ number: version, picture: { ...item.result }, created: stamp(), operator: revision.operator,
          text: revision.text, annotation: revision.annotation ? { ...revision.annotation } : undefined, baseVersion: revision.base.version || 1 })
      } else { item.result = sampleResult(index); getVersions(task, index)[0].created = stamp() }
      record(task, `原图 ${index + 1}：${revision ? '修改示例已更新（仅模拟）' : '示例结果已就绪'}。`)
    }
  }
}
export function tick(now = Date.now()) {
  if (preview.paused) return
  for (const task of preview.tasks) task.items.forEach((item, index) => {
    if (item.revision && active(item.revision.state)) advance(task, index, now, item.revision)
  })
  const task = [...preview.tasks].reverse().find(task => task.items.some(item => active(item.state)))
  if (!task) return
  const first = task.items.findIndex(item => active(item.state)), start = Math.floor(first / 10) * 10
  // Freeze the batch for this tick: the next batch cannot start until every member is terminal.
  for (let index = start; index < Math.min(start + 10, task.items.length); index++) {
    if (active(task.items[index].state)) advance(task, index, now)
  }
}
const timer = ['demo', 'mock'].includes(import.meta.env?.MODE || '') ? setInterval(tick, 250) : undefined
if (import.meta.hot) import.meta.hot.dispose(() => clearInterval(timer))
