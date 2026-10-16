import { onUnmounted, ref, watch } from 'vue'
import { IdentityError } from '@/api/identity/request'
import { archiveError, type ArchivePicture, type ArchivesApi } from '@/api/overseas/archives'

/** A single authenticated original. No cache survives a picture/owner change or unmount. */
export function useArchiveImage(api: ArchivesApi, archiveId: () => string, picture: () => ArchivePicture | undefined, failure: (reason: unknown) => void) {
  const blob = ref<Blob>(), url = ref(''), error = ref(''), loading = ref(false)
  let epoch = 0, alive = true, controller: AbortController | undefined
  function release() {
    controller?.abort()
    if (url.value) URL.revokeObjectURL(url.value)
    url.value = ''; blob.value = undefined
  }
  async function load() {
    const current = ++epoch, target = picture(), id = archiveId()
    release(); error.value = ''; loading.value = false
    if (!target) return
    controller = new AbortController(); loading.value = true
    try {
      const value = await api.content(id, target.id, AbortSignal.any([controller.signal, AbortSignal.timeout(60000)]))
      if (!alive || current !== epoch) return
      if (value.type !== target.contentType || value.size !== target.sizeBytes) throw Error('图片文件与归档记录不一致，请刷新后重试')
      blob.value = value; url.value = URL.createObjectURL(value)
    } catch (reason) {
      if (alive && current === epoch) {
        error.value = archiveError(reason)
        if (reason instanceof IdentityError && [401, 403].includes(reason.status)) failure(reason)
      }
    } finally { if (alive && current === epoch) loading.value = false }
  }
  function imageError() { error.value = '图片无法显示，请重试或下载原图查看' }
  watch([archiveId, picture], load, { immediate: true, flush: 'sync' })
  onUnmounted(() => { alive = false; ++epoch; release() })
  return { blob, url, error, loading, load, imageError }
}
