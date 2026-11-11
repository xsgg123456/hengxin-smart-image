import { mergeConfig } from 'vite'
import { fileURLToPath } from 'node:url'
import base from '../vite.config'
export default () => {
  const config = base({ mode: 'demo', isolatedPreview: true })
  const replacement = fileURLToPath(new URL('./baseline-api.ts', import.meta.url))
  config.resolve = { ...config.resolve, alias: [
    { find: '@/api/api-management-usage', replacement },
    { find: '@/api/execution-management', replacement },
    ...Object.entries(config.resolve?.alias || {}).map(([find, replacement]) => ({ find, replacement: String(replacement) })),
  ] }
  return mergeConfig(config, {
    define: { 'import.meta.env.VITE_ISOLATED_PREVIEW': JSON.stringify('true') },
    server: { port: 3041, strictPort: true, open: false, proxy: undefined },
    build: { outDir: 'dist-preview/domestic-activity', rollupOptions: { input: 'preview-domestic-activity/index.html' } },
  })
}
