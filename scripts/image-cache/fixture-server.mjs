import { createServer } from 'node:http'
import { createRequire } from 'node:module'
import { resolve, dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { deflateSync } from 'node:zlib'
const directory = dirname(fileURLToPath(import.meta.url))
const frontend = resolve(directory, '../../hengxin-smart-image/frontend')
const require = createRequire(resolve(frontend, 'package.json'))
const { createServer: createViteServer } = await import(pathToFileURL(require.resolve('vite')).href)
const { default: vue } = await import(pathToFileURL(require.resolve('@vitejs/plugin-vue')).href)

function crc32(data) {
  let crc = 0xffffffff
  for (const byte of data) { crc ^= byte; for (let i = 0; i < 8; i++) crc = (crc >>> 1) ^ (0xedb88320 & -(crc & 1)) }
  return (crc ^ 0xffffffff) >>> 0
}
function chunk(type, data) {
  const name = Buffer.from(type), length = Buffer.alloc(4), checksum = Buffer.alloc(4)
  length.writeUInt32BE(data.length); checksum.writeUInt32BE(crc32(Buffer.concat([name, data])))
  return Buffer.concat([length, name, data, checksum])
}
export function imageBytes(id, small = false, revision = 1) {
  const width = small ? 240 : 1600, height = small ? 150 : 1000
  const pixels = Buffer.alloc((width * 3 + 1) * height), seed = id.charCodeAt(0) + revision * 17
  for (let y = 0; y < height; y++) for (let x = 0; x < width; x++) {
    const offset = y * (width * 3 + 1) + x * 3 + 1
    pixels[offset] = (x + seed * 3) % 256; pixels[offset + 1] = (y + seed) % 256; pixels[offset + 2] = (x + y + seed * 5) % 256
  }
  const header = Buffer.alloc(13); header.writeUInt32BE(width); header.writeUInt32BE(height, 4); header[8] = 8; header[9] = 2
  return Buffer.concat([Buffer.from([137,80,78,71,13,10,26,10]), chunk('IHDR', header), chunk('IDAT', deflateSync(pixels)), chunk('IEND', Buffer.alloc(0))])
}
export async function startFixture() {
  const state = { requests: [], status: new Map(), thumbnailFailures: new Map(), revision: new Map(), delays: new Map(), active: 0, maxActive: 0, unexpected: [] }
  const vite = await createViteServer({ configFile: false, root: directory, plugins: [vue()],
    resolve: { alias: { '@': resolve(frontend, 'src'), vue: require.resolve('vue/dist/vue.esm-bundler.js'), 'element-plus': resolve(frontend, 'node_modules/element-plus') }, dedupe: ['vue'] },
    cacheDir: resolve(directory, '../../output/image-cache/vite-cache'),
    server: { middlewareMode: true, hmr: false, fs: { allow: [resolve(directory, '../..')] } }, appType: 'spa' })
  const server = createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost')
    if (!url.pathname.startsWith('/api/')) return vite.middlewares(req, res)
    const match = url.pathname.match(/^\/api\/overseas\/v1\/(?:tasks\/fixture\/studio\/(?:pictures|files)|materials)\/([\w-]+)\/content$/)
    if (!match) { state.unexpected.push(req.url); res.writeHead(501); return res.end() }
    const id = match[1], small = url.searchParams.get('thumbnail') === 'true', method = req.method
    const item = { id, small, method, url: req.url, status: 0, bytes: 0, ifNoneMatch: req.headers['if-none-match'] || null }
    state.requests.push(item)
    const remaining = state.thumbnailFailures.get(id) || 0
    if (small && remaining > 0) {
      state.thumbnailFailures.set(id, remaining - 1); item.status = 429
      res.writeHead(429, { 'Cache-Control': 'no-store', 'Retry-After': '1' }); return res.end()
    }
    if (method === 'GET' && !small) { state.active++; state.maxActive = Math.max(state.maxActive, state.active) }
    try {
      const delay = state.delays.get(id) || 0
      if (delay && !small) await new Promise(done => setTimeout(done, delay))
      const status = state.status.get(id) || 200
      if (status !== 200) { item.status = status; res.writeHead(status, { 'Cache-Control': 'no-store' }); return res.end() }
      const revision = state.revision.get(id) || 1, tag = `"${id}-${small ? 'small' : 'original'}-${revision}"`
      const headers = { 'Content-Type': 'image/png', 'Cache-Control': 'private, no-cache', ETag: tag, Vary: 'Cookie, Authorization' }
      if (req.headers['if-none-match'] === tag) { item.status = 304; res.writeHead(304, headers); return res.end() }
      const body = imageBytes(id, small, revision)
      item.status = 200; item.bytes = method === 'HEAD' ? 0 : body.length
      res.writeHead(200, { ...headers, 'Content-Length': body.length, 'Content-Disposition': `attachment; filename="${id}.png"` })
      res.end(method === 'HEAD' ? undefined : body)
    } catch (error) { item.error = String(error); if (!res.headersSent) res.writeHead(500); res.end() }
    finally { if (method === 'GET' && !small) state.active-- }
  })
  await new Promise((done, fail) => { server.once('error', fail); server.listen(0, '127.0.0.1', done) })
  return { state, origin: `http://127.0.0.1:${server.address().port}`, async close() { server.closeAllConnections(); await new Promise(done => server.close(done)); await vite.close() } }
}
