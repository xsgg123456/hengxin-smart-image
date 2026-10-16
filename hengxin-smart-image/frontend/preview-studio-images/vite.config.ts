import { mergeConfig } from 'vite'
import base from '../vite.config'
import path from 'node:path'
export default () => mergeConfig(base({ mode: 'demo', isolatedPreview: true }), {
  define: { 'import.meta.env.VITE_ISOLATED_PREVIEW': JSON.stringify('true') },
  server: { port: 3020, proxy: undefined, open: false },
  build: { outDir: '../../output/studio-images-build', rollupOptions: { input: path.resolve('preview-studio-images/index.html') } },
})
