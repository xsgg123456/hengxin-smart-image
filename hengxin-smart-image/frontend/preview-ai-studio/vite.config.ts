import { mergeConfig } from 'vite'
import base from '../vite.config'
import path from 'node:path'
export default () => mergeConfig(base({ mode: 'demo', isolatedPreview: true }), {
  define: { 'import.meta.env.VITE_ISOLATED_PREVIEW': JSON.stringify('true') },
  server: { port: 3016, proxy: undefined, open: '/preview-ai-studio/index.html' },
  build: { outDir: '../../output/ai-studio-build', rollupOptions: { input: path.resolve('preview-ai-studio/index.html') } },
})
