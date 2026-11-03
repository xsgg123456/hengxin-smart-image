// Real Vue/Element components with controlled API fault responses; never touches production.
import assert from 'node:assert/strict'
import { mkdir, readFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3047'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } }), page = await context.newPage()
page.setDefaultTimeout(20000)
const errors = [], unexpected = [], sends = [], caps = ['task.read', 'task.design', 'task.create']
page.on('pageerror', e => errors.push(e.message))
const task = { language: 'fr', id: 't', name: '多会话交互验收', productName: '灯具', brand: 'HX', platform: 'Amazon', market: '美国', remarks: '', skus: [{ code: 'A' }], workflow: 'studio', status: 'studio', version: 1, createdAt: '2026-10-24', updatedAt: '2026-10-24', createdBy: { id: 'u', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: caps, events: [] }
const make = (id, name) => ({ id, name, version: 1, createdAt: '2026-10-24T01:00:00Z', updatedAt: '2026-10-24T01:00:00Z', activeTurnId: null, status: 'empty', turnCount: 0 })
const rows = [make('a', '主图方案'), make('b', '详情方案')], turns = { a: [], b: [] }
let failImage = false, holdImage = false, releaseImage, downloads = 0
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jD1sAAAAASUVORK5CYII=', 'base64')
const picture = id => ({ id, name: '同名.png', url: `/api/overseas/v1/tasks/t/studio/pictures/${id}/content`, width: 1, height: 1, turnId: 'turn1', sku: null, archived: false })
turns.a = [{ id: 'turn1', conversationId: 'a', text: '生成', status: 'succeeded', skillName: null, reply: '完成', error: null, jobId: 'job1', jobVersion: 1, attachments: [], referencePictures: [], pictures: [picture('p1'), picture('p2')], createdAt: '2026-11-02' }]
page.on('download', () => downloads++)
let completed = false, version = 1, deferredSend, deletionCount = 0, archiveId = null
const state = (id = rows[0]?.id || null) => ({ taskId: 't', taskVersion: version, archiveId, completed, reopened: version > 1 && !completed, conversationId: id,
  conversations: rows, maxConversations: 10, activeConversationCount: rows.filter(r => r.activeTurnId).length,
  turns: turns[id] || [], materials: [], skills: [{ id: 's', name: 'skill', displayName: '测试Skill', description: '' }], activeTurnId: rows.find(r => r.id === id)?.activeTurnId || null })
const archiveRequests = []
const button = name => page.getByRole('button', { name, exact: true })
const input = page.getByRole('textbox', { name: '设计要求', exact: true })
const choose = name => page.locator('.session-switch').filter({ has: page.getByText(name, { exact: true }) }).click()
async function ready() { await page.locator('.session-current strong').filter({ hasText: '方案' }).waitFor(); await input.waitFor(); await page.waitForFunction(() => !document.querySelector('[aria-label="设计要求"]').disabled) }
async function visibleWithin(locator) {
  assert.ok(await locator.evaluate(el => { const r = el.getBoundingClientRect(); if (!r.width || !r.height || r.left < 0 || r.right > innerWidth || r.top < 0 || r.bottom > innerHeight) return false;
    for (let p = el.parentElement; p; p = p.parentElement) { const style = getComputedStyle(p), bounds = p.getBoundingClientRect(); if (/(auto|scroll|hidden|clip)/.test(style.overflowY) && (r.top < bounds.top - 1 || r.bottom > bounds.bottom + 1)) return false } return true }))
}
try {
  await context.route('**/*', async route => {
    const url = new URL(route.request().url()), path = url.pathname, method = route.request().method(), requested = url.searchParams.get('conversationId')
    if (['api.iconify.design', 'api.unisvg.com', 'api.simplesvg.com'].includes(url.hostname)) return route.fulfill({ contentType: 'application/json', body: '{}' })
    if (url.origin !== base && !['data:', 'blob:'].includes(url.protocol)) { unexpected.push(url.href); return route.abort() }
    if (!path.startsWith('/api/')) return route.continue()
    if (path.includes('/studio/pictures/')) {
      if (!url.searchParams.has('thumbnail')) {
        if (failImage) return route.fulfill({ status: 503, body: 'failed' })
        if (holdImage) await new Promise(resolve => { releaseImage = resolve })
      }
      return route.fulfill({ contentType: 'image/png', body: method === 'HEAD' ? '' : png })
    }
    let body = {}, status = 200
    if (path.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (path === '/api/identity/v1/me') body = { name: '设计', sessionId: 'identity-test' }
    else if (path.endsWith('/tickets')) body = { ticket: 'test' }
    else if (path === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
    else if (path.includes('/auth/')) { body = { id: 'd', name: '设计', identitySessionId: 'identity-test', status: 'active', roles: ['designer'], capabilities: caps }; if (path.endsWith('/access')) body = { state: 'allowed', member: body } }
    else if (path.endsWith('/tasks/t/materials')) body = []
    else if (path.endsWith('/task-designers')) body = { items: [{ id: 'd', name: '设计', department: '设计部' }], total: 1, page: 1, pageSize: 20 }
    else if (path.endsWith('/studio/transcript')) { assert.ok(requested); body = { items: [], cursor: 0, hasMore: false } }
    else if (path.endsWith('/studio/turns')) {
      const data = route.request().postDataJSON(); sends.push(data); assert.ok(data.conversationId)
      const row = rows.find(r => r.id === data.conversationId); row.activeTurnId = `turn-${sends.length}`; row.status = 'queued'; row.updatedAt = '2026-10-24T02:00:00Z'; row.turnCount++
      if (data.text === '延迟请求') await new Promise(resolve => { deferredSend = resolve })
      body = state(data.conversationId)
    } else if (path.endsWith('/studio/conversations')) { const id = `n${rows.length}`; rows.push(make(id, `会话${rows.length + 1}`)); turns[id] = []; body = state(id) }
    else if (path.includes('/studio/conversations/')) {
      const id = path.split('/').at(-1), row = rows.find(r => r.id === id), data = route.request().postDataJSON()
      assert.ok(data.version); assert.ok(route.request().headers()['idempotency-key'])
      if (method === 'PATCH') { row.name = data.name; row.version++; body = state(id) }
      else { deletionCount++; row.deletionStatus = 'deleting'; body = state(id) }
    } else if (path.endsWith('/studio/archive')) { archiveRequests.push(route.request().postDataJSON()); body = state() }
    else if (path.endsWith('/studio/complete')) { completed = true; task.status = 'completed'; version++; task.version = version; body = state() }
    else if (path.endsWith('/studio/reopen')) { completed = false; task.status = 'studio'; version++; task.version = version; body = state() }
    else if (path.endsWith('/studio')) body = state(requested || undefined)
    else if (path.endsWith('/tasks/t')) body = { ...task, status: completed ? 'completed' : 'studio', version }
    else { unexpected.push(path); status = 404 }
    return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  })
  const out = '../../output/playwright/archive-fields'
  await mkdir(out, { recursive: true })
  const labels = ['SKU', '目标平台', '品牌', '任务名称', '品名', '语言']
  for (const width of [1366, 390]) {
    await page.setViewportSize({ width, height: 900 })
    for (const multi of [false, true]) {
      task.skus = multi ? [{ code: 'A' }, { code: 'B' }] : [{ code: 'A' }]
      task.language = multi ? null : 'fr'
      task.productName = '用于验证字段换行的长产品名称'.repeat(3)
      await page.goto(`${base}/#/overseas/tasks/t`); await page.reload(); await ready()
      if (width === 390) {
        await button('展开工作台').click()
        await page.locator('.session-list').getByRole('button', { name: '收起', exact: true }).click()
        await button('任务素材 · 0').click()
      }
      await page.locator('.studio-picture-footer .el-checkbox').first().click()
      await button('归档所选图片（1）').click()
      const dialog = page.getByRole('dialog', { name: '归档所选图片', exact: true })
      await dialog.locator('.archive-fields').waitFor()
      assert.deepEqual(await dialog.locator('dt').allTextContents(), labels)
      assert.deepEqual(await dialog.locator('dd').allTextContents(), [multi ? 'A · B' : 'A', 'Amazon', 'HX', task.name, task.productName, multi ? '未设置' : '法语'])
      const confirm = dialog.getByRole('button', { name: '确认归档', exact: true })
      if (multi) {
        assert.equal(await confirm.isDisabled(), true)
        await dialog.locator('.el-select').click()
        await page.getByRole('option', { name: 'B', exact: true }).click()
      } else assert.equal(await dialog.locator('.el-select').count(), 0)
      for (const row of await dialog.locator('.archive-fields > div').all()) {
        await row.scrollIntoViewIfNeeded(); await visibleWithin(row)
      }
      await confirm.scrollIntoViewIfNeeded(); await visibleWithin(confirm)
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
      await page.screenshot({ path: `${out}/${width}-${multi ? 'multi' : 'single'}.png` })
      await confirm.click(); await dialog.waitFor({ state: 'hidden' })
      assert.equal(archiveRequests.at(-1).sku, multi ? 'B' : 'A')
      assert.deepEqual(archiveRequests.at(-1).pictureIds, ['p1'])
    }
  }
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, [])
  console.log('PASS archive six shared fields; single SKU automatic; multi SKU selection; original archive payload; historical language; long values; desktop/mobile clipping')
} catch (error) { console.error({ errors, unexpected }); await page.screenshot({ path: '../../output/playwright/archive-fields/failure.png' }); throw error }
finally { releaseImage?.(); await context.close(); await browser.close() }
