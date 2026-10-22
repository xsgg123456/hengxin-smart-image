// Disposable context, intercepted APIs and loopback-only frontend. No production writes.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3037'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } }), page = await context.newPage()
page.setDefaultTimeout(20000)
const errors = [], unexpected = [], caps = ['task.read', 'task.design'], removed = [], sends = []
page.on('pageerror', e => errors.push(e.message))
const asset = id => ({ id: `upload:${id}`, name: `${id}.txt`, contentType: 'text/plain', sizeBytes: 10, source: 'upload', url: `/api/overseas/v1/tasks/t/studio/files/${id}/content` })
let materials = ['a', 'b', 'c'].map(asset), conversationId = 'c1', failRemove = true, failSend = true, completed = false
const task = { id: 't', name: '海外草稿与批量移除验收', productName: '灯具', brand: 'HX', platform: 'Amazon', market: '美国', remarks: '', skus: [{ code: 'A' }], workflow: 'studio', status: 'studio', version: 1, createdAt: '2026-10-22', updatedAt: '2026-10-22', createdBy: { id: 'u', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: caps, events: [] }
const state = () => ({ taskId: 't', taskVersion: 1, archiveId: null, completed, reopened: false, conversationId, turns: [], materials, skills: [{ id: 's', name: 'skill', displayName: '测试Skill', description: '草稿恢复验收' }], activeTurnId: null })
const button = name => page.getByRole('button', { name, exact: true })
const input = page.getByRole('textbox', { name: '设计要求', exact: true })
async function ready() { await page.getByText('与 Codex 协作', { exact: true }).waitFor(); await input.waitFor(); await page.waitForFunction(() => !document.querySelector('[aria-label="设计要求"]').disabled) }
async function insidePanel(locator) {
  assert.ok(await locator.evaluate(el => {
    const r = el.getBoundingClientRect(); let node = el.parentElement
    if (r.width <= 0 || r.height <= 0 || r.left < 0 || r.right > innerWidth || r.top < 0 || r.bottom > innerHeight) return false
    while (node) { const s = getComputedStyle(node), p = node.getBoundingClientRect(); if (/(auto|scroll|hidden|clip)/.test(s.overflowY) && (r.top < p.top - 1 || r.bottom > p.bottom + 1)) return false; node = node.parentElement }
    return true
  }))
}
try {
  await context.route('**/*', async route => {
    const url = new URL(route.request().url()), path = url.pathname
    if (['api.iconify.design', 'api.unisvg.com', 'api.simplesvg.com'].includes(url.hostname)) return route.fulfill({ contentType: 'application/json', body: '{}' })
    if (url.origin !== base && !['data:', 'blob:'].includes(url.protocol)) { unexpected.push(url.href); return route.abort() }
    if (!path.startsWith('/api/')) return route.continue()
    let body = {}, status = 200
    if (path.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (path === '/api/identity/v1/me') body = { name: '设计', sessionId: 'identity-test' }
    else if (path.endsWith('/tickets')) body = { ticket: 'test' }
    else if (path === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
    else if (path.includes('/auth/')) { body = { id: 'd', name: '设计', identitySessionId: 'identity-test', status: 'active', roles: ['designer'], capabilities: caps }; if (path.endsWith('/access')) body = { state: 'allowed', member: body } }
    else if (path.endsWith('/studio/transcript')) body = { items: [], cursor: 0, hasMore: false }
    else if (path.includes('/studio/materials/')) {
      const id = decodeURIComponent(path.split('/').at(-1)); removed.push(id)
      if (id === 'upload:b' && failRemove) { status = 503; body = { detail: '暂时失败' } }
      else { materials = materials.filter(a => a.id !== id); body = state() }
    } else if (path.endsWith('/studio/files')) { materials.push(asset('uploaded')); body = { ...asset('uploaded'), materialState: 'added' } }
    else if (path.endsWith('/studio/turns')) { sends.push(route.request().postDataJSON()); body = state(); if (failSend) { status = 409; body = { detail: '测试冲突，草稿保留' } } }
    else if (path.endsWith('/studio/conversations')) { conversationId = 'c2'; body = state() }
    else if (path.endsWith('/studio')) body = state()
    else if (path.endsWith('/tasks/t')) body = task
    else if (path.endsWith('/materials')) body = []
    else if (path.endsWith('/jobs')) body = { items: [] }
    else if (path.endsWith('/execution-events')) body = { items: [], cursor: 0 }
    else if (path.endsWith('/plans') || path.endsWith('/pictures')) body = { items: [], taskVersion: 1 }
    else { unexpected.push(path); return route.abort() }
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await mkdir('../../output/playwright/studio-draft-materials', { recursive: true })
  await page.goto(`${base}/#/overseas/tasks/t`); await ready()
  assert.equal(await button('移除所选素材（0）').isDisabled(), true)
  await page.locator('[data-material-id="upload:a"] .el-checkbox').click()
  await button('引用所选素材（1）').click(); await input.fill('刷新后保留的设计意见')
  await page.getByRole('combobox', { name: '选择 Skill', exact: true }).click(); await page.getByRole('option').filter({ hasText: '测试Skill' }).click()
  await page.locator('.studio-composer input[type=file]').setInputFiles({ name: 'uploaded.txt', mimeType: 'text/plain', buffer: Buffer.from('test') })
  await button('移除 uploaded.txt').waitFor(); await page.reload(); await ready()
  assert.equal(await input.inputValue(), '刷新后保留的设计意见'); assert.equal(await button('移除 a.txt').count(), 1); assert.equal(await button('移除 uploaded.txt').count(), 1); assert.equal(await button('查看 Skill 说明').count(), 1)
  await page.locator('.studio-materials > .el-checkbox').click()
  await button('移除所选素材（4）').click(); await page.getByRole('button', { name: '取消', exact: true }).click(); await page.locator('.el-message-box').waitFor({ state: 'hidden' }); assert.deepEqual(removed, [])
  await insidePanel(button('移除所选素材（4）')); await insidePanel(button('引用所选素材（4）'))
  await page.screenshot({ path: '../../output/playwright/studio-draft-materials/desktop-selected.png', fullPage: true, animations: 'disabled' })
  await button('移除所选素材（4）').click(); await page.locator('.el-message-box').waitFor({ state: 'visible' })
  await page.waitForFunction(() => { const el = document.querySelector('.el-overlay-message-box'); return el && getComputedStyle(el).opacity === '1' && !document.querySelector('.fade-in-linear-enter-active') })
  await page.screenshot({ path: '../../output/playwright/studio-draft-materials/confirmation.png', fullPage: true, animations: 'disabled' }); await button('确认移除').click()
  await page.getByText('已移除 3 项，1 项未完成，请检查后重试', { exact: true }).waitFor()
  assert.equal(await page.getByRole('checkbox', { name: '选择 b.txt', exact: true }).isChecked(), true)
  assert.equal(await button('移除所选素材（1）').isEnabled(), true); assert.equal(await button('移除 a.txt').count(), 1)
  failRemove = false; await button('移除所选素材（1）').click(); await button('确认移除').click(); await page.getByText('暂无任务素材', { exact: true }).waitFor()
  await page.reload(); await ready(); assert.equal(await button('移除 a.txt').count(), 1); assert.equal(await button('移除 uploaded.txt').count(), 1); await page.getByText('暂无任务素材', { exact: true }).waitFor()
  await button('发送').click(); await page.getByText('测试冲突，草稿保留', { exact: true }).waitFor(); await page.reload(); await ready()
  assert.equal(await input.inputValue(), '刷新后保留的设计意见')
  failSend = false; await button('发送').click(); await page.waitForFunction(() => document.querySelector('[aria-label="设计要求"]').value === '')
  assert.deepEqual(sends.at(-1).attachmentIds, ['upload:a', 'upload:uploaded']); assert.equal(sends.at(-1).skillId, 's')
  await page.reload(); await ready(); assert.equal(await input.inputValue(), ''); assert.equal(await button('移除 a.txt').count(), 0)
  await input.fill('新对话应清空'); await button('开始新对话').click(); await button('确认开始新对话').click(); await page.waitForFunction(() => document.querySelector('[aria-label="设计要求"]').value === '')
  await page.reload(); await ready(); assert.equal(await input.inputValue(), '')
  await page.setViewportSize({ width: 390, height: 844 }); await button('展开工作台').click()
  await insidePanel(button('移除所选素材（0）')); await insidePanel(button('引用所选素材（0）')); await insidePanel(page.getByText('暂无任务素材', { exact: true }))
  await page.screenshot({ path: '../../output/playwright/studio-draft-materials/mobile-empty.png', fullPage: true, animations: 'disabled' })
  materials = Array.from({ length: 12 }, (_, i) => asset(`material-${i}`)); await button('刷新').click(); await page.getByRole('checkbox', { name: '选择 material-11.txt', exact: true }).waitFor({ state: 'attached' })
  await page.locator('.studio-materials > .el-checkbox').click()
  await page.waitForFunction(() => document.querySelectorAll('.studio-source-file input[type=checkbox]:checked').length === 12)
  await insidePanel(button('移除所选素材（12）')); await insidePanel(button('引用所选素材（12）'))
  await page.screenshot({ path: '../../output/playwright/studio-draft-materials/mobile-selected.png', fullPage: true, animations: 'disabled' })
  completed = true; await button('刷新').click(); await page.getByText('与 Codex 协作 · 已完成', { exact: true }).waitFor(); assert.equal(await button('移除所选素材（12）').isDisabled(), true)
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, [])
  console.log('PASS: upload/reload, draft text/Skill/attachments, hidden material recovery, selection/cancel/all/partial failure/retry, send failure/success, new conversation, readonly, desktop/mobile clipping checks')
} finally { await context.close(); await browser.close() }
