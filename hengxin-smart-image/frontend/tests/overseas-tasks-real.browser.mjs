// API与数据库真实，仅外部钉钉provider使用隔离harness替身。
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3015', headers = { 'X-HX-Request': '1', Origin: base }
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless: true }), sessions = {}, errors = []
const roles = ['operator', 'operator_manager', 'designer', 'design_manager', 'admin', 'dual', 'operator2', 'designer2']
let restored
async function api(context, method, path, data, key) { const response = await context.request[method](`${base}/api/overseas/v1${path}`, { headers: { ...headers, ...(key ? { 'Idempotency-Key': key } : {}) }, data }); return response }
const button = (page, name) => page.getByRole('button', { name, exact: true })
async function choose(page, name) { await page.locator('input[aria-label="负责设计"]:not([disabled])').waitFor(); await page.locator('.el-select').filter({ has: page.getByRole('combobox', { name: '负责设计', exact: true }) }).click(); await page.getByRole('option', { name, exact: false }).click() }
try {
  for (const role of roles) {
    const context = await browser.newContext({ viewport: { width: 1366, height: 900 } })
    const auth = await context.request.post(`${base}/api/identity/v1/dingtalk/container`, { headers, data: { code: `${role.endsWith('2') ? 'p19' : 'p18'}-${role}` } }); assert.equal(auth.status(), 200)
    const page = await context.newPage(); page.on('pageerror', e => errors.push(e.message)); await page.goto(`${base}/#/overseas`); await page.locator('.hx-page').filter({ hasText: /工作流任务|暂无此功能权限/ }).first().waitFor()
    const member = await (await api(context, 'get', '/auth/me')).json(); sessions[role] = { context, page, member }
    assert.equal(await page.getByRole('menuitem', { name: '提交图需', exact: true }).count(), member.capabilities.includes('task.create') ? 1 : 0)
    assert.equal(await page.getByRole('menuitem', { name: '工作流任务', exact: true }).count(), 1)
    assert.equal(await page.getByRole('menuitem', { name: '管理中心', exact: true }).count(), member.capabilities.includes('stats.read') ? 1 : 0)
    await page.goto(`${base}/#/overseas/create`)
    await (member.capabilities.includes('task.create') ? button(page, '提交图需') : page.getByText('暂无此功能权限')).waitFor()
  }
  const { page: creator, context: operator } = sessions.operator, name = `浏览器真实图需-${Date.now()}`
  const input = label => creator.locator('.el-form-item').filter({ has: creator.locator('.el-form-item__label', { hasText: label }) }).locator('input')
  await input('任务名称').fill(name); await input('品名').fill('手机壳'); await input('品牌').fill('HX'); await input('目标站点').fill('美国')
  await creator.getByRole('textbox', { name: 'SKU 1 编码', exact: true }).fill('BROWSER-A'); await button(creator, '添加 SKU').click(); await creator.getByRole('textbox', { name: 'SKU 2 编码', exact: true }).fill('BROWSER-B')
  await creator.getByRole('textbox', { name: '搜索负责设计' }).fill('p18-designer'); await creator.waitForTimeout(400); await choose(creator, '测试成员-p18-designer')
  assert.equal(await button(creator, '提交图需').isDisabled(), true)
  await creator.locator('[data-material-kind="competitor"] input[type=file]').setInputFiles({ name: '竞品.csv', mimeType: 'text/csv', buffer: Buffer.from('product,feature\ncase,clear') }); await creator.getByText(/竞品.csv · 解析成功/).waitFor()
  await button(creator, '提交图需').click(); await creator.getByRole('heading', { name: '任务信息', exact: true }).waitFor(); const id = creator.url().split('/').pop()
  await creator.reload(); await creator.getByText('BROWSER-B', { exact: true }).waitFor(); assert.equal(await button(creator, '改派设计').count(), 0)
  const created = await (await api(operator, 'get', `/tasks/${id}`)).json(); assert.equal(created.skus.length, 2); assert.equal(created.designer.id, sessions.designer.member.id)
  for (const role of roles) {
    const { page, context } = sessions[role]; await page.goto(`${base}/#/overseas/tasks/${id}`)
    const canRead = ['operator', 'operator_manager', 'designer', 'design_manager', 'admin'].includes(role)
    if (canRead) { await page.getByRole('heading', { name: '任务信息', exact: true }).waitFor(); assert.equal(await button(page, '改派设计').count(), ['design_manager', 'admin'].includes(role) ? 1 : 0) }
    else { await page.locator('.hx-page').filter({ hasText: /工作流任务|暂无此功能权限/ }).first().waitFor(); assert.equal(await page.getByText(name, { exact: true }).count(), 0) }
    const response = await api(context, 'get', `/tasks/${id}`); assert.equal(response.status(), canRead ? 200 : 403)
    const list = await (await api(context, 'get', `/tasks?search=${encodeURIComponent(name)}`)).json(); assert.equal(list.total, canRead ? 1 : 0)
  }
  const { page: manager, context: managerContext } = sessions.design_manager
  await button(manager, '改派设计').click(); await manager.getByRole('textbox', { name: '搜索负责设计' }).fill('p19-designer2'); await manager.waitForTimeout(400); await choose(manager, '测试成员-p19-designer2')
  await button(manager, '确认改派').click(); await manager.getByText('负责设计：测试成员-p19-designer2', { exact: false }).waitFor()
  const changed = await (await api(managerContext, 'get', `/tasks/${id}`)).json(); assert.equal(changed.version, 2); assert.equal(changed.events.length, 2)
  const oldPage = sessions.designer.page; await button(oldPage, '刷新任务详情').click(); await oldPage.locator('.hx-page').filter({ hasText: /工作流任务|暂无此功能权限/ }).first().waitFor(); assert.equal(await oldPage.getByText(name, { exact: true }).count(), 0)
  const newPage = sessions.designer2.page; await newPage.goto(`${base}/#/overseas/tasks/${id}`); await newPage.getByRole('heading', { name: '任务信息', exact: true }).waitFor()
  // 兼任运营与设计仍以服务端能力/范围为准。
  const admin = sessions.admin.context, dualId = sessions.dual.member.id
  const member = await (await api(admin, 'get', `/members/${dualId}`)).json(); restored = member
  assert.equal((await api(admin, 'patch', `/members/${dualId}`, { roles: ['operator', 'designer'], status: 'active', version: member.version })).status(), 200)
  const dualPage = sessions.dual.page; await dualPage.goto(`${base}/#/overseas/create`); await button(dualPage, '提交图需').waitFor(); const dual = await (await api(sessions.dual.context, 'get', '/auth/me')).json(); assert.ok(dual.capabilities.includes('task.create') && dual.capabilities.includes('task.design'))
  await mkdir('../../output/playwright/phase19', { recursive: true }); await manager.screenshot({ path: '../../output/playwright/phase19/task-real.png', fullPage: true })
  await manager.setViewportSize({ width: 390, height: 844 }); await button(manager, '改派设计').scrollIntoViewIfNeeded(); await manager.waitForTimeout(400); const overflow = await manager.evaluate(() => [...document.querySelectorAll('body *')].map(el => ({ tag: el.tagName, cls: el.className, right: el.getBoundingClientRect().right, width: el.getBoundingClientRect().width })).filter(x => x.right > innerWidth + 1 && x.width > 0)); assert.ok(await manager.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), JSON.stringify(overflow)); await manager.screenshot({ path: '../../output/playwright/phase19/task-real-mobile.png', fullPage: true })
  assert.deepEqual(errors, []); console.log('PASS real HTTP/DB browser: five roles+dual menus/direct links; multi-SKU create/reload; list scope; manager reassignment/audit; old designer immediate denied; new designer readable; 1366/390 screenshots')
} finally {
  if (restored) { const admin = sessions.admin.context, current = await (await api(admin, 'get', `/members/${restored.id}`)).json(); await api(admin, 'patch', `/members/${restored.id}`, { roles: restored.roles, status: restored.status, version: current.version }) }
  await browser.close()
}
