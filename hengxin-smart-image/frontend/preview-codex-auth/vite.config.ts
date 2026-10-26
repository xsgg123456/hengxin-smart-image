import { mergeConfig, type Plugin } from 'vite'
import base from '../vite.config'
const denyApi: Plugin = {
  name: 'preview-block-business-api',
  configureServer(server) {
    server.middlewares.use((req, res, next) => {
      if (req.url?.startsWith('/api/')) { res.statusCode = 403; res.end('Preview does not connect to business APIs'); return }
      next()
    })
  }
}
export default mergeConfig(base({ mode: 'demo', isolatedPreview: true }), {
  plugins: [denyApi],
  server: { host: '127.0.0.1', port: 3033, strictPort: true },
  build: { outDir: 'dist-preview/codex-auth', rollupOptions: { input: 'preview-codex-auth/index.html' } }
})
