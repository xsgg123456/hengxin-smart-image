import { onUnmounted, ref, watch } from 'vue'
import { archiveError, archiveImageFailure, archivePictureUrl, type ArchivePicture, type ArchivesApi } from '@/api/overseas/archives'
import { overseasImageCache, type ImageLease } from '@/api/overseas/image-cache'

/** Cards read small derivatives; the viewer leases authenticated, revalidated originals. */
export function useArchiveImage(api: ArchivesApi, archiveId: () => string, picture: () => ArchivePicture | undefined, failure: (reason: unknown) => void, thumbnail = true) {
  const blob = ref<Blob>(), url = ref(''), error = ref(''), loading = ref(false), imageKey = ref(0)
  let epoch = 0, alive = true, controller: AbortController | undefined, lease: ImageLease | undefined
  function release() {
    controller?.abort()
    if (lease) { lease.release(); lease = undefined }
    else if (url.value) URL.revokeObjectURL(url.value)
    url.value = ''; blob.value = undefined
  }
  async function load() {
    const current = ++epoch, target = picture(), id = archiveId()
    release(); error.value = ''; loading.value = false; imageKey.value++
    if (!target) return
    controller = new AbortController(); loading.value = true
    const signal = controller.signal
    try {
      let value: Blob
      if (thumbnail) value = await api.content(id, target.id, AbortSignal.any([signal, AbortSignal.timeout(60000)]), true)
      else {
        const acquired = await overseasImageCache.acquire(archivePictureUrl(id, target.id), { signal })
        if (!alive || current !== epoch) { acquired.release(); return }
        lease = acquired; value = acquired.blob
      }
      if (!alive || current !== epoch || signal.aborted) return
      if (!thumbnail && (value.type !== target.contentType || value.size !== target.sizeBytes)) {
        overseasImageCache.invalidate(archivePictureUrl(id, target.id))
        throw Error('图片文件与归档记录不一致，请刷新后重试')
      }
      blob.value = value; url.value = lease?.url || URL.createObjectURL(value)
    } catch (reason) {
      if (alive && current === epoch && !signal.aborted) {
        release(); error.value = archiveError(reason); archiveImageFailure(id, reason); failure(reason)
      }
    } finally { if (alive && current === epoch) loading.value = false }
  }
  function imageError() {
    release()
    if (!thumbnail && picture()) overseasImageCache.invalidate(archivePictureUrl(archiveId(), picture()!.id))
    error.value = '图片无法显示，请重试或下载原图查看'
  }
  const unsubscribe = overseasImageCache.subscribe(() => { ++epoch; release(); loading.value = false })
  watch([archiveId, picture], load, { immediate: true, flush: 'sync' })
  onUnmounted(() => { alive = false; ++epoch; release(); unsubscribe() })
  return { blob, url, error, loading, imageKey, load, imageError }
}
