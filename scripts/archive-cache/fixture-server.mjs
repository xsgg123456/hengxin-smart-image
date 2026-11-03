import { createServer } from 'node:http'
import { createRequire } from 'node:module'
import { resolve, dirname } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import { imageBytes } from '../image-cache/fixture-server.mjs'
export { imageBytes }
const directory = dirname(fileURLToPath(import.meta.url)), frontend = resolve(directory, '../../hengxin-smart-image/frontend')
const require = createRequire(resolve(frontend, 'package.json'))
const { createServer: createViteServer } = await import(pathToFileURL(require.resolve('vite')).href)
const { default: vue } = await import(pathToFileURL(require.resolve('@vitejs/plugin-vue')).href)
export async function startFixture() {
  const state = { requests: [], status: new Map(), thumbnailFailures: new Map(), revision: new Map(), delays: new Map(), thumbnailDelay: 0, active: 0, maxActive: 0, unexpected: [], metadataStatus: 200 }
  const bodies = new Map()
  const bytes = (id, small, revision) => { const key = `${id}:${small}:${revision}`; if (!bodies.has(key)) bodies.set(key, imageBytes(id, small, revision)); return bodies.get(key) }
  const pictures = ['a', 'b', 'c', 'd', 'e', 'f'].map((id, index) => ({ id, name: `${id}.png`, sku: 'SKU-A', width: 1600, height: 1000, sizeBytes: bytes(id, false, 1).length, contentType: 'image/png', url: `/api/overseas/v1/archives/fixture/pictures/${id}/content`, sourceConversationId: index < 3 ? 'one' : 'two', sourceConversationName: index < 3 ? '会话一' : '会话二' }))
  const archive = { id:'fixture',taskId:null,sourceDeleted:true,taskName:'独立归档任务',language:'en',productName:'真实组件测试成品',brand:'测试品牌',platform:'Amazon',skus:[{code:'SKU-A'}],pictureCount:pictures.length,createdAt:'2026-11-03T00:00:00Z',cover:pictures[0],pictures,deleteToken:'fixture-token',latestArchive:null,archiveHistory:[] }
  const vite = await createViteServer({ configFile: false, root: directory, plugins: [vue()],
    resolve: { alias: { '@': resolve(frontend, 'src'), vue: require.resolve('vue/dist/vue.esm-bundler.js'), 'vue-router': resolve(frontend, 'node_modules/vue-router'), 'element-plus': resolve(frontend, 'node_modules/element-plus') }, dedupe: ['vue'] },
    cacheDir: resolve(directory, '../../output/archive-cache/vite-cache'),
    server: { middlewareMode: true, hmr: false, fs: { allow: [resolve(directory, '../..')] } }, appType: 'spa' })
  const server = createServer(async (req, res) => {
    const url = new URL(req.url, 'http://localhost'), root = '/api/overseas/v1/archives'
    if (!url.pathname.startsWith('/api/')) return vite.middlewares(req, res)
    const json = (value, status = 200) => { res.writeHead(status, { 'Content-Type':'application/json', 'Cache-Control':'no-store' }); res.end(JSON.stringify(value)) }
    if (url.pathname === root) return json({items:url.searchParams.get('search') ? [] : [archive],total:url.searchParams.get('search') ? 0 : 1,page:1,pageSize:20})
    if (url.pathname === root + '/fixture') {
      if (req.method === 'DELETE') { state.metadataStatus = 404; for (const p of pictures) state.status.set(p.id, 404); return json({archiveId:'fixture',status:'deleted',error:null}) }
      return json(state.metadataStatus === 200 ? archive : {message:'成品不可访问'}, state.metadataStatus)
    }
    const match = url.pathname.match(/^\/api\/overseas\/v1\/archives\/fixture\/pictures\/([a-z]+)\/content$/)
    if (!match) { state.unexpected.push(req.url); return json({}, 501) }
    const id = match[1], small = url.searchParams.get('thumbnail') === 'true', method = req.method, started = performance.now()
    const item = { id, small, method, url:req.url, status:0, bytes:0, aborted:false, durationMs:0, ifNoneMatch:req.headers['if-none-match'] || null }; state.requests.push(item)
    let counted = method === 'GET' && !small
    if (counted) { state.active++; state.maxActive = Math.max(state.active, state.maxActive) }
    const complete = () => { if (counted) { state.active--; counted = false } item.durationMs = Math.round(performance.now() - started) }
    res.on('close', () => { if (!res.writableFinished) item.aborted = true; complete() })
    try {
      const delay = small ? (id === 'a' ? state.thumbnailDelay : 0) : state.delays.get(id) || 0
      if (delay) await new Promise(done => { const timer = setTimeout(done, delay); res.once('close', () => { clearTimeout(timer); done() }) })
      if (res.destroyed) return
      const remaining = state.thumbnailFailures.get(id) || 0
      if (small && remaining) { state.thumbnailFailures.set(id, remaining - 1); item.status=503; return json({},503) }
      const status = state.status.get(id) || 200
      if (status !== 200) { item.status=status; return json({}, status) }
      const revision = state.revision.get(id) || 1, tag = `"${id}-${small ? 'small' : 'original'}-${revision}"`
      const headers = { 'Content-Type':'image/png', 'Cache-Control':'private, no-cache', ETag:tag, Vary:'Cookie, Authorization' }
      if (req.headers['if-none-match'] === tag) { item.status=304; res.writeHead(304, headers); return res.end() }
      const body = bytes(id, small, revision); item.status=200; item.bytes=method === 'HEAD' ? 0 : body.length
      res.writeHead(200, {...headers,'Content-Length':body.length}); res.end(method === 'HEAD' ? undefined : body)
    } finally { complete() }
  })
  await new Promise((done, fail) => { server.once('error',fail); server.listen(0,'127.0.0.1',done) })
  return { state, origin:`http://127.0.0.1:${server.address().port}`, async close() { server.closeAllConnections(); await new Promise(done => server.close(done)); await vite.close() } }
}
