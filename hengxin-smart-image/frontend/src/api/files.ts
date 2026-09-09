import type { Mode } from '../types/hengxin'
import { getService, isMockMode } from './hengxin/client'
import { MAX_IMAGES } from './hengxin/limits'
export async function uploadFile(file: File) { return (await getService()).uploadFile(file) }
export async function getExamplePictures(mode: Mode, count: number) {
  if (!isMockMode) throw new Error('示例素材只在模拟模式可用')
  if (count < 1 || count > MAX_IMAGES) throw new Error('每组图片需要 1–20 张')
  const { sampleImages } = await import('./hengxin/fixtures')
  return sampleImages(mode, count)
}
