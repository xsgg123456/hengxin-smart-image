import { mergeConfig } from 'vite'
import base from '../vite.config'
import path from 'node:path'
export default () => mergeConfig(base({ mode: 'demo', isolatedPreview: true }), {
  define: { 'import.meta.env.VITE_ISOLATED_PREVIEW': JSON.stringify('true') },
  server: { port: 3026, proxy: undefined, open: false },
  build: { outDir: '../../output/records-scope-build', rollupOptions: { input: path.resolve('preview-records-scope/index.html') } },
})
