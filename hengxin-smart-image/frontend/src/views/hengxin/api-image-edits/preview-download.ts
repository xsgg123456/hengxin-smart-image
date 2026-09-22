import { prepareSet, safeFilename } from '../download-helpers'
import { taskState, type EditTask } from './preview-state'

const packing = new WeakSet<EditTask>()
function snapshot(task: EditTask) {
  if (taskState(task) !== '全部成功' || !task.items.length || task.items.some(item => !item.result)) {
    throw new Error('全部图片成功且所有修改完成后才能下载ZIP')
  }
  return task.items.map(item => {
    const result = item.result!
    const localBlob = typeof location !== 'undefined' && result.url.startsWith(`blob:${location.origin}/`)
    if (!/^\/demo-images\/sample-[1-4]\.jpg$/.test(result.url) && !localBlob) {
      throw new Error('演示下载仅允许本地示例图片')
    }
    return { name: result.name, url: result.url }
  })
}
export async function prepareTaskZip(task: EditTask): Promise<Blob> {
  const images = snapshot(task)
  const zip = await prepareSet(images)
  if (JSON.stringify(snapshot(task)) !== JSON.stringify(images)) throw new Error('打包期间结果已更新，请重新下载')
  return zip
}
export async function downloadTaskZip(task: EditTask): Promise<void> {
  if (packing.has(task)) throw new Error('正在打包，请稍候')
  packing.add(task)
  let url: string | undefined
  try {
    const zip = await prepareTaskZip(task)
    url = URL.createObjectURL(zip)
    const anchor = document.createElement('a')
    anchor.href = url; anchor.download = safeFilename(`${task.name}-示例结果`, 'zip')
    document.body.appendChild(anchor)
    anchor.click(); anchor.remove()
  } finally {
    packing.delete(task)
    if (url) { const captured = url; setTimeout(() => URL.revokeObjectURL(captured), 1000) }
  }
}
