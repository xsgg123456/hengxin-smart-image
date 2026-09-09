import { reactive, watch } from 'vue'
import { ElMessage } from 'element-plus'

export type Mode = 'wallpaper' | 'product' | 'text'
export type Picture = { name: string; url: string; version?: number }
export type Template = { id: string; name: string; mode: Mode; images: Picture[]; skill: string; active: boolean }
export type Task = { id: string; name: string; mode: Mode; template: string; state: string; progress: number; images: Picture[]; feedback: string[]; time: string; archived: boolean; pending?: { target: number; note: string } }
export type Archive = { id: string; taskId?: string; name: string; mode: Mode; images: Picture[]; time: string }
export const labels: Record<Mode, string> = { wallpaper: '替换壁纸', product: '替换商品', text: '替换文字' }
export const skills: Record<Mode, string> = { wallpaper: '壁纸替换 Skill', product: '商品替换 Skill', text: '文字替换 Skill' }
export const sampleImages = (mode: Mode, n = 8): Picture[] => Array.from({ length: n }, (_, i) => ({ name: `主图 ${String(i + 1).padStart(2, '0')}`, url: `/samples/${mode}-${i % 4}.svg`, version: 1 }))
const seedTemplates: Template[] = [
  { id: 't1', name: '极简光影 · 手机屏幕套图', mode: 'wallpaper', images: sampleImages('wallpaper'), skill: skills.wallpaper, active: true },
  { id: 't2', name: '暮色山川 · 质感展示', mode: 'wallpaper', images: sampleImages('wallpaper', 6).reverse(), skill: skills.wallpaper, active: true },
  { id: 't3', name: '原色轻透 · 钢化膜系列', mode: 'product', images: sampleImages('product'), skill: skills.product, active: true },
  { id: 't4', name: '桌面好物 · 产品展示', mode: 'product', images: sampleImages('product', 4).reverse(), skill: skills.product, active: true }
]
const seedTasks: Task[] = [
  { id: 'HX0908-001', name: '秋日山川 · 手机屏幕系列', mode: 'wallpaper', template: seedTemplates[0].name, state: '待查看', progress: 100, images: sampleImages('wallpaper'), feedback: [], time: '今天 10:32', archived: false },
  { id: 'HX0908-002', name: '高清钢化膜 · 商品主图', mode: 'product', template: seedTemplates[2].name, state: '待查看', progress: 100, images: sampleImages('product'), feedback: [], time: '今天 10:18', archived: false },
  { id: 'HX0908-003', name: '新品上市 · 文案更新', mode: 'text', template: '无需模板', state: '失败', progress: 0, images: sampleImages('text', 4), feedback: ['演示异常：执行服务暂不可用，可点击重试。'], time: '今天 09:56', archived: false }
]
const key = 'hengxin-interaction-prototype-v1'
function initial() {
  try { const data = JSON.parse(localStorage.getItem(key) || 'null'); if (data?.version === 1 && Array.isArray(data.tasks) && Array.isArray(data.templates) && Array.isArray(data.archives)) return data } catch { /* reset damaged demo data */ }
  return { version: 1, templates: seedTemplates, tasks: seedTasks, archives: [{ id: 'a0', name: '初秋上新 · 屏幕展示套图', mode: 'wallpaper', images: sampleImages('wallpaper'), time: '2026-09-07 16:24' }] }
}
export const db = reactive(initial() as { version: number; templates: Template[]; tasks: Task[]; archives: Archive[] })
let warned = false
watch(db, () => { try { localStorage.setItem(key, JSON.stringify(db)) } catch { if (!warned) { ElMessage.warning('本地演示存储已满，本次数据仅保留在当前页面'); warned = true } } }, { deep: true })
export function stamp() { return new Date().toLocaleString('zh-CN', { hour12: false }) }
const active = new Set<string>()
export function run(task: Task, target = -1, note = '') {
  if (active.has(task.id)) return
  active.add(task.id)
  const resumed = !!task.pending
  if (task.pending) { target = task.pending.target; note = task.pending.note }
  task.pending = { target, note }
  task.state = '排队中'; task.progress = 0
  if (note && !resumed) task.feedback.unshift(`${stamp()} · ${target < 0 ? '整套' : `第 ${target + 1} 张`}：${note}`)
  const timer = window.setInterval(() => {
    task.state = '执行中'; task.progress += 25
    if (task.progress >= 100) {
      clearInterval(timer); active.delete(task.id); task.state = '待查看'; task.progress = 100
      if (note) task.archived = false
      if (note) task.images = task.images.map((p, i) => target < 0 || i === target ? { ...p, version: (p.version || 1) + 1 } : p)
      delete task.pending
      ElMessage.success('演示流程完成，可以查看示例图片')
    }
  }, 700)
}
db.tasks.filter(t => ['执行中', '排队中'].includes(t.state)).forEach(t => run(t))
export function createTask(mode: Mode, name: string, template?: Template, sources?: Picture[]) {
  const task: Task = { id: `HX-${Date.now()}`, name, mode, template: template?.name || '无需模板', state: '排队中', progress: 0, images: sampleImages(mode, template?.images.length || sources?.length || 4), feedback: [], time: stamp(), archived: false }
  db.tasks.unshift(task)
  const saved = db.tasks[0]; run(saved); return saved
}
export function archiveTask(task: Task) {
  if (task.state !== '待查看' || task.archived) return
  db.archives.unshift({ id: `A-${Date.now()}`, taskId: task.id, name: task.name, mode: task.mode, images: task.images.map(p => ({ ...p })), time: stamp() })
  task.archived = true; ElMessage.success('已归档，可在成品库查看')
}
export function removeArchive(archive: Archive) {
  db.archives = db.archives.filter(a => a.id !== archive.id)
  const task = db.tasks.find(t => t.id === archive.taskId)
  if (task) task.archived = db.archives.some(a => a.taskId === task.id && JSON.stringify(a.images) === JSON.stringify(task.images))
}
export async function readPictures(files: File[]): Promise<Picture[]> {
  const valid = files.filter(f => /^image\/(png|jpeg|webp)$/.test(f.type) && f.size <= 10 * 1024 * 1024)
  if (valid.length !== files.length) ElMessage.warning('原型仅接收 10 MB 内的 JPG、PNG、WebP 图片')
  return Promise.all(valid.map(file => new Promise<Picture>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const url = String(reader.result); const img = new Image()
      img.onload = () => resolve({ name: file.name, url })
      img.onerror = () => reject(new Error('图片文件无法解码'))
      img.src = url
    }
    reader.onerror = () => reject(new Error('图片读取失败')); reader.readAsDataURL(file)
  })))
}
