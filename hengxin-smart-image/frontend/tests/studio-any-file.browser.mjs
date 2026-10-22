// Real built UI, disposable browser and intercepted APIs; no business writes or model calls.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3037'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } })
const page = await context.newPage()
page.setDefaultTimeout(20000)
const errors = [], unexpected = [], sent = [], uploads = [], caps = ['task.read', 'task.design']
page.on('pageerror', error => errors.push(error.message))
const task = { id: 't', name: '任意格式附件验收', productName: '灯具', brand: 'OUTON', platform: 'Amazon', market: '美国', remarks: '', skus: [{ code: 'A' }], workflow: 'studio', status: 'studio', version: 1, createdAt: '2026-10-22', updatedAt: '2026-10-22', createdBy: { id: 'u', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: caps, events: [] }
const materials = []
const state = () => ({ taskId: 't', taskVersion: 1, archiveId: null, completed: false, reopened: false, conversationId: 'c1', turns: [], materials, skills: [], activeTurnId: null })
const button = name => page.getByRole('button', { name, exact: true })
async function ready() {
  await page.getByText('与 Codex 协作', { exact: true }).waitFor()
  await page.waitForFunction(() => !document.querySelector('[aria-label="设计要求"]').disabled)
}
async function checkAttachments(names) {
  await page.getByRole('button', { name: /查看全部/ }).click()
  const dialog = page.getByRole('dialog', { name: `待发送附件 · ${names.length}`, exact: true })
  for (const name of names) await dialog.getByRole('button', { name: `移除 ${name}`, exact: true }).waitFor()
  await dialog.getByRole('button', { name: '完成', exact: true }).click()
  await dialog.waitFor({ state: 'hidden' })
}
try {
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname
    if (['api.iconify.design', 'api.unisvg.com', 'api.simplesvg.com'].includes(url.hostname)) return route.fulfill({ contentType: 'application/json', body: '{}' })
    if (url.origin !== base && !['data:', 'blob:'].includes(url.protocol)) { unexpected.push(url.href); return route.abort() }
    if (!path.startsWith('/api/')) return route.continue()
    let body = {}
    if (path.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (path === '/api/identity/v1/me') body = { name: '设计', sessionId: 'identity-test' }
    else if (path.endsWith('/tickets')) body = { ticket: 'test' }
    else if (path === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
    else if (path.includes('/auth/')) { body = { id: 'd', name: '设计', identitySessionId: 'identity-test', status: 'active', roles: ['designer'], capabilities: caps }; if (path.endsWith('/access')) body = { state: 'allowed', member: body } }
    else if (path.endsWith('/studio/transcript')) body = { items: [], cursor: 0, hasMore: false }
    else if (path.endsWith('/studio/files')) {
      const bytes = request.postDataBuffer(), name = /filename="([^"]+)"/.exec(bytes.toString('utf8'))?.[1]
      assert.ok(name); assert.ok(bytes.includes(Buffer.from([0, 255, 13, 10, 128])))
      uploads.push(name)
      const id = String(uploads.length)
      body = { id: `upload:${id}`, name, contentType: 'application/octet-stream', sizeBytes: 5, source: 'upload', url: `/api/overseas/v1/tasks/t/studio/files/${id}/content`, materialState: 'added' }
      materials.push(body)
    } else if (path.endsWith('/studio/turns')) { sent.push(request.postDataJSON()); body = state() }
    else if (path.endsWith('/studio')) body = state()
    else if (path.endsWith('/tasks/t')) body = task
    else if (path.endsWith('/materials')) body = []
    else if (path.endsWith('/jobs') || path.endsWith('/plans') || path.endsWith('/pictures')) body = { items: [] }
    else if (path.endsWith('/execution-events')) body = { items: [], cursor: 0 }
    else { unexpected.push(path); return route.abort() }
    await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.goto(`${base}/#/overseas/tasks/t`); await ready()
  const picker = page.locator('.studio-composer input[type=file]')
  assert.equal(await picker.getAttribute('accept'), null)
  const names = ['字体包.zip', '品牌.ttf', '源文件.psd', '旧文档.doc', 'README', '自定义.custom']
  await picker.setInputFiles(names.map(name => ({ name, mimeType: 'application/octet-stream', buffer: Buffer.from([0, 255, 13, 10, 128]) })))
  await button(`从列表移除 ${names.at(-1)}`).waitFor()
  await checkAttachments(names)
  for (const [event, name] of [['drop', '拖入.7z'], ['paste', '粘贴.otf']]) {
    await page.locator('.studio-composer').evaluate((el, { event, name }) => {
      const data = new DataTransfer()
      data.items.add(new File([new Uint8Array([0, 255, 13, 10, 128])], name, { type: 'application/octet-stream' }))
      el.dispatchEvent(event === 'drop' ? new DragEvent('drop', { bubbles: true, dataTransfer: data }) : new ClipboardEvent('paste', { bubbles: true, clipboardData: data }))
    }, { event, name })
    await button(`从列表移除 ${name}`).waitFor(); names.push(name)
  }
  await page.reload(); await ready()
  await checkAttachments(names)
  const note = page.getByText('支持任意格式文件', { exact: false })
  assert.ok(await note.isVisible())
  await picker.setInputFiles({ name: '空文件.zip', mimeType: 'application/zip', buffer: Buffer.alloc(0) })
  await page.getByText('请选择非空文件，单个最大 500 MB', { exact: true }).waitFor()
  assert.deepEqual(uploads, names)
  await page.getByRole('textbox', { name: '设计要求', exact: true }).fill('使用这些原始文件继续设计')
  await button('发送').click()
  await page.waitForFunction(() => !document.querySelector('[aria-label="设计要求"]').value)
  assert.equal(sent.length, 1); assert.equal(sent[0].attachmentIds.length, names.length)
  await mkdir('../../output/playwright/studio-any-file', { recursive: true })
  await page.screenshot({ path: '../../output/playwright/studio-any-file/desktop.png', fullPage: true })
  await page.setViewportSize({ width: 980, height: 800 })
  assert.ok(await note.isVisible())
  // The composer height follows ResizeObserver; assert after its layout has settled.
  await page.waitForFunction(() => {
    const el = document.querySelector('.studio-compose-note')
    if (!el) return false
    const r = el.getBoundingClientRect()
    return r.width > 0 && r.height > 0 && r.left >= 0 && r.top >= 0 && r.right <= innerWidth && r.bottom <= innerHeight
  })
  await page.screenshot({ path: '../../output/playwright/studio-any-file/narrow.png', fullPage: true })
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, [])
  console.log(JSON.stringify({ passed: true, selected: 6, dropped: 1, pasted: 1, restored: 8, sent: 8, emptyRejected: true, errors, unexpected }))
} finally { await context.close(); await browser.close() }
