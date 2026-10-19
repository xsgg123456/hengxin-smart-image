import { mergeConfig } from 'vite'
import base from '../vite.config'
import path from 'node:path'
export default () => mergeConfig(base({ mode: 'demo', isolatedPreview: true }), {
  define: { 'import.meta.env.VITE_ISOLATED_PREVIEW': JSON.stringify('true') },
  server: { host: '127.0.0.1', port: 3021, strictPort: true, proxy: undefined, open: false },
  build: { outDir: '../../output/studio-process-build', rollupOptions: { input: path.resolve('preview-studio-process/index.html') } },
})
