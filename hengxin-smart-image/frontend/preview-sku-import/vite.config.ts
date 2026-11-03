import { mergeConfig } from 'vite'
import base from '../vite.config'
export default mergeConfig(base({ mode: 'demo', isolatedPreview: true }), {
  server: { port: 3038, strictPort: true },
  build: { outDir: 'dist-preview/sku-import', rollupOptions: { input: 'preview-sku-import/index.html' } },
})

