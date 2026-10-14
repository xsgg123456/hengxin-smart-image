// Disposable browser; every API and image request is intercepted. No model invocation.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3026'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } }), page = await context.newPage()
page.setDefaultTimeout(20000)
const errors = [], unexpected = [], caps = ['task.read', 'task.design'], cursors = [], keys = []
page.on('pageerror', error => errors.push(error.message))
const material = { id: 'task:m', name: '需求.pdf', contentType: 'application/pdf', sizeBytes: 10, url: '/api/overseas/v1/materials/m/content', source: 'task' }
const task = { id: 't', name: '原生对话验收', productName: '手机', brand: 'HX', platform: 'Amazon', market: '美国', remarks: '', skus: [{ code: 'A' }], workflow: 'studio', status: 'studio', version: 1, createdAt: '2026-10-14', updatedAt: '2026-10-14', createdBy: { id: 'u', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: caps, events: [] }
let active = false, failTranscript = false, conversationId = 'c1', loseConversation = true, sent
const turn = (id, text, conversation = 'c1') => ({ id, text, conversationId: conversation, skillName: null, status: 'succeeded', reply: null, error: null, deliveryError: null, jobId: id, jobVersion: 1, attachments: [], pictures: [], referencePictures: [], createdAt: '2026-10-14' })
const turns = Array.from({ length: 12 }, (_, i) => ({ ...turn(`old${i}`, `历史需求 ${i}`, 'old'), reply: `历史回复 ${i}` }))
turns.push({ ...turn('r', '当前设计需求'), status: 'running', reply: '不应与公开消息重复的reply' })
const current = () => turns.at(-1)
const entries = []
function append(itemId, text, kind = 'message', state = 'completed', turnId = 'r') { entries.push({ id: entries.length + 1, turnId, itemId, text, kind, state, createdAt: '2026-10-14' }) }
append('first', '第一条公开消息：**完整正文**\n\n```js\nconst answer = 42\n```\n[官网](https://example.com)\n![临时图](/workspace/tmp.png)\n![外网图](https://evil.invalid/tmp.png)\n<img src="https://evil.invalid/raw.png" onerror="alert(1)">')
append('work', '正在处理公开工具状态。![临时图](/workspace/draft.png)', 'tool', 'running')
append('second', '第二条公开消息开头', 'message', 'running')
const state = () => ({ taskId: 't', completed: false, conversationId, turns, materials: [material], skills: [{ id: 'skill', name: 'example', displayName: '完整中文 Skill 标题', description: '保留选择测试' }], activeTurnId: active ? current().id : null })
const button = name => page.getByRole('button', { name, exact: true })
const messages = page.locator('.studio-messages'), markdown = page.locator('.studio-markdown')
let uploads = 0
try {
  await context.route('**/*', async route => {
    const url = new URL(route.request().url()), path = url.pathname
    if (['api.iconify.design', 'api.unisvg.com', 'api.simplesvg.com'].includes(url.hostname)) { await route.fulfill({ contentType: 'application/json', body: '{}' }); return }
    if (url.origin !== base && !['data:', 'blob:'].includes(url.protocol)) { unexpected.push(route.request().url()); await route.abort(); return }
    if (!path.startsWith('/api/')) return route.continue()
    let body = {}, status = 200
    if (path.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (path === '/api/identity/v1/me') body = { name: '设计', sessionId: 'identity-test' }
    else if (path.endsWith('/tickets')) body = { ticket: 'test' }
    else if (path === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
    else if (path.includes('/auth/')) { body = { id: 'd', name: '设计', identitySessionId: 'identity-test', status: 'active', roles: ['designer'], capabilities: caps }; if (path.endsWith('/access')) body = { state: 'allowed', member: body } }
    else if (path.endsWith('/studio/transcript')) {
      const after = Number(url.searchParams.get('after')); cursors.push(after)
      const available = entries.filter(e => e.id > after), items = available.slice(0, 2)
      body = { items, cursor: items.at(-1)?.id ?? after, hasMore: available.length > items.length }
      if (failTranscript) { status = 503; body = {} }
    } else if (path.endsWith('/studio/conversations')) {
      keys.push(route.request().headers()['idempotency-key']); conversationId = 'c2'
      if (loseConversation) { loseConversation = false; await route.abort(); return }
      body = state()
    } else if (path.endsWith('/studio/turns')) {
      sent = route.request().postDataJSON(); turns.push({ ...turn('new', sent.text, conversationId), status: 'running' }); active = true; body = state()
    } else if (path.endsWith('/cancel')) {
      active = false; current().status = 'cancelled'; body = state()
    } else if (path.endsWith('/pictures/p/content')) {
      await route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jQmQAAAAASUVORK5CYII=', 'base64') }); return
    } else if (path.endsWith('/studio/files')) { uploads++; body = { ...material, id: `upload:${uploads}`, source: 'upload', name: `文件${uploads}.txt`, contentType: 'text/plain', url: `/api/overseas/v1/tasks/t/studio/files/${uploads}/content` } }
    else if (path.endsWith('/studio')) body = state()
    else if (path.endsWith('/tasks/t')) body = task
    else if (path.endsWith('/materials')) body = []
    else if (path.endsWith('/jobs')) body = { items: [] }
    else if (path.endsWith('/execution-events')) body = { items: [], cursor: 0 }
    else if (path.endsWith('/plans') || path.endsWith('/pictures')) body = { items: [], taskVersion: 1 }
    else { unexpected.push(path); await route.abort(); return }
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.goto(`${base}/#/overseas/tasks/t`)
  const input = page.locator('.studio-composer input[type=file]')
  await input.waitFor({ state: 'attached' })
  await page.getByText('最多 100 个附件 · 单个最大 500 MB', { exact: true }).waitFor()
  await input.setInputFiles(Array.from({ length: 101 }, (_, i) => ({ name: `${i}.txt`, mimeType: 'text/plain', buffer: Buffer.from('x') })))
  await page.getByText(/每条消息最多添加 100 个附件/).waitFor(); assert.equal(uploads, 0)
  await input.setInputFiles(Array.from({ length: 100 }, (_, i) => ({ name: `${i}.txt`, mimeType: 'text/plain', buffer: Buffer.from('x') })))
  await page.waitForFunction(() => document.querySelectorAll('.studio-composer .studio-attachment').length === 100)
  assert.equal(uploads, 100)
  await input.setInputFiles({ name: 'extra.txt', mimeType: 'text/plain', buffer: Buffer.from('x') })
  await page.getByText(/每条消息最多添加 100 个附件/).waitFor(); assert.equal(uploads, 100)
  await mkdir('../../output/playwright/upload-limits', { recursive: true })
  await page.screenshot({ path: '../../output/playwright/upload-limits/desktop.png', fullPage: true })
  await page.locator('.studio-composer .studio-attachment button').first().click()
  await input.setInputFiles({ name: 'retry.txt', mimeType: 'text/plain', buffer: Buffer.from('x') })
  await page.waitForFunction(() => document.querySelectorAll('.studio-composer .studio-attachment').length === 100)
  assert.equal(uploads, 101)
  await page.setViewportSize({ width: 390, height: 844 })
  await page.waitForTimeout(500)
  if (await page.locator('.menu-model').isVisible()) await page.locator('.menu-model').click({ position: { x: 350, y: 400 } })
  await button('收起').click()
  await page.waitForTimeout(400)
  await input.setInputFiles({ name: 'extra-mobile.txt', mimeType: 'text/plain', buffer: Buffer.from('x') })
  await page.getByText(/每条消息最多添加 100 个附件/).waitFor()
  for (const locator of [page.locator('.studio-dropzone'), page.locator('.studio-page .el-alert').first(), button('发送')]) {
    await locator.scrollIntoViewIfNeeded()
    const box = await locator.boundingBox()
    assert.ok(box && box.x >= -1 && box.x + box.width <= 391 && box.y >= -1 && box.y + box.height <= 845, JSON.stringify(box))
  }
  await page.locator('.studio-composer .studio-attachment button').first().click()
  await input.setInputFiles({ name: 'mobile-retry.txt', mimeType: 'text/plain', buffer: Buffer.from('x') })
  await page.waitForFunction(() => document.querySelectorAll('.studio-composer .studio-attachment').length === 100)

  await page.screenshot({ path: '../../output/playwright/upload-limits/mobile.png', fullPage: true })
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
  await button('发送').click(); await button('停止').waitFor(); assert.equal(sent.attachmentIds.length, 100)
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, [])
  console.log('PASS: 101 blocked before upload; 100 upload/send; remove/retry; 500 MB text; desktop/mobile')
} finally { await browser.close() }
