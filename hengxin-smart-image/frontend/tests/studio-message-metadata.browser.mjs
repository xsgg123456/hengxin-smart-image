// Real application/components, isolated local browser contexts and mocked API only.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3053'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const output = '../../output/playwright/message-metadata'
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
const errors = [], unexpected = [], results = []
const longName = '超长实际发送人姓名用于验证窄屏完整自动换行'.repeat(4)
let activePage
try {
  for (const width of [1366, 390]) {
    let finished = false, viewer = '另一个查看人'
    const context = await browser.newContext({ viewport: { width, height: 900 }, timezoneId: 'America/Los_Angeles' })
    const page = await context.newPage(); activePage = page; page.setDefaultTimeout(15000)
    page.on('pageerror', e => errors.push(e.message))
    const root = '/api/overseas/v1/tasks/t/studio'
    const task = { id: 't', name: '消息身份时间验收', productName: '灯具', brand: 'OUTON', platform: 'Amazon', market: '', remarks: '', skus: [{ code: 'A' }], workflow: 'studio', status: 'studio', version: 1, createdAt: '2026-11-02T01:00:00Z', updatedAt: '2026-11-02T01:00:00Z', createdBy: { id: 'creator', name: '任务提交人' }, designer: { id: 'designer', name: '负责设计', status: 'active', eligible: true }, events: [], requirementsReviews: [], capabilities: ['task.read'] }
    const turn = (id, extra = {}) => ({ id, text: `${id} 设计要求`, reply: `${id} 回复`, status: 'succeeded', skillName: null, error: null, jobId: id, jobVersion: 1, conversationId: 'a', createdAt: '2026-11-02T01:02:03Z', attachments: [], referencePictures: [], pictures: [], ...extra })
    const turns = () => [
      turn('first', { actor: { id: 'sender-a', name: '发送人甲' }, replyAt: '2026-11-02T02:03:04Z', replyTimeSource: 'message' }),
      turn('second', { actor: { id: 'sender-b', name: '发送人乙' }, replyAt: '2026-11-02T03:04:05Z', replyTimeSource: 'completed' }),
      turn('legacy', { createdAt: '' }),
      turn('blank', { actor: { id: 'missing', name: '   ' }, createdAt: '', replyAt: null, replyTimeSource: null }),
      turn('long', { actor: { id: 'long', name: longName }, replyAt: '2026-11-02T04:05:06Z', replyTimeSource: 'message' }),
      turn('fallback', { actor: { id: 'sender-a', name: '发送人甲' }, reply: null, replyAt: '2026-11-02T05:06:07Z', replyTimeSource: 'message' }),
      turn('running', { actor: { id: 'sender-b', name: '发送人乙' }, reply: finished ? '执行结束回复' : null, status: finished ? 'succeeded' : 'running', replyAt: finished ? '2026-11-02T06:07:08Z' : null, replyTimeSource: finished ? 'message' : null })
    ]
    await context.route('**/*', async route => {
      const req = route.request(), url = new URL(req.url()), path = url.pathname
      if (['api.iconify.design', 'api.unisvg.com', 'api.simplesvg.com'].includes(url.hostname)) return route.fulfill({ json: {} })
      if (url.origin !== base) { unexpected.push(url.href); return route.abort() }
      if (!path.startsWith('/api/')) return route.continue()
      let body
      if (path.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
      else if (path === '/api/identity/v1/me') body = { name: viewer, sessionId: 'metadata-test' }
      else if (path.endsWith('/tickets')) body = { ticket: 'test' }
      else if (path === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
      else if (path.includes('/auth/')) { body = { id: 'viewer', name: viewer, identitySessionId: 'metadata-test', status: 'active', roles: ['designer'], capabilities: ['task.read'] }; if (path.endsWith('/access')) body = { state: 'allowed', member: body } }
      else if (path === `${root}/transcript`) body = { items: [{ id: 1, turnId: 'fallback', itemId: 'm', kind: 'message', text: '历史公开回复', state: 'completed', createdAt: '2026-11-02T05:06:07Z' }], cursor: 1, hasMore: false }
      else if (path === root) body = { taskId: 't', taskVersion: 1, archiveId: null, completed: false, reopened: false, conversationId: 'a', conversations: [{ id: 'a', name: '消息测试会话', version: 1, createdAt: '2026-11-02T01:00:00Z', updatedAt: '2026-11-02T01:00:00Z', activeTurnId: finished ? null : 'running', status: finished ? 'succeeded' : 'running', turnCount: 7 }], maxConversations: 10, activeConversationCount: finished ? 0 : 1, turns: turns(), materials: [], skills: [], activeTurnId: finished ? null : 'running' }
      else if (path.endsWith('/tasks/t/materials')) body = []
      else if (path.endsWith('/tasks/t')) body = task
      else { unexpected.push(`${req.method()} ${path}`); return route.fulfill({ status: 404, json: {} }) }
      return route.fulfill({ json: body })
    })
    async function ready() {
      await page.locator('.studio-message.user').nth(6).waitFor(); await page.getByText('历史公开回复', { exact: true }).waitFor()
      if (width === 390) {
        await page.getByRole('button', { name: '展开工作台', exact: true }).click()
        if (await page.locator('.session-list').count()) await page.getByRole('button', { name: '会话 · 1/10', exact: true }).click()
        if (await page.locator('.studio-materials').count()) await page.getByRole('button', { name: '任务素材 · 0', exact: true }).click()
      }
    }
    const userHeaders = page.locator('.studio-message.user .studio-message-name')
    const assistantHeaders = page.locator('.studio-message.assistant .studio-message-name')
    await page.goto(`${base}/#/overseas/tasks/t`); await page.reload(); await ready()
    assert.equal(await page.evaluate(() => Intl.DateTimeFormat().resolvedOptions().timeZone), 'America/Los_Angeles')
    assert.deepEqual(await userHeaders.allTextContents(), ['发送人甲2026-11-02 09:02:03', '发送人乙2026-11-02 09:02:03', '未知操作人时间未记录', '未知操作人时间未记录', `${longName}2026-11-02 09:02:03`, '发送人甲2026-11-02 09:02:03', '发送人乙2026-11-02 09:02:03'])
    assert.deepEqual(await assistantHeaders.allTextContents(), ['Codex 已回复2026-11-02 10:03:04', 'Codex 已回复完成于 2026-11-02 11:04:05', 'Codex 已回复时间未记录', 'Codex 已回复时间未记录', 'Codex 已回复2026-11-02 12:05:06', 'Codex 已回复2026-11-02 13:06:07', 'Codex 执行中'])
    assert.equal(await page.getByRole('textbox', { name: '设计要求', exact: true }).isDisabled(), true)
    const before = await userHeaders.allTextContents()
    viewer = '更换后的查看人'; await page.reload(); await ready()
    assert.deepEqual(await userHeaders.allTextContents(), before, '更换查看人和刷新不能改变历史署名')
    await userHeaders.nth(4).scrollIntoViewIfNeeded()
    const bounds = await userHeaders.nth(4).evaluate(node => {
      const rect = node.getBoundingClientRect(), range = document.createRange(); range.selectNodeContents(node)
      const visible = [...range.getClientRects()].every(r => r.left >= rect.left - 1 && r.right <= rect.right + 1)
      const parents = []; for (let p = node.parentElement; p; p = p.parentElement) { const s = getComputedStyle(p); if (/auto|hidden|scroll|clip/.test(s.overflowX + s.overflowY)) { const r = p.getBoundingClientRect(); parents.push({ left: r.left, right: r.right, top: r.top, bottom: r.bottom }) } }
      const uncovered = [...range.getClientRects()].filter(r => r.width && r.height).every(r => node.contains(document.elementFromPoint((r.left + r.right) / 2, (r.top + r.bottom) / 2)))
      return { width: rect.width, height: rect.height, visible, uncovered, contained: parents.every(r => rect.left >= r.left - 1 && rect.right <= r.right + 1 && rect.top >= r.top - 1 && rect.bottom <= r.bottom + 1), viewport: rect.left >= 0 && rect.right <= innerWidth }
    })
    assert.equal(bounds.visible, true, '姓名及时间文本不能横向挤出消息头'); assert.equal(bounds.contained, true, '消息头不能被滚动祖先裁切'); assert.equal(bounds.viewport, true); assert.equal(bounds.uncovered, true, '消息头不能被浮层遮挡')
    if (width === 390) assert.ok(bounds.height > 40, '长姓名应真实换行')
    await page.screenshot({ path: `${output}/${width}-long-name.png`, fullPage: true })
    finished = true; await page.getByRole('button', { name: '刷新', exact: true }).click()
    await page.getByText('执行结束回复', { exact: true }).waitFor()
    assert.equal(await assistantHeaders.nth(6).textContent(), 'Codex 已回复2026-11-02 14:07:08')
    const stable = await assistantHeaders.allTextContents(); await page.reload(); await ready()
    assert.deepEqual(await assistantHeaders.allTextContents(), stable)
    await assistantHeaders.nth(6).scrollIntoViewIfNeeded(); await page.screenshot({ path: `${output}/${width}-finished.png`, fullPage: true })
    results.push({ width, timezone: 'America/Los_Angeles', headers: stable, bounds })
    await context.close()
  }
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, [])
  await writeFile(`${output}/results.json`, JSON.stringify(results, null, 2))
  console.log('PASS message metadata real component browser', JSON.stringify(results))
} catch (error) {
  if (activePage && !activePage.isClosed()) { await activePage.screenshot({ path: `${output}/failure.png`, fullPage: true }); console.error({ errors, unexpected, text: await activePage.locator('body').innerText() }) }
  throw error
} finally { await browser.close() }
