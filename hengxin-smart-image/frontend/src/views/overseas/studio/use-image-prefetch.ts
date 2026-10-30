import { onUnmounted, watch } from 'vue'
import type { Studio } from '@/api/overseas/studio'
import { overseasImageCache } from '@/api/overseas/image-cache'
import { imageUrl, isImage, type StudioImage } from './studio-images'

export function useImagePrefetch(scope: () => string, data: () => Studio | undefined, drafts: () => StudioImage[]) {
  watch(() => {
    const value = data()
    const images = value ? [...value.materials, ...value.turns.flatMap(turn => [...turn.pictures, ...turn.attachments, ...turn.referencePictures]), ...drafts()] : []
    return { scope: scope(), sources: images.filter(isImage).map(asset => ({ url: imageUrl(asset), size: 'sizeBytes' in asset ? asset.sizeBytes : undefined })) }
  }, value => overseasImageCache.setPrefetch(value.scope, value.sources), { immediate: true, deep: true })
  onUnmounted(() => overseasImageCache.setPrefetch('', []))
}
