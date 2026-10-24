// Real Vue/Element components with controlled API fault responses; never touches production.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3032'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } }), page = await context.newPage()
page.setDefaultTimeout(20000)
const errors = [], unexpected = [], sends = [], caps = ['task.read', 'task.design', 'task.create']
page.on('pageerror', e => errors.push(e.message))
const task = { id: 't', name: '多会话交互验收', productName: '灯具', brand: 'HX', platform: 'Amazon', market: '美国', remarks: '', skus: [{ code: 'A' }], workflow: 'studio', status: 'studio', version: 1, createdAt: '2026-10-24', updatedAt: '2026-10-24', createdBy: { id: 'u', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: caps, events: [] }
const make = (id, name) => ({ id, name, version: 1, createdAt: '2026-10-24T01:00:00Z', updatedAt: '2026-10-24T01:00:00Z', activeTurnId: null, status: 'empty', turnCount: 0 })
const rows = [make('a', '主图方案'), make('b', '详情方案')], turns = { a: [], b: [] }
let completed = false, version = 1, deferredSend, deletionCount = 0, archiveId = null
const state = (id = rows[0]?.id || null) => ({ taskId: 't', taskVersion: version, archiveId, completed, reopened: version > 1 && !completed, conversationId: id,
  conversations: rows, maxConversations: 10, activeConversationCount: rows.filter(r => r.activeTurnId).length,
  turns: turns[id] || [], materials: [], skills: [{ id: 's', name: 'skill', displayName: '测试Skill', description: '' }], activeTurnId: rows.find(r => r.id === id)?.activeTurnId || null })
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
    const url = new URL(route.request().url()), path = url.pathname
    if (['api.iconify.design', 'api.unisvg.com', 'api.simplesvg.com'].includes(url.hostname)) return route.fulfill({ json: {} })
    if (url.origin !== base) { unexpected.push(url.href); return route.abort() }
    if (!path.startsWith('/api/')) return route.continue()
    let body = {}, status = 200
    if (path.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (path === '/api/identity/v1/me') body = { name: '设计', sessionId: 'identity-test' }
    else if (path.endsWith('/tickets')) body = { ticket: 'test' }
    else if (path === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
    else if (path.includes('/auth/')) { body = { id: 'd', name: '设计', identitySessionId: 'identity-test', status: 'active', roles: ['super_admin'], capabilities: caps }; if (path.endsWith('/access')) body = { state: 'allowed', member: body } }
    else if (path.endsWith('/studio/transcript')) body = { items: [], cursor: 0, hasMore: false }
    else if (path.endsWith('/studio')) body = state(url.searchParams.get('conversationId') || undefined)
    else if (path.endsWith('/tasks/t/materials')) body = []
    else if (path.endsWith('/tasks/t')) body = task
    else if (path.endsWith('/task-designers')) body = { items: [], total: 0, page: 1, pageSize: 20 }
    else { unexpected.push(path); status = 404 }
    return route.fulfill({ status, json: body })
  })
  await page.goto(`${base}/#/overseas/tasks/t`); await ready()
  await mkdir('../../output/playwright/overseas-polish', { recursive: true })
  const expanded = page.getByRole('textbox', { name: '展开的设计要求', exact: true })
  const long = '保留真实结构，保持尺寸比例。\n'.repeat(100)
  for (const size of [{ width: 1920, height: 911 }, { width: 1366, height: 900 }]) {
    await page.setViewportSize(size); await input.fill('短草稿')
    const before = await input.boundingBox()
    await input.fill(long); assert.equal((await input.boundingBox()).height, before.height)
    assert.equal(await input.getAttribute('rows'), '2')
    await visibleWithin(button('展开编辑')); await visibleWithin(button('发送'))
    await page.screenshot({ animations: 'disabled', path: `../../output/playwright/overseas-polish/formal-${size.width}.png` })
    await button('展开编辑').click(); await expanded.waitFor()
    assert.equal(await expanded.inputValue(), long)
    assert.equal(await expanded.evaluate(el => getComputedStyle(el).fontSize), '16px')
    await expanded.fill('第一行'); await expanded.press('End'); await expanded.press('Enter'); await expanded.type('第二行')
    assert.equal(await expanded.inputValue(), '第一行\n第二行')
    await visibleWithin(button('完成编辑'))
    await page.screenshot({ animations: 'disabled', path: `../../output/playwright/overseas-polish/dialog-${size.width}.png` })
    await expanded.press('Escape'); await expanded.waitFor({ state: 'hidden' })
    assert.equal(await input.inputValue(), '第一行\n第二行')
    await button('展开编辑').click(); await expanded.fill(long); await button('完成编辑').click(); await expanded.waitFor({ state: 'hidden' })
    assert.equal(await input.inputValue(), long)
  }
  await choose('详情方案'); assert.equal(await input.inputValue(), '')
  await button('展开编辑').click(); await expanded.fill('详情专属草稿'); await button('完成编辑').click()
  await choose('主图方案'); assert.equal(await input.inputValue(), long)
  completed = true; version++; task.version = version; task.status = 'completed'; await button('刷新').click(); await page.waitForFunction(() => [...document.querySelectorAll('button')].find(b => b.textContent.includes('展开编辑'))?.disabled)
  await page.goto(`${base}/#/overseas/create`)
  const platform = page.locator('.el-form-item').filter({ has: page.locator('.el-form-item__label', { hasText: '目标平台' }) })
  await platform.locator('.el-select').click()
  const labels = ['亚马逊/Amazon', '美客多/Mercado Libre', '沃尔玛/Walmart', '家得宝/The Home Depot', '虾皮/Shopee', '威费尔/Wayfair']
  assert.deepEqual(await page.getByRole('option').allTextContents(), labels)
  await page.getByRole('option', { name: labels[3], exact: true }).click()
  assert.ok((await platform.innerText()).includes(labels[3]))
  assert.equal(await page.locator('.el-form-item__label').getByText('目标站点', { exact: true }).count(), 1)
  assert.equal(await page.getByText('目标站点 / 语言', { exact: true }).count(), 0)
  await page.screenshot({ animations: 'disabled', path: '../../output/playwright/overseas-polish/create.png', fullPage: true })
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, [])
  console.log('PASS: fixed two rows; long draft; 1920/1366 clipping; 16px/Enter/Escape/done; session drafts; completed disabled; six platforms/site label')
} catch (error) {
  await page.screenshot({ animations: 'disabled', path: '../../output/playwright/overseas-polish/failure.png', fullPage: true })
  console.error(JSON.stringify({ errors, unexpected, text: await page.locator('body').innerText() })); throw error
} finally { await browser.close() }




