import { mergeConfig } from 'vite'
import base from '../vite.config'
export default mergeConfig(base({ mode: 'demo', isolatedPreview: true }), {
  server: { port: 3036, strictPort: true },
  build: { outDir: 'dist-preview/skill-platforms', rollupOptions: { input: 'preview-skill-platforms/index.html' } },
})

