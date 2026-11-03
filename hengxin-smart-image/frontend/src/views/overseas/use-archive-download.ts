import { onUnmounted, ref } from 'vue'
import { archiveError, archiveImageFailure, archivePictureUrl, type ArchivePicture } from '@/api/overseas/archives'
import { overseasImageCache } from '@/api/overseas/image-cache'
import { saveBlob } from '@/api/overseas/pictures'

export function useArchiveDownload(id: () => string, picture: () => ArchivePicture | undefined, failure: (reason: unknown) => void) {
  const downloading = ref(false), downloadError = ref(''), controller = new AbortController()
  async function download() {
    const asset = picture(), archiveId = id()
    if (!asset || downloading.value) return
    downloading.value = true; downloadError.value = ''
    try {
      const lease = await overseasImageCache.acquire(archivePictureUrl(archiveId, asset.id), { signal: controller.signal })
      try {
        if (controller.signal.aborted) return
        if (lease.blob.type !== asset.contentType || lease.blob.size !== asset.sizeBytes) {
          overseasImageCache.invalidate(archivePictureUrl(archiveId, asset.id))
          throw Error('图片文件与归档记录不一致，请刷新后重试')
        }
        saveBlob(lease.blob, asset.name)
      } finally { lease.release() }
    } catch (reason) {
      if (!controller.signal.aborted) { downloadError.value = archiveError(reason); archiveImageFailure(archiveId, reason); failure(reason) }
    } finally { downloading.value = false }
  }
  onUnmounted(() => controller.abort())
  return { downloading, downloadError, download }
}
