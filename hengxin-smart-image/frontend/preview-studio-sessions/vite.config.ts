import { mergeConfig } from 'vite'
import base from '../vite.config'
export default mergeConfig(base({ mode: 'demo', isolatedPreview: true }), {
  server: { port: 3031, strictPort: true },
  build: { outDir: 'dist-preview/studio-sessions', rollupOptions: { input: 'preview-studio-sessions/index.html' } },
})

