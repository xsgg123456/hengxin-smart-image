// Isolated UI/API fixtures. Native file bytes come from a disposable slow HTTP server.
import assert from 'node:assert/strict'
import { createServer, request as httpRequest } from 'node:http'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const upstream = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3015'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(upstream).hostname))
const browser = await chromium.launch({ headless: true }), context = await browser.newContext({ viewport: { width: 1366, height: 900 } })
const page = await context.newPage(), errors = [], requests = [], timers = new Set()
page.on('pageerror', e => errors.push(e.message)); page.setDefaultTimeout(15000)
const longName = 'ZZZ-13圆形杂志桌灯-竞品listing-杨陈玉-20260804-'.repeat(3) + '.xlsx'
const assets = [
  { id: 'task:m', name: longName, contentType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', sizeBytes: 86062183, url: '/api/overseas/v1/materials/m/content', source: 'task' },
  { id: 'upload:u', name: '上传图片.png', contentType: 'image/png', sizeBytes: 1024, url: '/api/overseas/v1/tasks/t/studio/files/u/content', source: 'upload' }
]
let mode = 'normal', finished = false
const payload = Buffer.alloc(2 * 1024 * 1024, 42)
const streamServer = createServer((req, res) => {
  if (!assets.some(a => a.url === req.url)) {
    const proxy = httpRequest(upstream + req.url, { method: req.method, headers: req.headers }, response => { res.writeHead(response.statusCode, response.headers); response.pipe(res) })
    proxy.on('error', () => { res.writeHead(502); res.end() }); req.pipe(proxy); return
  }
  requests.push(`${req.method} ${req.url}`)
  finished = false
  res.writeHead(200, { 'Content-Type': 'application/octet-stream', 'Content-Length': payload.length, 'Content-Disposition': `attachment; filename*=UTF-8''${encodeURIComponent(req.url.includes('/files/') ? assets[1].name : longName)}` })
  res.write(payload.subarray(0, 65536))
  const timer = setTimeout(() => { finished = true; res.end(payload.subarray(65536)); timers.delete(timer) }, 2500)
  timers.add(timer); res.on('close', () => { clearTimeout(timer); timers.delete(timer) })
})
await new Promise(resolve => streamServer.listen(0, '127.0.0.1', resolve))
const streamOrigin = `http://127.0.0.1:${streamServer.address().port}`
const base = streamOrigin
const caps = ['task.read', 'task.design']
const task = { id: 't', name: '附件仅下载验收', productName: '灯具', brand: 'HX', platform: 'Amazon', market: '美国', remarks: '', skus: [{ code: 'A' }], workflow: 'studio', status: 'studio', version: 1, createdAt: '2026-10-14', updatedAt: '2026-10-14', createdBy: { id: 'u', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: caps, events: [] }
const picture = { id: 'p', name: '生成图片.png', url: '/api/overseas/v1/tasks/t/studio/pictures/p/content', width: 1, height: 1, turnId: 'r', sku: null, archived: false }
const state = { taskId: 't', completed: false, conversationId: 'c', turns: [{ id: 'r', conversationId: 'c', text: '已发送附件', skillName: null, status: 'succeeded', reply: '已生成', error: null, jobId: 'j', jobVersion: 1, attachments: assets, pictures: [picture], referencePictures: [], createdAt: '2026-10-14' }], materials: assets, skills: [], activeTurnId: null }
try {
  await context.route(`${base}/api/**`, async route => {
    const req = route.request(), path = new URL(req.url()).pathname
    requests.push(`${req.method()} ${path}`)
    if (assets.some(a => a.url === path)) {
      if (req.method() === 'HEAD') {
        if (mode === 'slow-head') await new Promise(resolve => setTimeout(resolve, 1200))
        await route.fulfill({ status: mode === 'missing' ? 404 : mode === 'storage' ? 503 : 200, body: '' }).catch(() => {})
      } else await route.continue({ url: streamOrigin + path })
      return
    }
    if (path === picture.url) { await route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jQmQAAAAASUVORK5CYII=', 'base64') }); return }
    let body = {}
    if (path.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (path === '/api/identity/v1/me') body = { name: '设计', sessionId: 'identity-test' }
    else if (path.endsWith('/tickets')) body = { ticket: 'test' }
    else if (path === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
    else if (path.includes('/auth/')) { body = { id: 'd', name: '设计', identitySessionId: 'identity-test', status: 'active', roles: ['designer'], capabilities: caps }; if (path.endsWith('/access')) body = { state: 'allowed', member: body } }
    else if (path.endsWith('/studio/transcript')) body = { items: [], cursor: 0, hasMore: false }
    else if (path.endsWith('/studio')) body = state
    else if (path.endsWith('/tasks/t')) body = task
    else if (path.endsWith('/materials')) body = []
    else if (path.endsWith('/jobs')) body = { items: [] }
    else if (path.endsWith('/execution-events')) body = { items: [], cursor: 0 }
    else if (path.endsWith('/plans') || path.endsWith('/pictures')) body = { items: [], taskVersion: 1 }
    else throw Error(`Unexpected ${req.method()} ${path}`)
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.goto(`${base}/#/overseas/tasks/t`)
  const row = page.locator('.studio-source-file').filter({ has: page.getByRole('checkbox', { name: longName, exact: true }) })
  await row.waitFor()
  assert.equal(await page.locator('.studio-materials img').count(), 0, 'uploaded images must not preview')
  assert.equal(requests.some(r => r.startsWith('GET ') && assets.some(a => r.endsWith(a.url))), false, 'no implicit attachment fetch')
  assert.ok(await page.locator('.studio-picture img').count() || await page.locator('.studio-messages img').count(), 'generated pictures remain visible')
  const downloadEvent = page.waitForEvent('download'); await row.getByRole('button', { name: '下载原文件', exact: true }).click(); const download = await downloadEvent
  assert.equal(finished, false, 'browser must start download before whole file reaches client')
  assert.equal(download.suggestedFilename(), longName)
  await row.getByRole('status').filter({ hasText: '已发起下载' }).waitFor()
  const parts = []; for await (const part of await download.createReadStream()) parts.push(part)
  assert.deepEqual(Buffer.concat(parts), payload)
  // Historical turn attachments use the same native download rather than a preview popup.
  const turnFile = page.locator('.studio-messages .studio-attachment').filter({ hasText: assets[1].name })
  const imageDownload = page.waitForEvent('download'); await turnFile.getByRole('button', { name: '下载原文件' }).click()
  const imageFile = await imageDownload; assert.equal(imageFile.suggestedFilename(), assets[1].name); assert.equal(await imageFile.failure(), null)
  assert.equal(await page.getByRole('dialog').count(), 0)
  await mkdir('../../output/playwright/attachment-download', { recursive: true })
  await page.screenshot({ path: '../../output/playwright/attachment-download/studio-desktop.png', fullPage: true })
  const originalGets = () => requests.filter(r => r.startsWith('GET ') && r.endsWith(assets[0].url)).length
  const count = originalGets(); mode = 'storage'; await row.getByRole('button', { name: '下载原文件' }).click(); await row.getByRole('alert').waitFor(); assert.equal(originalGets(), count)
  mode = 'slow-head'; await row.getByRole('button', { name: '下载原文件' }).click(); await row.getByRole('button', { name: '取消检查' }).click(); await page.waitForTimeout(1400); assert.equal(originalGets(), count)
  await page.setViewportSize({ width: 390, height: 844 })
  mode = 'normal'; await page.reload(); await row.waitFor()
  await row.scrollIntoViewIfNeeded()
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
  assert.ok(await row.evaluate(el => el.scrollWidth <= el.clientWidth + 1), 'long filename must fit card')
  const name = row.getByRole('checkbox', { name: longName, exact: true })
  assert.ok(await name.evaluate(el => { const label = el.closest('label')?.querySelector('.el-checkbox__label'); return label && label.scrollWidth <= label.clientWidth + 1 && label.scrollHeight <= label.clientHeight + 1 }), 'full filename must wrap without clipping')
  await page.screenshot({ path: '../../output/playwright/attachment-download/studio-mobile.png', fullPage: true })
  assert.deepEqual(errors, []); console.log('PASS native attachment download starts before body completes; exact bytes/name; both sources/history; no uploaded image preview; generated images retained; HEAD error/cancel; long name wraps')
} catch (error) { console.error(await page.locator('body').innerText()); console.error({ errors, requests }); throw error }
finally { await browser.close(); for (const timer of timers) clearTimeout(timer); streamServer.closeAllConnections(); await new Promise(resolve => streamServer.close(resolve)) }
