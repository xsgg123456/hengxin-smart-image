import type { Picture } from '@/types/hengxin'
import { ElMessage } from 'element-plus'
import { isMockMode } from '@/api/hengxin/client'
import { readImage, prepareSet, safeFilename, requestDownload, imageExtension } from './download-helpers'
const apiUrl = import.meta.env.VITE_API_URL || '/api/v1'
function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob), a = document.createElement('a')
  try { a.href = url; a.download = name; document.body.append(a); a.click() }
  finally { a.remove(); setTimeout(() => URL.revokeObjectURL(url), 2000) }
}
export async function downloadPicture(p: Picture): Promise<void> {
  try {
    if (!isMockMode) {
      const blob = await requestDownload(apiUrl, [p.fileId])
      const extension = imageExtension(new Uint8Array(await blob.arrayBuffer()), blob.type.split(';')[0])
      save(blob, safeFilename(p.name, extension))
      return
    }
    const { data, extension, mime } = await readImage(p.url)
    save(new Blob([data], { type: mime }), safeFilename(p.name, extension))
  } catch (error) { ElMessage.error(error instanceof Error ? `下载失败：${error.message}` : '下载失败，请重试') }
}
export async function downloadSet(images: Picture[], name: string): Promise<void> {
  try {
    const blob = isMockMode ? await prepareSet(images) : await requestDownload(apiUrl, images.map(image => image.fileId), name)
    save(blob, safeFilename(name, 'zip'))
  } catch (error) { ElMessage.error(error instanceof Error ? `打包失败：${error.message}` : '打包失败，请重试') }
}
