// Isolated real UI: never reads production sessions or calls a model.
import assert from 'node:assert/strict'
import { createServer, request as httpRequest } from 'node:http'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const upstream = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3034'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(upstream).hostname))
const streamServer = createServer((req, res) => {
  if (/\/studio\/(outputs|pictures)\//.test(req.url)) {
    const image = req.url.includes('/pictures/')
    const body = Buffer.from(image ? 'broken-preview' : 'test')
    res.writeHead(200, { 'Content-Type': image ? 'image/png' : 'application/zip', 'Content-Length': body.length, 'Content-Disposition': `attachment; filename=${image ? 'picture.png' : 'output.zip'}` }); res.end(body); return
  }
  const proxy = httpRequest(upstream + req.url, { method: req.method, headers: req.headers }, response => { res.writeHead(response.statusCode, response.headers); response.pipe(res) })
  proxy.on('error', () => { res.writeHead(502); res.end() }); req.pipe(proxy)
})
await new Promise(resolve => streamServer.listen(0, '127.0.0.1', resolve))
const base = `http://127.0.0.1:${streamServer.address().port}`
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } }), page = await context.newPage()
const errors = [], unexpected = [], caps = ['task.read', 'task.design']
page.setDefaultTimeout(20000)
page.on('pageerror', error => errors.push(error.message))
const task = { id: 't', name: '收图状态验收', productName: '灯具', brand: 'HX', platform: 'Amazon', market: '美国', remarks: '', skus: [{ code: 'A' }], workflow: 'studio', status: 'studio', version: 1, createdAt: '2026-10-24', updatedAt: '2026-10-24', createdBy: { id: 'u', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: caps, events: [] }
const row = { id: 'c', name: '主图会话', version: 1, createdAt: '2026-10-24', updatedAt: '2026-10-24', activeTurnId: 'turn', status: 'running', turnCount: 1 }
const picture = { id: 'p', name: '已保存.jpg', url: '/api/overseas/v1/tasks/t/studio/pictures/p/content', width: 1600, height: 1600, turnId: 'turn', sku: null, archived: false }
const turn = { id: 'turn', conversationId: 'c', text: '生成图片', skillName: null, status: 'collecting', reply: '最终图片已经输出', error: null, jobId: 'j', jobVersion: 1, attachments: [], referencePictures: [], pictures: [], createdAt: '2026-10-24', deliveryStatus: { state: 'capturing', expected: null, saved: 0 } }
const output = { id: 'out', name: '方案.zip', contentType: 'application/zip', sizeBytes: 4, url: '/api/overseas/v1/tasks/t/studio/outputs/out/content' }
let recoveries = 0, listEmpty = false
turn.status = row.status = 'succeeded'; row.activeTurnId = null; turn.pictures = [picture]; turn.outputs = [output]; turn.deliveryStatus = { state: 'partial', expected: 3, saved: 2 }
const state = () => ({ taskId: 't', taskVersion: 1, archiveId: null, completed: false, reopened: false, conversationId: 'c', conversations: [row], maxConversations: 10, activeConversationCount: row.activeTurnId ? 1 : 0, turns: [turn], materials: [], skills: [], activeTurnId: row.activeTurnId })
async function checkVisible(locator) {
  await locator.scrollIntoViewIfNeeded()
  assert.ok(await locator.evaluate(el => {
    const r = el.getBoundingClientRect()
    if (!r.width || !r.height || r.left < 0 || r.right > innerWidth || r.top < 0 || r.bottom > innerHeight) return false
    for (let p = el.parentElement; p; p = p.parentElement) {
      const style = getComputedStyle(p), bounds = p.getBoundingClientRect()
      if (/(auto|scroll|hidden|clip)/.test(style.overflowY) && (r.top < bounds.top - 1 || r.bottom > bounds.bottom + 1)) return false
      if (/(auto|scroll|hidden|clip)/.test(style.overflowX) && (r.left < bounds.left - 1 || r.right > bounds.right + 1)) return false
    }
    return true
  }), 'Progress text is clipped')
}
try {
  await context.route('**/*', async route => {
    const url = new URL(route.request().url()), path = url.pathname
    if (['api.iconify.design', 'api.unisvg.com', 'api.simplesvg.com'].includes(url.hostname)) return route.fulfill({ contentType: 'application/json', body: '{}' })
    if (url.origin !== base && !['data:', 'blob:'].includes(url.protocol)) { unexpected.push(url.href); return route.abort() }
    if (!path.startsWith('/api/')) return route.continue()
    let body = {}, status = 200
    if (/\/studio\/(outputs|pictures)\/.*\/content$/.test(path)) return route.continue()
    if (path.endsWith('/recoverable-files')) return route.fulfill({ json: { busy: false, items: listEmpty ? [] : ['a', 'b'].map(id => ({ id, name: id + '.zip', path: id + '.zip', version: 'v1', source: 'work', sizeBytes: id === 'a' ? 0 : 500000000 })) } })
    if (path.endsWith('/recover-files')) {
      const files = route.request().postDataJSON().files
      if (++recoveries === 1) assert.deepEqual(files.map(f => f.id), ['a', 'b']); else assert.deepEqual(files, [{ id: 'b', version: 'v1' }])
      return route.fulfill({ json: { saved: [{ id: 'saved-' + recoveries, kind: 'file' }], errors: recoveries === 1 ? [{ id: 'b', name: 'b.zip', message: '对象存储暂不可用，请重试' }] : [] } })
    }
    if (path.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (path === '/api/identity/v1/me') body = { name: '设计', sessionId: 'identity-test' }
    else if (path.endsWith('/tickets')) body = { ticket: 'test' }
    else if (path === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
    else if (path.includes('/auth/')) { body = { id: 'd', name: '设计', identitySessionId: 'identity-test', status: 'active', roles: ['designer'], capabilities: caps }; if (path.endsWith('/access')) body = { state: 'allowed', member: body } }
    else if (path.endsWith('/studio/transcript')) body = { items: [], cursor: 0, hasMore: false }
    else if (path.endsWith('/studio')) body = state()
    else if (path.endsWith('/tasks/t/materials')) body = []
    else if (path.endsWith('/tasks/t')) body = task
    else { unexpected.push(path); status = 404 }
    return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.goto(`${base}/#/overseas/tasks/t`, { timeout: 60000 })
  await page.getByText('文件收取已结束，已保存 2/3 个。未保存的文件可通过“取回文件”重试。', { exact: true }).waitFor()
  await page.getByRole('textbox', { name: '设计要求', exact: true }).fill('继续设计')
  assert.equal(await page.getByRole('button', { name: '发送', exact: true }).isDisabled(), false)
  assert.equal(await page.locator('.studio-pictures .studio-picture').count(), 1)
  const downloadPromise = page.waitForEvent('download')
  await page.locator('[aria-label="本轮输出文件"]').getByRole('button', { name: '下载原文件', exact: true }).click()
  const download = await downloadPromise; assert.equal(await download.failure(), null)
  const imageDownloadPromise = page.waitForEvent('download')
  await page.locator('.studio-picture').getByRole('button', { name: '下载原文件', exact: true }).click()
  const imageDownload = await imageDownloadPromise; assert.equal(await imageDownload.failure(), null)
  await page.getByRole('button', { name: '取回文件', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '取回文件', exact: true })
  await dialog.locator('label').filter({ hasText: 'a.zip' }).click()
  await dialog.locator('label').filter({ hasText: 'b.zip' }).click()
  await dialog.getByRole('button', { name: '取回所选文件', exact: true }).click()
  await dialog.getByText('b.zip：对象存储暂不可用，请重试', { exact: true }).waitFor()
  assert.equal(await dialog.getByRole('checkbox', { name: '选择 a.zip', exact: true }).isChecked(), false)
  assert.equal(await dialog.getByRole('checkbox', { name: '选择 b.zip', exact: true }).isChecked(), true)
  await mkdir('../../output/playwright/studio-outputs', { recursive: true })
  await checkVisible(dialog.getByRole('button', { name: '重试所选文件', exact: true }))
  await page.screenshot({ path: '../../output/playwright/studio-outputs/desktop-partial.png', fullPage: true })
  await dialog.getByRole('button', { name: '重试所选文件', exact: true }).click()
  await dialog.getByText('已保存 1 个文件，0 个未保存。', { exact: true }).waitFor()
  assert.equal(recoveries, 2)
  await page.setViewportSize({ width: 390, height: 844 })
  await checkVisible(dialog.getByRole('button', { name: '取回所选文件', exact: true }))
  await checkVisible(dialog.locator('label').filter({ hasText: 'b.zip' }))
  await page.screenshot({ path: '../../output/playwright/studio-outputs/mobile-dialog.png', fullPage: true })
  listEmpty = true; await dialog.getByRole('button', { name: '刷新列表', exact: true }).click()
  await dialog.getByText('没有可取回的文件。未生成、已删除或已覆盖且没有副本的文件无法恢复。', { exact: true }).waitFor()
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, [])
  console.log('PASS: mixed outputs, partial terminal/send enabled, output download, failed preview original download, recovery partial/retry/empty, desktop/mobile clipping; no model calls')
} catch (error) {
  await mkdir('../../output/playwright/studio-outputs', { recursive: true })
  await page.screenshot({ path: '../../output/playwright/studio-outputs/failure.png', fullPage: true })
  console.error(JSON.stringify({ errors, unexpected, text: await page.locator('body').innerText() }))
  throw error
} finally { await context.close(); await browser.close(); streamServer.closeAllConnections(); await new Promise(resolve => streamServer.close(resolve)) }
