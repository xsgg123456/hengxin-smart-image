// Real Vue/Element components with controlled API fault responses; never touches production.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3032'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } }), page = await context.newPage()
page.setDefaultTimeout(20000)
const errors = [], unexpected = [], sends = [], caps = ['task.read', 'task.design']
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
    const url = new URL(route.request().url()), path = url.pathname, method = route.request().method(), requested = url.searchParams.get('conversationId')
    if (['api.iconify.design', 'api.unisvg.com', 'api.simplesvg.com'].includes(url.hostname)) return route.fulfill({ contentType: 'application/json', body: '{}' })
    if (url.origin !== base && !['data:', 'blob:'].includes(url.protocol)) { unexpected.push(url.href); return route.abort() }
    if (!path.startsWith('/api/')) return route.continue()
    let body = {}, status = 200
    if (path.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (path === '/api/identity/v1/me') body = { name: '设计', sessionId: 'identity-test' }
    else if (path.endsWith('/tickets')) body = { ticket: 'test' }
    else if (path === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
    else if (path.includes('/auth/')) { body = { id: 'd', name: '设计', identitySessionId: 'identity-test', status: 'active', roles: ['designer'], capabilities: caps }; if (path.endsWith('/access')) body = { state: 'allowed', member: body } }
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
    } else if (path.endsWith('/studio/complete')) { completed = true; task.status = 'completed'; version++; task.version = version; body = state() }
    else if (path.endsWith('/studio/reopen')) { completed = false; task.status = 'studio'; version++; task.version = version; body = state() }
    else if (path.endsWith('/studio')) body = state(requested || undefined)
    else if (path.endsWith('/tasks/t')) body = { ...task, status: completed ? 'completed' : 'studio', version }
    else { unexpected.push(path); status = 404 }
    return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.goto(`${base}/#/overseas/tasks/t`); await ready()
  await input.fill('主图草稿'); await choose('详情方案'); await input.fill('详情草稿'); await choose('主图方案'); assert.equal(await input.inputValue(), '主图草稿')
  await button('＋ 新建会话').click(); await page.getByText('会话3', { exact: true }).first().waitFor(); assert.equal(await input.inputValue(), '')
  await choose('详情方案'); assert.equal(await input.inputValue(), '详情草稿'); await page.reload(); await ready(); assert.equal(await input.inputValue(), '详情草稿')
  await choose('主图方案'); await input.fill('延迟请求'); await button('发送').click(); await choose('详情方案'); await input.fill('新详情草稿')
  assert.equal(await button('发送').isEnabled(), true); await page.waitForFunction(() => document.querySelector('.session-status.running')); deferredSend(); await button('刷新').click(); assert.equal(await input.inputValue(), '新详情草稿')
  rows[0].activeTurnId = null; rows[0].status = 'succeeded'; rows[0].updatedAt = '2026-10-24T03:00:00Z'; await button('刷新').click(); await page.getByText('有新结果', { exact: true }).waitFor(); assert.equal(await input.inputValue(), '新详情草稿')
  await choose('主图方案'); assert.equal(await input.inputValue(), ''); await button('重命名').click(); await page.locator('.el-message-box input').fill('主图定稿'); await button('保存').click(); await page.locator('.session-current strong').filter({ hasText: '主图定稿' }).waitFor()
  await button('管理会话3').click(); await page.getByRole('menuitem', { name: '删除会话', exact: true }).click(); await button('取消').click(); assert.equal(deletionCount, 0)
  await button('管理会话3').click(); await page.getByRole('menuitem', { name: '删除会话', exact: true }).click(); await button('确认删除').click(); await page.getByText('删除中', { exact: true }).waitFor(); assert.equal(deletionCount, 1)
  archiveId = 'archive'; await button('刷新').click(); await button('完成任务').click(); await button('确认完成').click(); await page.getByText('任务已完成 · 所有会话只读', { exact: true }).waitFor()
  await choose('详情方案'); assert.equal(await input.inputValue(), '新详情草稿'); assert.equal(await input.isDisabled(), true)
  await button('解冻工作台').click(); await button('取消').click(); assert.equal(completed, true); await button('解冻工作台').click(); await button('确认解冻').click(); await page.waitForFunction(() => !document.querySelector('[aria-label="设计要求"]').disabled); assert.equal(sends.length, 1)
  await mkdir('../../output/playwright/studio-sessions', { recursive: true }); await page.screenshot({ path: '../../output/playwright/studio-sessions/desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 }); await button('展开工作台').click(); await page.locator('.session-list').getByRole('button', { name: '收起', exact: true }).click(); await page.locator('.studio-materials').getByRole('button', { name: '收起', exact: true }).click()
  await visibleWithin(input); await visibleWithin(button('发送')); await page.screenshot({ path: '../../output/playwright/studio-sessions/mobile.png', fullPage: true })
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, [])
  console.log('PASS: actual Vue components, isolated drafts/refresh, delayed send, unread completion, create/rename/delete confirmation, task lock/reopen, desktop/mobile clipping')
} finally { deferredSend?.(); await context.close(); await browser.close() }
