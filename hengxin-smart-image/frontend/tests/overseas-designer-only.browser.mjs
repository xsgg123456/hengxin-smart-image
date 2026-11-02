// Formal Vue/Element components with controlled local API responses. No production data or AI calls.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3044'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const output = '../../output/playwright/designer-only'
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } }), page = await context.newPage()
page.setDefaultTimeout(15000)
const errors = [], unexpected = [], creates = [], resubmits = [], reviews = []
page.on('pageerror', e => errors.push(e.message))
let role = 'designer', canReview = false, failCreate = true, failResubmit = true
const memberCaps = () => ['task.read', 'task.create', 'task.design', ...(role === 'super_admin' ? ['members.manage'] : [])]
const taskCaps = () => ['task.read', 'task.requirements.resubmit', ...(canReview ? ['task.requirements.review'] : [])]
const task = { id: 't', name: '审核流程验收', productName: '落地灯', brand: 'OUTON', platform: 'Amazon', language: 'en', market: '历史站点', remarks: '历史补充说明不展示也不回传', skus: [{ code: 'A' }], workflow: 'studio', status: 'pending_review', version: 1, createdAt: '2026-11-02', updatedAt: '2026-11-02', createdBy: { id: 'd', name: '提交设计' }, designer: { id: 'other', name: '负责设计', status: 'active', eligible: true }, capabilities: taskCaps(), events: [], requirementsReviews: [] }
const material = { id: 'm', kind: 'competitor', name: '图需.csv', sizeBytes: 12, contentType: 'text/csv', taskId: null, createdAt: '2026-11-02', status: 'ready' }
const button = name => page.getByRole('button', { name, exact: true })
const field = label => page.locator('.el-form-item').filter({ has: page.locator('.el-form-item__label').getByText(label, { exact: true }) })
const labels = ['SKU 1', '目标平台', '品牌', '任务名称', '品名', '语言', '负责设计']
async function checkForm() {
  await page.getByRole('textbox', { name: 'SKU 1 编码', exact: true }).waitFor()
  assert.deepEqual(await page.locator('.hx-create-grid .el-form-item__label').allTextContents(), labels)
  assert.equal(await page.getByText('补充说明', { exact: false }).count(), 0)
  assert.equal(await page.getByText('目标站点', { exact: true }).count(), 0)
}
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
  }))
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
    else if (p.includes('/auth/')) { body = { id: 'd', name: '提交设计', identitySessionId: 'identity-test', status: 'active', roles: [role], capabilities: memberCaps() }; if (p.endsWith('/access')) body = { state: 'allowed', member: body } }
    else if (p.endsWith('/task-designers')) body = { items: [{ id: 'other', name: '负责设计', department: '' }], total: 1, page: 1, pageSize: 20 }
    else if (p.endsWith('/requirements-review')) {
      const input = req.postDataJSON(); reviews.push(input)
      task.status = 'returned'; task.version++
      task.requirementsReviews.push({ id: 'r', decision: input.decision, comment: input.comment, actorId: 'other', actorName: '负责设计', version: task.version, createdAt: '2026-11-02' })
      body = { ...task, capabilities: taskCaps() }
    } else if (p.endsWith('/resubmit')) {
      const input = req.postDataJSON(); resubmits.push({ input, key: req.headers()['idempotency-key'] })
      if (failResubmit) return route.abort()
      Object.assign(task, input, { status: 'pending_review', version: task.version + 1 }); body = { ...task, capabilities: taskCaps() }
    } else if (p.endsWith('/tasks/t/materials')) body = [{ ...material, taskId: 't' }]
    else if (p.endsWith('/materials')) body = material
    else if (p.endsWith('/tasks/t')) body = { ...task, capabilities: taskCaps() }
    else if (p.endsWith('/tasks') && req.method() === 'POST') {
      const input = req.postDataJSON(); creates.push({ input, key: req.headers()['idempotency-key'] })
      if (failCreate) return route.abort()
      Object.assign(task, input); body = { ...task, capabilities: taskCaps() }
    } else { unexpected.push(p); status = 404 }
    await route.fulfill({ status, json: body })
  })
  // Each supported identity reaches the actual create page with the server's create capability.
  for (role of ['designer', 'design_manager', 'super_admin']) {
    await page.goto(`${base}/#/overseas/create`); await page.reload(); await checkForm()
    assert.equal(await page.getByRole('textbox', { name: 'SKU 1 编码', exact: true }).isEnabled(), true)
  }
  role = 'designer'; await page.reload(); await checkForm()
  assert.deepEqual(await page.locator('.hx-summary .el-step__title').allTextContents(), ['提交图需', '图需审核', 'AI 设计工作台', '归档成品库'])
  await page.getByRole('textbox', { name: 'SKU 1 编码', exact: true }).fill('A')
  await button('添加 SKU').click(); await page.getByRole('textbox', { name: 'SKU 2 编码', exact: true }).fill('B')
  await page.locator('.sku-row').nth(1).getByRole('button', { name: '移除', exact: true }).click(); await checkForm()
  await button('添加 SKU').click(); await page.getByRole('textbox', { name: 'SKU 2 编码', exact: true }).fill('B')
  await field('目标平台').locator('.el-select').click(); await page.getByRole('option', { name: '亚马逊/Amazon', exact: true }).click()
  await field('语言').locator('.el-select').click(); await page.getByRole('option', { name: '英语', exact: true }).click()
  await field('品牌').locator('.el-select').click(); await page.getByRole('option', { name: 'OUTON', exact: true }).click()
  await field('任务名称').locator('input').fill('设计人员提交验收'); await field('品名').locator('input').fill('落地灯')
  await field('负责设计').locator('.el-select').click(); await page.getByRole('option', { name: '负责设计', exact: true }).click()
  await page.locator('[data-material-kind="competitor"] input[type=file]').setInputFiles({ name: '图需.csv', mimeType: 'text/csv', buffer: Buffer.from('sku,feature') })
  await button('提交图需').click(); await page.getByText('服务连接失败，请稍后重试', { exact: true }).waitFor()
  assert.equal(await field('任务名称').locator('input').inputValue(), '设计人员提交验收')
  await unclipped(page.getByRole('alert').last()); await page.screenshot({ path: `${output}/create-error.png` })
  await page.getByRole('heading', { name: '基本信息', exact: false }).scrollIntoViewIfNeeded(); await page.screenshot({ path: `${output}/create-fields.png` })
  failCreate = false; await button('提交图需').click(); await page.getByRole('heading', { name: '审核结论', exact: true }).waitFor()
  assert.equal(creates.length, 2); assert.equal(creates[0].key, creates[1].key)
  assert.deepEqual(creates[1].input.skus, [{ code: 'A' }, { code: 'B' }]); assert.equal(creates[1].input.designerId, 'other')
  assert.equal(Object.hasOwn(creates[1].input, 'remarks'), false); assert.equal(creates[1].input.market, '')
  assert.equal(await button('退回提交人修改').count(), 0, '创建人只有读取权限时不显示审核操作')
  assert.equal(await page.getByText('历史补充说明', { exact: false }).count(), 0)
  canReview = true; await button('刷新任务详情').click(); await button('退回提交人修改').click()
  await page.getByText('请填写退回原因，便于提交人修改。', { exact: true }).waitFor(); assert.equal(reviews.length, 0)
  await page.getByRole('textbox', { name: '图需审核意见', exact: true }).fill('补充尺寸资料')
  await button('退回提交人修改').click(); await page.getByRole('dialog').getByRole('button', { name: '取消', exact: true }).click(); assert.equal(reviews.length, 0)
  await button('退回提交人修改').click(); await page.getByRole('dialog').getByRole('button', { name: '确认', exact: true }).click()
  await page.getByText('已退回提交人，修改完成后需重新提交设计审核。', { exact: true }).waitFor(); assert.equal(reviews.length, 1)
  await page.screenshot({ path: `${output}/returned.png`, fullPage: true })
  await button('修改图需并重新提交').click()
  await page.locator('.sku-row').nth(1).getByRole('button', { name: '移除', exact: true }).click(); await checkForm()
  await field('任务名称').locator('input').fill('退回后修改')
  await button('重新提交设计审核').click(); await page.getByText('服务连接失败，请稍后重试', { exact: true }).waitFor()
  assert.equal(await field('任务名称').locator('input').inputValue(), '退回后修改')
  for (const viewport of [{ width: 1366, height: 900 }]) {
    await page.setViewportSize(viewport); await unclipped(button('重新提交设计审核')); await unclipped(field('任务名称'))
    await page.screenshot({ path: `${output}/resubmit-${viewport.width}.png`, fullPage: true })
  }
  failResubmit = false; await button('重新提交设计审核').click(); await page.getByRole('heading', { name: '审核结论', exact: true }).waitFor()
  assert.equal(resubmits.length, 2); assert.equal(resubmits[0].key, resubmits[1].key)
  assert.equal(Object.hasOwn(resubmits[1].input, 'remarks'), false); assert.equal(task.remarks, '历史补充说明不展示也不回传')
  assert.equal(resubmits[1].input.name, '退回后修改'); assert.deepEqual(resubmits[1].input.materialIds, ['m'])
  task.status = 'returned'; await page.setViewportSize({ width: 390, height: 844 }); await page.reload()
  await button('修改图需并重新提交').click(); await checkForm(); await page.locator('.menu-left-close').waitFor({ state: 'attached' })
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
  await page.getByRole('heading', { name: '基本信息', exact: false }).scrollIntoViewIfNeeded()
  await page.screenshot({ path: `${output}/resubmit-390.png` })
  await unclipped(button('重新提交设计审核')); await page.screenshot({ path: `${output}/resubmit-390-submit.png` })
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, [])
  console.log('PASS three role create access; ordered fields; SKU add/remove; no site/remarks; designer selection; failed create retry; read-only reviewer capability; reject required/cancel/confirm; resubmit retry and preserved historic remarks; desktop/mobile clipping')
} catch (error) {
  await page.screenshot({ path: `${output}/failure.png`, fullPage: true }); console.error({ errors, unexpected, text: await page.locator('body').innerText() }); throw error
} finally { await browser.close() }

