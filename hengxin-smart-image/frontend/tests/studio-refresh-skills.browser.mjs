// Isolated browser context and intercepted APIs; no real task or model requests.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3018'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } }), page = await context.newPage()
page.setDefaultTimeout(20000)
const errors = [], caps = ['task.read', 'task.design']
page.on('pageerror', error => errors.push(error.message))
const description = '完整描述：按商品资料设计主图，保留细节、检查文字与布局。'.repeat(12) + ' 描述末尾验收'
const material = { id: 'task:m', name: '需求.pdf', contentType: 'application/pdf', sizeBytes: 10, url: '/api/overseas/v1/materials/m/content', source: 'task' }
const task = { id: 't', name: '工作台刷新验收', productName: '手机', brand: 'HX', platform: 'Amazon', market: '美国', remarks: '', skus: [{ code: 'A' }], workflow: 'studio', status: 'studio', version: 1, createdAt: '2026-10-14', updatedAt: '2026-10-14', createdBy: { id: 'u', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: caps, events: [] }
let reads = 0, active = false, completed = false, fail = false, delay = 0
const turns = Array.from({ length: 12 }, (_, i) => ({ id: `r${i}`, text: `历史需求 ${i}`, skillName: null, status: 'succeeded', reply: `历史回复 ${i}`, error: null, jobId: `j${i}`, jobVersion: 1, attachments: [], pictures: [], referencePictures: [], createdAt: '2026-10-14' }))
const state = () => ({ taskId: 't', completed, turns, materials: [material], skills: [{ id: 'skill', name: 'example', displayName: '完整中文 Skill 标题', description }], activeTurnId: active ? 'r11' : null })
const button = name => page.getByRole('button', { name, exact: true })
try {
  await context.route(`${base}/api/**`, async route => {
    const path = new URL(route.request().url()).pathname
    let body = {}, status = 200
    if (path.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (path === '/api/identity/v1/me') body = { name: '设计', sessionId: 'identity-test' }
    else if (path.endsWith('/tickets')) body = { ticket: 'test' }
    else if (path === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
    else if (path.includes('/auth/')) { body = { id: 'd', name: '设计', identitySessionId: 'identity-test', status: 'active', roles: ['designer'], capabilities: caps }; if (path.endsWith('/access')) body = { state: 'allowed', member: body } }
    else if (path.endsWith('/studio/transcript')) body = { items: [], cursor: 0, hasMore: false }
    else if (path.endsWith('/studio/events')) body = { items: [], cursor: 0 }
    else if (path.endsWith('/studio')) { reads++; if (delay) await new Promise(done => setTimeout(done, delay)); body = state(); if (fail) { status = 503; body = { detail: '读取临时失败' } } }
    else if (path.endsWith('/tasks/t')) body = task
    else if (path.endsWith('/materials')) body = []
    else if (path.endsWith('/jobs')) body = { items: [] }
    else if (path.endsWith('/execution-events')) body = { items: [], cursor: 0 }
    else if (path.endsWith('/plans') || path.endsWith('/pictures')) body = { items: [], taskVersion: 1 }
    else throw Error(`Unexpected API ${path}`)
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.goto(`${base}/#/overseas/tasks/t`)
  await page.getByText('与 Codex 协作', { exact: true }).waitFor()
  const input = page.getByRole('textbox', { name: '设计要求', exact: true }), refresh = button('刷新')
  await input.fill('刷新后保留这份草稿')
  await page.locator('.studio-materials .el-checkbox').filter({ hasText: '全选素材' }).click(); await button('引用所选素材（1）').click()
  await page.getByRole('combobox', { name: '选择 Skill', exact: true }).click()
  const option = page.getByRole('option').filter({ hasText: '完整中文 Skill 标题' })
  assert.ok((await option.innerText()).includes(description)); await option.click()
  await button('查看 Skill 说明').click(); assert.equal(await page.locator('.studio-skill-description').innerText(), description)
  await page.getByRole('dialog').locator('.el-dialog__headerbtn').click()
  await page.locator('.studio-messages').evaluate(el => { el.scrollTop = 180 })
  const scroll = await page.locator('.studio-messages').evaluate(el => el.scrollTop), first = reads
  await page.waitForTimeout(3000); assert.equal(reads, first); assert.equal(await refresh.evaluate(el => el.classList.contains('is-loading')), false)
  active = true; delay = 300; await refresh.click(); assert.equal(await refresh.evaluate(el => el.classList.contains('is-loading')), true)
  await page.waitForFunction(() => !document.querySelector('.studio-actions .is-loading'))
  const before = reads; await page.waitForTimeout(2900); assert.ok(reads > before)
  assert.equal(await refresh.evaluate(el => el.classList.contains('is-loading')), false)
  assert.equal(await input.inputValue(), '刷新后保留这份草稿'); assert.equal(await button('移除 需求.pdf').count(), 1)
  assert.equal(await page.locator('.studio-messages').evaluate(el => el.scrollTop), scroll)
  assert.equal(await button('查看 Skill 说明').count(), 1)
  await mkdir('../../output/playwright/studio', { recursive: true })
  await page.screenshot({ path: '../../output/playwright/studio/refresh-desktop.png', fullPage: true })
  fail = true; await refresh.click(); await page.locator('.studio-chat-card .el-alert--error').waitFor()
  fail = false; await refresh.click(); await page.locator('.studio-chat-card .el-alert--error').waitFor({ state: 'hidden' })
  active = false; completed = true; await refresh.click(); await page.getByText('与 Codex 协作 · 已完成', { exact: true }).waitFor()
  const end = reads; await page.waitForTimeout(3000); assert.equal(reads, end)
  completed = false; await refresh.click(); await input.waitFor({ state: 'visible' })
  await page.setViewportSize({ width: 390, height: 844 }); await button('展开工作台').click(); await button('收起').click()
  await page.getByRole('combobox', { name: '选择 Skill', exact: true }).click()
  await option.waitFor(); assert.ok((await option.innerText()).includes(description))
  assert.ok(await option.evaluate(el => { const r = el.getBoundingClientRect(); return r.left >= 0 && r.right <= innerWidth }))
  await page.waitForTimeout(300); assert.ok(await option.evaluate(el => el.clientHeight >= el.querySelector('p').offsetHeight)); await page.screenshot({ path: '../../output/playwright/studio/skill-mobile.png', fullPage: true })
  assert.ok(await option.evaluate(el => { const wrap = el.closest('.el-select-dropdown__wrap'); wrap.scrollTop = wrap.scrollHeight; const row = el.getBoundingClientRect(), box = wrap.getBoundingClientRect(); return row.bottom <= box.bottom + 1 }))
  await option.click(); await button('查看 Skill 说明').click()
  assert.equal(await page.locator('.studio-skill-description').innerText(), description)
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
  await page.screenshot({ path: '../../output/playwright/studio/skill-description-mobile.png', fullPage: true })
  assert.deepEqual(errors, [])
  console.log('PASS: idle/active/completed polling, manual spinner, silent auto refresh, error recovery, draft/attachment/skill/scroll persistence; full descriptions desktop/mobile')
} finally { await context.close(); await browser.close() }
