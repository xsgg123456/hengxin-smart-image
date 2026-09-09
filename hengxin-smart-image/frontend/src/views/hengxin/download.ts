import type { Picture } from '@/types/hengxin'
import { ElMessage } from 'element-plus'
import { readImage, prepareSet, safeFilename } from './download-helpers'
function save(blob: Blob, name: string) {
  const url = URL.createObjectURL(blob), a = document.createElement('a')
  try { a.href = url; a.download = name; document.body.append(a); a.click() }
  finally { a.remove(); setTimeout(() => URL.revokeObjectURL(url), 2000) }
}
export async function downloadPicture(p: Picture): Promise<void> {
  try {
    const { data, extension, mime } = await readImage(p.url)
    save(new Blob([data], { type: mime }), safeFilename(p.name, extension))
  } catch { ElMessage.error('下载失败：图片不可用或请求超时，请重试') }
}
export async function downloadSet(images: Picture[], name: string): Promise<void> {
  try { save(await prepareSet(images), safeFilename(name, 'zip')) }
  catch { ElMessage.error('打包失败：请检查图片并重试，未下载残缺套图') }
}
