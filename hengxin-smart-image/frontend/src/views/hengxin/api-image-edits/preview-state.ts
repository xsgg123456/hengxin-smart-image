import { reactive } from 'vue'
import type { Picture } from '@/types/hengxin'

export type Scenario = 'success' | 'retry' | 'partial'
export type ItemState = '等待处理' | '处理中' | '等待重试' | '成功' | '失败'
export interface EditItem { source: Picture; state: ItemState; retries: number; nextAt: number; result?: Picture }
export interface EditTask {
  id: string; name: string; prompt: string; material: Picture; items: EditItem[]
  created: string; scenario: Scenario; events: string[]
}
export const preview = reactive({
  images: [] as Picture[], name: '', prompt: '', scenario: 'retry' as Scenario,
  tasks: [] as EditTask[], paused: false, pendingUploads: 0
})
export const examplePictures = (): Picture[] => Array.from({ length: 5 }, (_, i) => ({
  name: `手机主图-${String(i + 1).padStart(2, '0')}.jpg`, url: `/demo-images/sample-${i % 4 + 1}.jpg`
}))
export function fillExample() {
  preview.images = [...examplePictures(), { name: '共用壁纸素材.svg', url: '/samples/api-material.svg' }]
  preview.name = '秋日上新 · 手机屏幕套图'
  preview.prompt = '将原图中所有手机屏幕内的壁纸替换为素材图，保持手机外观、文案、布局、背景和其他设计元素不变。'
}
export function taskState(task: EditTask) {
  if (task.items.some(item => ['处理中', '等待重试'].includes(item.state))) return '处理中'
  if (task.items.some(item => item.state === '等待处理')) return '排队中'
  const count = task.items.filter(item => item.state === '成功').length
  return count === task.items.length ? '全部成功' : count ? '部分失败' : '全部失败'
}
export function submitPreview() {
  if (!['demo', 'mock'].includes(import.meta.env?.MODE || '')) throw new Error('此功能仅用于交互预览')
  if (preview.pendingUploads || preview.images.length < 2 || !preview.name.trim() || !preview.prompt.trim()) throw new Error('请补全任务信息，并等待图片读取完成')
  const pictures = preview.images.map(image => ({ ...image }))
  const task: EditTask = {
    id: `API-${Date.now()}`, name: preview.name.trim(), prompt: preview.prompt.trim(), material: pictures.pop()!,
    items: pictures.map(source => ({ source, state: '等待处理', retries: 0, nextAt: 0 })),
    created: new Date().toLocaleString('zh-CN', { hour12: false }), scenario: preview.scenario,
    events: ['演示任务已受理，图片顺序与提示词已保存。']
  }
  preview.tasks.unshift(task)
  preview.images = []; preview.name = ''; preview.prompt = ''
  return task.id
}
export function retryFailed(task: EditTask) {
  if (['处理中', '排队中'].includes(taskState(task))) return
  task.scenario = 'success'
  task.items.filter(item => item.state === '失败').forEach(item => {
    item.state = '等待处理'; item.retries = 0; item.nextAt = 0
  })
  task.events.unshift('已重新排入失败图片；本轮演示成功恢复，成功项保持不变。')
}
export function tick(now = Date.now()) {
  if (preview.paused) return
  const task = [...preview.tasks].reverse().find(item => ['处理中', '排队中'].includes(taskState(item)))
  if (!task) return
  const index = task.items.findIndex(item => ['等待处理', '处理中', '等待重试'].includes(item.state))
  const item = task.items[index]
  if (!item) return
  if (item.state === '等待处理' || (item.state === '等待重试' && now >= item.nextAt)) {
    item.state = '处理中'; item.nextAt = now + 2400
    task.events.unshift(`原图 ${index + 1}：${item.retries ? `开始第 ${item.retries} 次重试` : '开始处理'}。`)
  } else if (item.state === '处理中' && now >= item.nextAt) {
    const fails = index === Math.min(2, task.items.length - 1) &&
      (task.scenario === 'partial' || (task.scenario === 'retry' && item.retries === 0))
    if (fails && item.retries < 3) {
      const delay = 2 ** item.retries
      item.retries++; item.state = '等待重试'; item.nextAt = now + delay * 1000
      task.events.unshift(`原图 ${index + 1}：模拟服务暂不可用，${delay} 秒后第 ${item.retries}/3 次重试。`)
    } else if (fails) {
      item.state = '失败'; task.events.unshift(`原图 ${index + 1}：3 次重试已用尽，继续处理后续图片。`)
    } else {
      item.state = '成功'
      item.result = { name: `示例结果-${index + 1}.jpg`, url: `/demo-images/sample-${index % 4 + 1}.jpg` }
      task.events.unshift(`原图 ${index + 1}：示例结果已就绪。`)
    }
  }
}
const timer = ['demo', 'mock'].includes(import.meta.env?.MODE || '') ? setInterval(tick, 250) : undefined
if (import.meta.hot) import.meta.hot.dispose(() => clearInterval(timer))

