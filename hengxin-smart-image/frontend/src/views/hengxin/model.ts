import { reactive, shallowReadonly } from 'vue'
import { ElMessage } from 'element-plus'
import { workspace as validWorkspace } from '../../api/hengxin/validate'
import { getService, isMockMode } from '../../api/hengxin/client'
import type { Archive, CreateTaskInput, Mode, Task, Template, Workspace } from '../../types/hengxin'
export type { Archive, Mode, Picture, Task, Template } from '../../types/hengxin'
export { loadExamples, readPictures } from '../../api/hengxin/local-pictures'
export const labels: Record<Mode, string> = { wallpaper: '替换壁纸', product: '替换商品', text: '替换文字' }
export const skills: Record<Mode, string> = { wallpaper: '壁纸替换 Skill', product: '商品替换 Skill', text: '文字替换 Skill' }

const state = reactive<Workspace>({ templates: [], tasks: [], archives: [] })
export const db = shallowReadonly(state)
export const connection = reactive({ loading: false, error: '' })
let timer: ReturnType<typeof setTimeout> | undefined
let refreshing: Promise<void> | undefined
let polling = false
export async function refreshWorkspace(): Promise<void> {
  if (refreshing) return refreshing
  refreshing = (async () => {
    connection.loading = true
    try {
      const snapshot = await (await getService()).getWorkspace()
      if (!validWorkspace(snapshot)) {
        throw new Error('工作区数据格式错误')
      }
      Object.assign(state, snapshot)
      connection.error = ''
    } catch (error) {
      connection.error = error instanceof Error ? error.message : '工作区加载失败'
      throw error
    } finally { connection.loading = false }
  })()
  try { await refreshing } finally { refreshing = undefined }
}
export function startPolling() {
  stopPolling()
  polling = true
  async function poll() {
    try { await refreshWorkspace() } catch { /* 提示由工作区显示 */ }
    if (polling) timer = setTimeout(poll, state.tasks.some(t => ['执行中', '排队中'].includes(t.state)) ? (isMockMode ? 1000 : 3000) : 10000)
  }
  timer = setTimeout(poll, 1000)
}
export function stopPolling() { polling = false; clearTimeout(timer) }
async function update<T>(action: () => Promise<T>): Promise<T> {
  const result = await action()
  // 先等待已有读取结束，再获取写入后的快照，避免复用旧请求。
  try { await refreshing } catch { /* 再次读取 */ }
  // 写操作已成功时，读取失败不能伪装成提交失败，避免用户重复创建。
  try { await refreshWorkspace() } catch { /* 工作区错误提示允许单独重载 */ }
  if (polling) startPolling()
  return result
}
export async function createTask(input: CreateTaskInput) {
  return update(async () => (await getService()).createTask(input))
}
export async function saveTemplate(template: Template) {
  return update(async () => (await getService()).saveTemplate(template))
}
export async function deleteTemplate(id: string) {
  return update(async () => (await getService()).deleteTemplate(id))
}
export async function run(task: Task, target = -1, note = '') {
  return update(async () => (await getService()).revise({ taskId: task.id, target: target < 0 ? null : target, note }))
}
export async function archiveTask(task: Task) {
  try {
    await update(async () => (await getService()).archive(task.id))
    ElMessage.success('已归档，可在成品库查看')
  } catch (error) { ElMessage.error(error instanceof Error ? error.message : '归档失败') }
}
export async function removeArchive(archive: Archive) {
  return update(async () => (await getService()).deleteArchive(archive.id))
}
