import { mergeConfig } from 'vite'
import base from '../vite.config'
export default mergeConfig(base({ mode: 'demo', isolatedPreview: true }), {
  define: { 'import.meta.env.VITE_ISOLATED_PREVIEW': JSON.stringify('true') },
  server: { host: '127.0.0.1', port: 3036, strictPort: true, open: false },
  build: { outDir: 'dist-preview/batch-annotation', rollupOptions: { input: 'preview-batch-annotation/index.html' } },
})
