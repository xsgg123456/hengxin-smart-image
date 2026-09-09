import type { Mode, Picture } from '../../types/hengxin'
import { isMockMode } from './client'

export async function loadExamples(mode: Mode, count?: number): Promise<Picture[]> {
  if (!isMockMode) throw new Error('示例素材只在模拟模式可用')
  const { sampleImages } = await import('./fixtures')
  return sampleImages(mode, count)
}
/** 只读取本地预览；沿用原型限制，待 Phase 2 确认正式规格。 */
export async function readPictures(files: File[]): Promise<Picture[]> {
  if (files.some(file => !/^image\/(png|jpeg|webp)$/.test(file.type) || !file.size || file.size > 10 * 1024 * 1024)) {
    throw new Error('预览仅接收非空且不超过 10 MiB 的 JPG、PNG、WebP 图片')
  }
  return Promise.all(files.map(file => new Promise<Picture>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => {
      const url = String(reader.result)
      const image = new Image()
      image.onload = () => resolve({ name: file.name, url })
      image.onerror = () => reject(new Error('图片文件无法解码'))
      image.src = url
    }
    reader.onerror = () => reject(new Error('图片读取失败'))
    reader.readAsDataURL(file)
  })))
}
