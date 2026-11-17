import { mergeConfig } from 'vite'
import base from '../vite.config'
export default () => mergeConfig(base({ mode: 'demo', isolatedPreview: true }), {
  define: { 'import.meta.env.VITE_ISOLATED_PREVIEW': JSON.stringify('true') },
  server: { port: 3038, strictPort: true, open: false, proxy: undefined },
  build: { outDir: 'dist-preview/task-center', rollupOptions: { input: 'preview-task-center/index.html' } },
})
