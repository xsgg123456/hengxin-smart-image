import { computed, onUnmounted, ref, watch, type ComputedRef } from 'vue'
import { overseasImageCache, type ImageLease } from '@/api/overseas/image-cache'
import { imageUrl, type StudioImage } from './studio-images'

const loadingImage = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="280" height="100"><text x="140" y="55" fill="white" text-anchor="middle" font-size="18">正在加载原图…</text></svg>')
const failedImage = 'data:image/svg+xml,' + encodeURIComponent('<svg xmlns="http://www.w3.org/2000/svg" width="280" height="100"><text x="140" y="55" fill="white" text-anchor="middle" font-size="18">原图暂时无法显示</text></svg>')
export function useImageViewer(images: ComputedRef<StudioImage[]>, failure: (reason: unknown) => void) {
  const visible = ref(false), current = ref(0), viewerKey = ref(0), urls = ref<Record<number, string>>({}), error = ref('')
  const leases = new Map<number, ImageLease>(), pending = new Map<number, AbortController>()
  let generation = 0
  const urlList = computed(() => images.value.map((_asset, index) => urls.value[index] || (error.value && current.value === index ? failedImage : loadingImage)))
  function close() {
    visible.value = false; generation++; error.value = ''; urls.value = {}
    pending.forEach(controller => controller.abort()); pending.clear()
    leases.forEach(lease => lease.release()); leases.clear()
  }
  async function load(index: number, report: boolean) {
    const asset = images.value[index]; if (!asset || leases.has(index) || pending.has(index)) return
    const epoch = generation, controller = new AbortController(); pending.set(index, controller)
    try {
      const lease = await overseasImageCache.acquire(imageUrl(asset), { signal: controller.signal })
      if (epoch !== generation || controller.signal.aborted) { lease.release(); return }
      leases.set(index, lease); urls.value = { ...urls.value, [index]: lease.url }
    } catch (reason) {
      if (epoch === generation && !controller.signal.aborted && report && current.value === index) {
        error.value = reason instanceof Error ? reason.message : '图片无法读取，请重试'; failure(reason)
      }
    } finally { if (pending.get(index) === controller) pending.delete(index) }
  }
  async function select(index: number) {
    current.value = index; error.value = ''
    for (const [other, controller] of pending) if (other !== index) { controller.abort(); pending.delete(other) }
    for (const [other, lease] of leases) if (other !== index) { lease.release(); leases.delete(other); delete urls.value[other] }
    await load(index, true)
    // Background prefetch keeps compressed Blobs only; only the current image gets a decode URL.
  }
  function open(index: number) { close(); current.value = index; visible.value = true; void select(index) }
  function imageError() {
    const index = current.value, lease = leases.get(index)
    if (!lease) return
    lease.release(); leases.delete(index); delete urls.value[index]
    overseasImageCache.invalidate(imageUrl(images.value[index]))
    error.value = '图片无法显示，请重新加载或下载原文件'
    // Element Plus keeps its native decode-error flag until navigation/remount.
    viewerKey.value++
  }
  const unsubscribe = overseasImageCache.subscribe(close)
  watch(() => images.value.map(imageUrl).join('\n'), close)
  onUnmounted(() => { close(); unsubscribe() })
  return { visible, current, viewerKey, urlList, error, open, close, select, imageError, retry: () => select(current.value) }
}
