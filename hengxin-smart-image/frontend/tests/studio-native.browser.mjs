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
let active = true, failTranscript = false, conversationId = 'c1', loseConversation = true, sent
const turn = (id, text, conversation = 'c1') => ({ id, text, conversationId: conversation, skillName: null, status: 'succeeded', reply: null, error: null, deliveryError: null, jobId: id, jobVersion: 1, attachments: [], pictures: [], referencePictures: [], createdAt: '2026-10-14' })
const turns = Array.from({ length: 12 }, (_, i) => ({ ...turn(`old${i}`, `历史需求 ${i}`, 'old'), reply: `历史回复 ${i}` }))
turns.push({ ...turn('r', '当前设计需求'), status: 'running', reply: '不应与公开消息重复的reply' })
const current = () => turns.at(-1)
const entries = []
function append(itemId, text, kind = 'message', state = 'completed', turnId = 'r') { entries.push({ id: entries.length + 1, turnId, itemId, text, kind, state, createdAt: '2026-10-14' }) }
append('first', '第一条公开消息：**完整正文**\n\n```js\nconst answer = 42\n```\n[官网](https://example.com)\n![临时图](/workspace/tmp.png)\n![外网图](https://evil.invalid/tmp.png)\n<img src="https://evil.invalid/raw.png" onerror="alert(1)">')
append('work', '正在处理公开工具状态。![临时图](/workspace/draft.png)', 'tool', 'running')
append('second', '第二条公开消息开头', 'message', 'running')
const state = () => ({ taskId: 't', taskVersion: 1, archiveId: null, reopened: false, completed: false, conversationId, turns, materials: [material], skills: [{ id: 'skill', name: 'example', displayName: '完整中文 Skill 标题', description: '保留选择测试' }], activeTurnId: active ? current().id : null })
const button = name => page.getByRole('button', { name, exact: true })
const messages = page.locator('.studio-messages'), markdown = page.locator('.studio-markdown')
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
    } else if (path.endsWith('/studio')) body = state()
    else if (path.endsWith('/tasks/t')) body = task
    else if (path.endsWith('/materials')) body = []
    else if (path.endsWith('/jobs')) body = { items: [] }
    else if (path.endsWith('/execution-events')) body = { items: [], cursor: 0 }
    else if (path.endsWith('/plans') || path.endsWith('/pictures')) body = { items: [], taskVersion: 1 }
    else { unexpected.push(path); await route.abort(); return }
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.goto(`${base}/#/overseas/tasks/t`)
  await page.getByText('第二条公开消息开头', { exact: true }).waitFor()
  assert.deepEqual(cursors.slice(0, 2), [0, 2]); assert.equal(await messages.getByText('不应与公开消息重复的reply').count(), 0)
  assert.equal(await messages.locator('pre code').innerText(), 'const answer = 42\n')
  assert.equal(await messages.locator('.studio-execution[open]').count(), 1)
  assert.equal(await markdown.locator('img').count(), 0); assert.equal(await button('开始新对话').isDisabled(), true)
  await mkdir('../../output/playwright/studio-native', { recursive: true })
  await page.screenshot({ path: '../../output/playwright/studio-native/running-markdown.png', fullPage: true })
  const input = page.getByRole('textbox', { name: '设计要求', exact: true }), refresh = button('刷新')
  await input.fill('保留草稿'); await page.locator('.studio-materials .el-checkbox').filter({ hasText: '全选素材' }).click(); await button('引用所选素材（1）').click()
  await page.getByRole('combobox', { name: '选择 Skill', exact: true }).click(); await page.getByRole('option').filter({ hasText: '完整中文 Skill 标题' }).click()
  await messages.evaluate(el => { el.scrollTop = 100 }); await page.waitForTimeout(100)
  const position = await messages.evaluate(el => el.scrollTop)
  assert.equal(position, 100)
  const long = '长文公开内容。'.repeat(1600) + '长文末尾验收'
  append('second', long)
  await page.getByText(long, { exact: true }).waitFor()
  assert.equal(await messages.evaluate(el => el.scrollTop), position)
  assert.equal(await refresh.evaluate(el => el.classList.contains('is-loading')), false)
  assert.equal(await input.inputValue(), '保留草稿'); assert.equal(await button('移除 需求.pdf').count(), 1); assert.equal(await button('查看 Skill 说明').count(), 1)
  await messages.evaluate(el => { el.scrollTop = el.scrollHeight }); await page.waitForTimeout(100)
  append('third', '追加的一整条消息\n\n' + '下一段\n\n'.repeat(20))
  await messages.getByText('追加的一整条消息', { exact: true }).waitFor(); await page.waitForTimeout(100)
  assert.ok(await messages.evaluate(el => el.scrollHeight - el.scrollTop - el.clientHeight < 3))
  failTranscript = true; await refresh.click(); await page.locator('.studio-chat-card>.el-card__body>.el-alert--error').waitFor()
  append('after-fail', '断线期间追加的完整消息'); failTranscript = false; await refresh.click(); await messages.getByText('断线期间追加的完整消息', { exact: true }).waitFor()
  assert.equal(await messages.getByText('第一条公开消息：', { exact: false }).count(), 1)
  current().status = 'failed'; current().error = '执行中断'; active = false
  await refresh.click(); await messages.getByText('执行中断', { exact: true }).waitFor()
  assert.equal(await messages.locator('.studio-markdown img').count(), 0); assert.equal(await messages.getByText(long, { exact: true }).count(), 1)
  const picture = { id: 'p', name: '正式图片', sourcePath: 'sandbox:/workspace/正式 图片.png', url: '/api/overseas/v1/tasks/t/studio/pictures/p/content', width: 800, height: 800, turnId: 'delivery-turn', sku: null, archived: false }
  turns.push({ ...turn('delivery-turn', '正式交付'), pictures: [picture], deliveryError: '另一个图片未能收取，已保留文字' })
  append('earlier-draft', '过程说明：![过程草稿](<sandbox:/workspace/正式 图片.png>)', 'message', 'completed', 'delivery-turn')
  append('delivery', '## 草稿\n![非交付段落](<sandbox:/workspace/正式 图片.png>)\n\n## 正式交付\n![正式图片](<sandbox:/workspace/正式 图片.png>)\n![未交付](/workspace/other.png)', 'message', 'completed', 'delivery-turn')
  await refresh.click(); await messages.locator('.studio-picture img').waitFor()
  assert.equal(await messages.locator('.studio-markdown img').count(), 0)
  assert.equal(await messages.locator('.studio-picture img').count(), 1); assert.equal(await messages.locator('.studio-picture img').getAttribute('src'), picture.url)
  assert.equal(await messages.getByText('过程说明：', { exact: false }).count(), 1)
  assert.equal(await messages.locator('.studio-execution[open]').count(), 0); assert.equal(await messages.getByText(long, { exact: true }).count(), 1)
  await page.reload(); await messages.getByText(long, { exact: true }).waitFor(); assert.equal(await messages.getByText('断线期间追加的完整消息', { exact: true }).count(), 1)
  await input.fill('新会话失败前草稿'); await button('开始新对话').click()
  const dialog = page.getByRole('dialog', { name: '开始新对话', exact: true }); await dialog.waitFor(); assert.ok((await dialog.innerText()).includes('旧对话、任务材料'))
  await button('确认开始新对话').click(); await button('核实并重试上次操作').waitFor()
  assert.equal(await input.inputValue(), '新会话失败前草稿'); await dialog.getByRole('button', { name: '取消', exact: true }).click()
  assert.equal(await button('开始新对话').isDisabled(), true); await button('核实并重试上次操作').click()
  await button('核实并重试上次操作').waitFor({ state: 'hidden' })
  await messages.getByText('当前对话 · 可以开始新的设计需求', { exact: true }).waitFor()
  assert.deepEqual(keys, [keys[0], keys[0]]); assert.equal(await input.inputValue(), ''); assert.equal(await messages.getByText(long, { exact: true }).count(), 1)
  await input.fill('  新会话正文\n'); await button('发送').click(); await button('停止').waitFor(); assert.equal(sent.text, '  新会话正文\n'); assert.deepEqual(sent.attachmentIds, []); assert.equal(sent.skillId, null)
  append('new-message', '停止前收到的公开文字', 'message', 'running', 'new'); await messages.getByText('停止前收到的公开文字', { exact: true }).waitFor()
  await button('停止').click(); await button('发送').waitFor(); assert.equal(await messages.getByText('停止前收到的公开文字', { exact: true }).count(), 1)
  await mkdir('../../output/playwright/studio-native', { recursive: true })
  await page.screenshot({ path: '../../output/playwright/studio-native/desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 }); await button('展开工作台').click(); await button('收起').click()
  await messages.evaluate(el => { el.scrollTop = el.scrollHeight }); await page.waitForTimeout(100)
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
  for (const name of ['开始新对话', '刷新', '发送']) assert.ok(await button(name).evaluate(el => { const r = el.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth && r.top >= 0 && r.bottom <= innerHeight }))
  await button('开始新对话').click(); await dialog.waitFor(); await page.waitForTimeout(250)
  assert.ok(await dialog.evaluate(el => { const r = el.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth && r.bottom <= innerHeight }))
  await page.screenshot({ path: '../../output/playwright/studio-native/mobile-confirm.png', fullPage: true })
  assert.deepEqual(unexpected, []); assert.deepEqual(errors, [])
  console.log('PASS: incremental pages/updates, full messages/long text, safe Markdown and delivery images, failure/cancel/reload, scroll follow/history, draft selection persistence, idempotent new conversation, 390px')
} finally { await context.close(); await browser.close() }
