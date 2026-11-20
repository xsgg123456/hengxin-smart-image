import { studioPreviewImages } from './studio-preview-images'
import { mergeConfig } from 'vite'
import base from '../vite.config'
export default mergeConfig(base({ mode: 'demo', isolatedPreview: true }), {
  plugins: [studioPreviewImages()],
  server: { port: 3086, strictPort: true },
  build: { outDir: 'dist-preview/overseas-design-center', rollupOptions: { input: 'preview-overseas-design-center/index.html' } },
})



