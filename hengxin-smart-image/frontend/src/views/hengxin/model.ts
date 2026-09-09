import { reactive } from 'vue'
import { workspace as validWorkspace } from '../../api/hengxin/validate'
import { getService } from '../../api/hengxin/client'
import type { Mode } from '../../types/hengxin'
export { createTask } from '../../api/tasks'
export type { Archive, Mode, Picture, Task, Template } from '../../types/hengxin'
export const labels: Record<Mode, string> = { wallpaper: '替换壁纸', product: '替换商品', text: '替换文字' }
export const connection = reactive({ loading: false, error: '' })
let refreshing: Promise<void> | undefined
/** 仅启动阶段的兼容检查；页面列表与详情各自查询，不共享过期快照。 */
export async function refreshWorkspace(): Promise<void> {
  if (refreshing) return refreshing
  refreshing = (async () => {
    connection.loading = true
    try {
      const snapshot = await (await getService()).getWorkspace()
      if (!validWorkspace(snapshot)) throw new Error('工作区数据格式错误')
      connection.error = ''
    } catch (error) {
      connection.error = error instanceof Error ? error.message : '工作区加载失败'
      throw error
    } finally { connection.loading = false }
  })()
  try { await refreshing } finally { refreshing = undefined }
}
