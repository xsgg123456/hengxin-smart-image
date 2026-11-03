import { onUnmounted, watch } from 'vue'
import { archiveImageFailure, archivePictureUrl, type ArchivePicture } from '@/api/overseas/archives'
import { overseasImageCache } from '@/api/overseas/image-cache'

export function useArchivePrefetch(id: () => string, pictures: () => ArchivePicture[], enabled: () => boolean = () => true) {
  const owner = overseasImageCache.createPrefetch(reason => archiveImageFailure(id(), reason))
  watch(() => ({ id: id(), pictures: enabled() ? pictures() : [] }), value => {
    owner.update(value.id, value.pictures.map(picture => ({ url: archivePictureUrl(value.id, picture.id), size: picture.sizeBytes })))
  }, { immediate: true, deep: true })
  onUnmounted(owner.dispose)
}
