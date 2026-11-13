import { onBeforeUnmount, reactive, watch } from 'vue'
import type { StudioPicture } from '@/api/shared/studio'
import { loadStudioImage } from '../studio-images'
import { decodeImage } from './state'

export function useBoardImages(pictures: () => StudioPicture[]) {
  const images = reactive<Record<string, { url: string; width: number; height: number; error: string }>>({})
  let controller = new AbortController(), epoch = 0
  function clear() {
    controller.abort(); controller = new AbortController(); ++epoch
    for (const key of Object.keys(images)) { URL.revokeObjectURL(images[key].url); delete images[key] }
  }
  async function load(picture: StudioPicture) {
    const token = epoch, signal = controller.signal
    images[picture.id] = { url: '', width: picture.width || 1, height: picture.height || 1, error: '' }
    try {
      const result = await decodeImage(await loadStudioImage(picture, signal))
      if (token !== epoch || signal.aborted) { URL.revokeObjectURL(result.url); return }
      images[picture.id] = { url: result.url, width: result.image.naturalWidth, height: result.image.naturalHeight, error: '' }
    } catch (error) { if (token === epoch && !signal.aborted) images[picture.id].error = error instanceof Error ? error.message : '图片读取失败' }
  }
  watch(() => pictures().map(p => `${p.id}:${p.url}`).join('|'), () => { clear(); pictures().forEach(p => { void load(p) }) }, { immediate: true })
  onBeforeUnmount(clear)
  return images
}
