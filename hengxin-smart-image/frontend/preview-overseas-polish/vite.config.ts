import { mergeConfig } from 'vite'
import base from '../vite.config'
export default mergeConfig(base({ mode: 'demo', isolatedPreview: true }), {
  server: { port: 3032, strictPort: true },
  build: { outDir: 'dist-preview/overseas-polish', rollupOptions: { input: 'preview-overseas-polish/index.html' } },
})

