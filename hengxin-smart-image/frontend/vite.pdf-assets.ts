import { readFileSync, readdirSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { createRequire } from 'node:module'
import type { Plugin } from 'vite'

/** Ship fonts/CMaps/decoders with the app; PDF viewing never relies on a CDN. */
export function pdfAssets(): Plugin {
  const require = createRequire(import.meta.url)
  const root = dirname(require.resolve('pdfjs-dist/package.json'))
  const version = JSON.parse(readFileSync(join(root, 'package.json'), 'utf8')).version as string
  const prefix = `pdfjs-${version}/`
  const files = new Map<string, Buffer>()
  for (const folder of ['cmaps', 'standard_fonts', 'wasm']) {
    for (const name of readdirSync(join(root, folder))) {
      if (/\.(bcmap|pfb|ttf|wasm|js)$/.test(name)) files.set(prefix + folder + '/' + name, readFileSync(join(root, folder, name)))
    }
  }
  return {
    name: 'local-pdf-assets',
    config: () => ({
      define: { __PDF_ASSET_BASE__: JSON.stringify('/' + prefix) },
      // Production nginx maps .js to JavaScript; its default MIME table lacks .mjs.
      build: { rollupOptions: { output: { assetFileNames: asset => asset.names.includes('pdf.worker.min.mjs') ? 'assets/pdf.worker.min-[hash].js' : 'assets/[name]-[hash][extname]' } } }
    }),
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        const path = (req.url || '').split('?')[0].replace(/^\//, ''), bytes = files.get(path)
        if (!bytes) return next()
        res.setHeader('Content-Type', path.endsWith('.wasm') ? 'application/wasm' : path.endsWith('.js') ? 'text/javascript' : 'application/octet-stream')
        res.end(bytes)
      })
    },
    generateBundle() { for (const [fileName, source] of files) this.emitFile({ type: 'asset', fileName, source }) }
  }
}
