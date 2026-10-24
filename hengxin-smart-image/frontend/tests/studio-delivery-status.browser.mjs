// Isolated real UI: never reads production sessions or calls a model.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3034'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } }), page = await context.newPage()
const errors = [], unexpected = [], caps = ['task.read', 'task.design']
page.setDefaultTimeout(20000)
page.on('pageerror', error => errors.push(error.message))
const task = { id: 't', name: '收图状态验收', productName: '灯具', brand: 'HX', platform: 'Amazon', market: '美国', remarks: '', skus: [{ code: 'A' }], workflow: 'studio', status: 'studio', version: 1, createdAt: '2026-10-24', updatedAt: '2026-10-24', createdBy: { id: 'u', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: caps, events: [] }
const row = { id: 'c', name: '主图会话', version: 1, createdAt: '2026-10-24', updatedAt: '2026-10-24', activeTurnId: 'turn', status: 'running', turnCount: 1 }
const picture = { id: 'p', name: '已保存.jpg', url: '/api/overseas/v1/tasks/t/studio/pictures/p/content', width: 1600, height: 1600, turnId: 'turn', sku: null, archived: false }
const turn = { id: 'turn', conversationId: 'c', text: '生成图片', skillName: null, status: 'collecting', reply: '最终图片已经输出', error: null, jobId: 'j', jobVersion: 1, attachments: [], referencePictures: [], pictures: [], createdAt: '2026-10-24', deliveryStatus: { state: 'capturing', expected: null, saved: 0 } }
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
    if (path.endsWith('/pictures/p/content')) return route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+a9b8AAAAASUVORK5CYII=', 'base64') })
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
  await page.goto(`${base}/#/overseas/tasks/t`)
  await page.getByText('回复已结束，正在接收文件', { exact: true }).waitFor()
  turn.deliveryStatus = { state: 'saving', expected: 8, saved: 1 }; turn.pictures = [picture]
  await page.getByRole('button', { name: '刷新', exact: true }).click()
  await page.getByText('回复已结束，文件保存中 1/8', { exact: true }).waitFor()
  assert.equal(await page.locator('.studio-pictures .studio-picture').count(), 1)
  await checkVisible(page.locator('.studio-messages .el-alert__title'))
  await mkdir('../../output/playwright/studio-delivery-status', { recursive: true })
  await page.screenshot({ path: '../../output/playwright/studio-delivery-status/desktop-saving.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 })
  await page.getByRole('button', { name: '展开工作台', exact: true }).click()
  await page.locator('.session-list').getByRole('button', { name: '收起', exact: true }).click()
  await page.getByRole('button', { name: '任务素材 · 0', exact: true }).click()
  await checkVisible(page.locator('.studio-messages .el-alert__title'))
  await page.screenshot({ path: '../../output/playwright/studio-delivery-status/mobile-saving.png', fullPage: true })
  turn.deliveryStatus = { state: 'waiting', expected: 8, saved: 1 }
  await page.getByRole('button', { name: '刷新', exact: true }).click()
  await page.getByText('文件收取已结束，已保存 1/8 个。未保存的文件可通过“取回文件”重试。', { exact: true }).waitFor()
  turn.deliveryStatus = { state: 'complete', expected: 1, saved: 1 }; turn.status = row.status = 'succeeded'; row.activeTurnId = null
  await page.getByRole('button', { name: '刷新', exact: true }).click()
  await page.waitForFunction(() => !document.querySelector('.studio-messages .el-alert'))
  assert.equal(await page.locator('.studio-pictures .studio-picture').count(), 1)
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, [])
  console.log('PASS: capturing, partial image, saving/waiting counts, completion, desktop/mobile clipping; no model calls')
} catch (error) {
  await mkdir('../../output/playwright/studio-delivery-status', { recursive: true })
  await page.screenshot({ path: '../../output/playwright/studio-delivery-status/failure.png', fullPage: true })
  console.error(JSON.stringify({ errors, unexpected, text: await page.locator('body').innerText() }))
  throw error
} finally { await context.close(); await browser.close() }
