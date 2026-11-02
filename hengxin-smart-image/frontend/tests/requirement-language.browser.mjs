// Formal components; isolated browser context and mocked local APIs; no production writes or AI calls.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3046'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const output = '../../output/playwright/requirement-language'
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } }), page = await context.newPage()
page.setDefaultTimeout(15000)
const errors = [], unexpected = [], creates = [], resubmits = []
page.on('pageerror', e => errors.push(e.message))
const caps = ['task.read', 'task.create', 'task.requirements.resubmit']
const task = { id: 't', name: '语言测试任务', productName: '落地灯', brand: 'OUTON', platform: 'Amazon', language: 'en', market: '美国历史站点', remarks: '', skus: [{ code: 'A' }], workflow: 'studio', status: 'pending_review', version: 1, createdAt: '2026-11-02', updatedAt: '2026-11-02', createdBy: { id: 'd', name: '提交设计' }, designer: { id: 'other', name: '负责设计', status: 'active', eligible: true }, capabilities: caps, events: [], requirementsReviews: [] }
const material = { id: 'm', kind: 'competitor', name: '图需.csv', sizeBytes: 12, contentType: 'text/csv', taskId: null, createdAt: '2026-11-02', status: 'ready' }
const picture = { id: 'p', name: '成品.png', sku: 'A', width: 1, height: 1, contentType: 'image/png', sizeBytes: 68, url: '/api/overseas/v1/archives/a/pictures/p/content' }
const archive = { id: 'a', taskId: null, sourceDeleted: true, taskName: '独立快照任务名称', productName: '快照品名', language: 'fr', brand: 'OUTON', platform: 'Amazon', skus: [{ code: 'A' }], pictureCount: 1, createdAt: '2026-11-02', pictures: [picture], cover: picture }
const button = name => page.getByRole('button', { name, exact: true })
const field = label => page.locator('.el-form-item').filter({ has: page.locator('.el-form-item__label').getByText(label, { exact: true }) })
async function choose(label, value) { await field(label).locator('.el-select').click(); await page.getByRole('option', { name: value, exact: true }).click() }
async function unclipped(locator) {
  await locator.scrollIntoViewIfNeeded()
  assert.ok(await locator.evaluate(el => {
    const b = el.getBoundingClientRect()
    if (!b.width || !b.height) return false
    for (let p = el.parentElement; p; p = p.parentElement) {
      const r = p.getBoundingClientRect(), s = getComputedStyle(p)
      if (/(auto|scroll|hidden|clip)/.test(s.overflowX) && (b.left < r.left - 1 || b.right > r.right + 1)) return false
      if (/(auto|scroll|hidden|clip)/.test(s.overflowY) && (b.top < r.top - 1 || b.bottom > r.bottom + 1)) return false
    }
    return true
  }), await locator.textContent())
}
try {
  await context.route('**/*', async route => {
    const req = route.request(), u = new URL(req.url()), p = u.pathname
    if (['api.iconify.design', 'api.unisvg.com', 'api.simplesvg.com'].includes(u.hostname)) return route.fulfill({ json: {} })
    if (u.origin !== base) { unexpected.push(u.href); return route.abort() }
    if (!p.startsWith('/api/')) return route.continue()
    let body = {}, status = 200
    if (p.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (p === '/api/identity/v1/me') body = { name: '提交设计', sessionId: 'identity-test' }
    else if (p.endsWith('/tickets')) body = { ticket: 'test' }
    else if (p === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
    else if (p.includes('/auth/')) { body = { id: 'd', name: '提交设计', identitySessionId: 'identity-test', status: 'active', roles: ['designer'], capabilities: caps }; if (p.endsWith('/access')) body = { state: 'allowed', member: body } }
    else if (p.endsWith('/task-designers')) body = { items: [{ id: 'other', name: '负责设计', department: '' }], total: 1, page: 1, pageSize: 20 }
    else if (p.endsWith('/resubmit')) { const input = req.postDataJSON(); resubmits.push(input); Object.assign(task, input, { status: 'pending_review', version: task.version + 1 }); body = task }
    else if (p.endsWith('/tasks/t/studio/transcript')) body = { items: [], cursor: 0, hasMore: false }
    else if (p.endsWith('/tasks/t/studio')) body = { taskId: 't', taskVersion: task.version, archiveId: null, completed: false, reopened: false, conversationId: null, conversations: [], maxConversations: 10, activeConversationCount: 0, turns: [], materials: [], skills: [], activeTurnId: null }
    else if (p.endsWith('/tasks/t/materials')) body = [{ ...material, taskId: 't' }]
    else if (p.endsWith('/materials')) body = material
    else if (p.endsWith('/tasks/t')) body = task
    else if (p.endsWith('/tasks') && req.method() === 'POST') { const input = req.postDataJSON(); creates.push(input); Object.assign(task, input, { status: 'pending_review' }); body = task }
    else if (p.endsWith('/archives/a/pictures/p/content')) return route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+cWZkAAAAASUVORK5CYII=', 'base64') })
    else if (p.endsWith('/archives/a')) body = archive
    else if (p.endsWith('/archives')) body = { items: [archive], total: 1, page: 1, pageSize: 20 }
    else { unexpected.push(p); status = 404 }
    await route.fulfill({ status, json: body })
  })
  const languages = [['en','英语'],['de','德语'],['fr','法语'],['es','西班牙语']]
  for (const [code, label] of languages) {
    await page.goto(`${base}/#/overseas/create`); await page.reload(); await field('语言').waitFor()
    assert.ok((await field('目标平台').textContent()).includes('请选择目标平台'))
    assert.ok((await field('语言').textContent()).includes('请选择语言'))
    await page.getByRole('textbox', { name: 'SKU 1 编码', exact: true }).fill('A')
    await field('任务名称').locator('input').fill(`语言测试${label}`); await field('品名').locator('input').fill('落地灯')
    await choose('品牌', 'OUTON'); await choose('负责设计', '负责设计')
    await page.locator('[data-material-kind="competitor"] input[type=file]').setInputFiles({ name: '图需.csv', mimeType: 'text/csv', buffer: Buffer.from('sku,feature') })
    await button('提交图需').click(); await page.getByText('请填写必填信息并指定设计', { exact: true }).waitFor(); assert.equal(creates.length, languages.findIndex(l => l[0] === code))
    await choose('目标平台', '亚马逊/Amazon')
    await button('提交图需').click(); await page.getByText('请选择语言（英语、德语、法语或西班牙语）', { exact: true }).waitFor()
    await field('语言').locator('.el-select').click()
    await page.getByRole('option', { name: '英语', exact: true }).waitFor()
    assert.deepEqual(await page.locator('.el-select-dropdown').filter({ has: page.getByRole('option', { name: '英语', exact: true }) }).locator('.el-select-dropdown__item').allTextContents(), languages.map(l => l[1]))
    await page.getByRole('option', { name: label, exact: true }).click(); await page.getByRole('option', { name: label, exact: true }).waitFor({ state: 'hidden' })
    if (code === 'en') { await unclipped(field('语言')); await page.screenshot({ path: `${output}/create-desktop.png`, fullPage: true }) }
    await button('提交图需').click(); await page.getByRole('heading', { name: '审核结论', exact: true }).waitFor()
    assert.equal(creates.at(-1).language, code); assert.equal(creates.at(-1).platform, 'Amazon')
    assert.ok((await page.locator('.facts').textContent()).includes(`语言${label}`))
    task.status = 'returned'; await page.reload(); await button('修改图需并重新提交').click(); await field('语言').waitFor()
    assert.ok((await field('语言').textContent()).includes(label)); assert.ok((await field('目标平台').textContent()).includes('亚马逊/Amazon'))
    await button('重新提交设计审核').click(); await page.getByRole('heading', { name: '审核结论', exact: true }).waitFor(); assert.equal(resubmits.at(-1).language, code)
  }
  for (const language of [null, undefined]) {
    task.status = 'returned'; task.language = language; task.platform = 'TikTok Shop'; task.market = '美国历史站点'
    await page.reload(); await page.getByRole('heading', { name: '审核结论', exact: true }).waitFor()
    assert.ok((await page.locator('.facts').textContent()).includes('语言未设置'))
    await button('修改图需并重新提交').click(); assert.ok((await field('语言').textContent()).includes('请选择语言')); assert.ok((await field('目标平台').textContent()).includes('TikTok Shop'))
    const before = resubmits.length
    await button('重新提交设计审核').click(); await page.getByText('请选择语言（英语、德语、法语或西班牙语）', { exact: true }).waitFor(); assert.equal(resubmits.length, before)
    await page.setViewportSize({ width: 390, height: 844 }); await page.locator('.menu-left-close').waitFor({ state: 'attached' })
    for (const label of ['目标平台','语言']) await unclipped(field(label))
    await unclipped(page.getByRole('alert').last()); await unclipped(button('重新提交设计审核'))
    assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
    await choose('语言', '德语'); await page.screenshot({ path: `${output}/resubmit-390.png`, fullPage: true })
    await button('重新提交设计审核').click(); await page.getByRole('heading', { name: '审核结论', exact: true }).waitFor()
    assert.equal(resubmits.at(-1).language, 'de'); assert.equal(resubmits.at(-1).platform, 'TikTok Shop'); assert.equal(resubmits.at(-1).market, '美国历史站点')
  }
  for (const width of [1366, 390]) {
    await page.setViewportSize({ width, height: 900 }); await page.goto(`${base}/#/overseas/archive`); await page.reload()
    await button('查看成品').click(); const dialog = page.getByRole('dialog', { name: '归档成品', exact: true })
    await dialog.locator('.archive-fields').waitFor()
    assert.deepEqual(await dialog.locator('.archive-fields dt').allTextContents(), ['SKU','目标平台','品牌','任务名称','品名','语言'])
    assert.deepEqual(await dialog.locator('.archive-fields dd').allTextContents(), ['A','Amazon','OUTON','独立快照任务名称','快照品名','法语'])
    for (const row of await dialog.locator('.archive-fields > div').all()) await unclipped(row)
    await unclipped(dialog.getByRole('button', { name: '关闭', exact: true })); await dialog.locator('.archive-fields').screenshot({ path: `${output}/archive-${width}.png` })
    archive.taskName = null; archive.language = null; await button('刷新成品详情').click(); await dialog.getByText('未设置', { exact: true }).first().waitFor()
    assert.equal(await dialog.getByText('未设置', { exact: true }).count(), 2); assert.equal(await dialog.getByText('原任务已删除', { exact: true }).count(), 1)
    await dialog.getByRole('button', { name: '关闭', exact: true }).click(); archive.taskName = '独立快照任务名称'; archive.language = 'fr'
  }
  task.status = 'studio'; task.language = 'es'; await page.goto(`${base}/#/overseas/tasks/t`); await page.reload()
  await page.getByText('语言：西班牙语', { exact: false }).waitFor(); await unclipped(page.locator('.studio-task-meta')); await page.screenshot({ path: `${output}/studio-language-390.png` })
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, [])
  console.log('PASS empty platform/language required; four languages create/resubmit/details; null/absent legacy requires selection; historical platform retained; archive six independent snapshot fields and unknowns; 1366/390 visible clipping checks')
} catch (error) { await page.screenshot({ path: `${output}/failure.png`, fullPage: true }); console.error({ errors, unexpected, text: await page.locator('body').innerText() }); throw error }
finally { await browser.close() }
