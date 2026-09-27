// Real browser/cache against an isolated local HTTP fixture and actual Vite UI.
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { readFile, mkdir, writeFile } from 'node:fs/promises'
import { resolve, isAbsolute } from 'node:path'
import { pathToFileURL } from 'node:url'
import { intercept } from './browser-fixtures.mjs'
const moduleName = process.env.PLAYWRIGHT_MODULE || 'playwright'
const { chromium } = await import(isAbsolute(moduleName) ? pathToFileURL(moduleName).href : moduleName)
const upstream = new URL(process.env.PERFORMANCE_TEST_ORIGIN || 'http://127.0.0.1:3027')
assert(['127.0.0.1', 'localhost'].includes(upstream.hostname))
const output = resolve('output/playwright/performance-direct')
await mkdir(output, { recursive: true })
const original = await readFile(resolve(output, 'original.png'))
const thumbnail = await readFile(resolve(output, 'display.webp'))
const state = { user: { id: 'fixture-user', name: '性能验证', role: 'operator', status: 'active' },
  authCalls: 0, imageCalls: 0, apiCalls: [], unexpected: [], hits: 0, bytes: 0, useOriginal: true }
state.imageResponse = (route, url) => {
  const small = !state.useOriginal && url.searchParams.get('variant') === '256'
  const tag = small ? '"small-v1"' : '"original-v1"'
  const headers = { 'Cache-Control': 'private, no-cache', 'ETag': tag, 'Vary': 'Cookie, Authorization' }
  if (route.request().headers()['if-none-match'] === tag) {
    state.hits++
    return route.fulfill({ status: 304, headers, body: '' })
  }
  const body = small ? thumbnail : original
  state.bytes += body.length
  return route.fulfill({ status: 200, contentType: small ? 'image/webp' : 'image/png', headers, body })
}
let handler
const server = createServer(async (req, res) => {
  try {
    await handler({ request: () => ({ url: () => origin + req.url, headers: () => req.headers }),
      abort: () => { res.writeHead(403); res.end() },
      fulfill: ({ status = 200, contentType, headers = {}, body = '' }) => {
        res.writeHead(status, { ...(contentType ? { 'Content-Type': contentType } : {}), ...headers }); res.end(body)
      },
      continue: async () => {
        const response = await fetch(new URL(req.url, upstream))
        res.writeHead(response.status, { 'Content-Type': response.headers.get('content-type') || 'text/plain' })
        res.end(Buffer.from(await response.arrayBuffer()))
      }
    })
  } catch { res.writeHead(500); res.end() }
})
await new Promise(done => server.listen(0, '127.0.0.1', done))
const origin = `http://127.0.0.1:${server.address().port}`
await intercept({ route: async (_, fn) => { handler = fn } }, origin, state)
const browser = await chromium.launch({ headless: true })
const measurements = []
try {
  for (const reduced of [false, true]) {
    state.useOriginal = !reduced; state.bytes = state.imageCalls = state.hits = state.authCalls = 0
    const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
    const page = await context.newPage()
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    const start = Date.now()
    await page.goto(origin + '/#/templates/index', { waitUntil: 'networkidle' })
    await page.getByRole('heading', { name: '模板库', exact: true }).waitFor()
    await page.waitForFunction(() => [...document.querySelectorAll('.hx-picture img')].some(img => img.complete && img.naturalWidth))
    const first = { ms: Date.now() - start, images: state.imageCalls, bytes: state.bytes, auth: state.authCalls }
    assert(first.images > 0 && first.images < 44, 'offscreen pictures must not all load at first screen')
    assert.equal(first.auth, 1, 'bootstrap and initial routing must share one user read')
    await page.screenshot({ path: resolve(output, reduced ? 'display-first.png' : 'original-first.png') })
    const count = state.imageCalls, before = state.bytes
    const reloadStart = Date.now()
    await page.reload({ waitUntil: 'networkidle' })
    await page.getByRole('heading', { name: '模板库', exact: true }).waitFor()
    assert(state.hits > 0, 'real browser must revalidate existing private image bytes')
    assert.equal(state.bytes - before, 0, 'refresh must not retransmit unchanged visible images')
    const refresh = { ms: Date.now() - reloadStart, requests: state.imageCalls - count, bytes: state.bytes - before, hits: state.hits }
    const navigationStart = Date.now()
    await page.evaluate(() => { location.hash = '#/tasks/index' })
    await page.waitForTimeout(400)
    await page.evaluate(() => { location.hash = '#/templates/index' })
    await page.getByRole('heading', { name: '模板库', exact: true }).waitFor()
    await page.waitForTimeout(500)
    assert.equal(state.bytes - before, 0)
    measurements.push({ representation: reduced ? '256 WebP' : 'original PNG', first, refresh,
      returnNavigation: { ms: Date.now() - navigationStart, bytes: state.bytes - before }, errors })
    assert.deepEqual(errors, [])
    await context.close()
  }
  assert(measurements[1].first.bytes < measurements[0].first.bytes / 10)
  await writeFile(resolve(output, 'evidence.json'), JSON.stringify({ passed: true,
    scope: 'Actual UI + Chromium + localhost fixture images; not production latency; same image and viewport', measurements }, null, 2))
  console.log(JSON.stringify(measurements))
} finally { await browser.close(); await new Promise(done => server.close(done)) }
