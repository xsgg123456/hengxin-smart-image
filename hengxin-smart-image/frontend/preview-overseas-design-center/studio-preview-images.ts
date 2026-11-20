import { fileURLToPath } from 'node:url'
import type { Plugin } from 'vite'

export function studioPreviewImages(): Plugin {
  return {
    name: 'design-center-local-thumbnails',
    enforce: 'pre',
    resolveId(source, importer) {
      if (source === './studio-images' && importer?.replaceAll('\\', '/').includes('/shared/studio/StudioAssetImage.vue')) {
        return fileURLToPath(new URL('./studio-image-access.ts', import.meta.url))
      }
    },
  }
}
