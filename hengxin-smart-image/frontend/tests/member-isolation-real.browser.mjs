// 仅运行 --members 本地隔离环境；竞态case只延迟真实/me回执，不伪造API数据。
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3013'
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname), '仅允许本地隔离环境')
const browser = await chromium.launch({ headless: true }), contexts = [], results = []
const output = '../../output/playwright/member-isolation'
await mkdir(output, { recursive: true })
const headers = { 'X-HX-Request': '1', Origin: base }
async function login(code) {
  const context = await browser.newContext({ viewport: { width: 1366, height: 900 } }); contexts.push(context)
  const response = await context.request.post(`${base}/api/identity/v1/dingtalk/container`, { headers, data: { code } })
  assert.equal(response.status(), 200, await response.text())
  const identity = await response.json(), page = await context.newPage(), writes = [], errors = []
  page.on('pageerror', e => errors.push(e.message))
  page.on('request', r => { if (r.method() === 'POST') writes.push(new URL(r.url()).pathname) })
  await page.goto(`${base}/#/auth/business`)
  await ready(page)
  assert.equal(writes.some(p => /\/identity\/(session|application)/.test(p)), false, '选择页加载不得建会话或申请')
  return { context, page, writes, errors, name: identity.name }
}
async function ready(page) {
  await page.getByRole('button', { name: /^国内业务/ }).waitFor()
  await page.getByText('正在验证企业身份与业务权限…', { exact: true }).waitFor({ state: 'hidden' })
}
async function confirm(page, name) { const dialog = page.getByRole('dialog').filter({ hasText: name }).last(); await dialog.getByRole('button', { name: '确认', exact: true }).click() }
async function unclipped(locator) {
  await locator.scrollIntoViewIfNeeded()
  const failures = await locator.evaluate(el => {
    const box = el.getBoundingClientRect(), failures = []
    if (box.width <= 0 || box.height <= 0 || box.left < 0 || box.right > innerWidth || box.top < 0 || box.bottom > innerHeight) failures.push('viewport')
    for (let parent = el.parentElement; parent; parent = parent.parentElement) {
      const rect = parent.getBoundingClientRect(), css = getComputedStyle(parent)
      if (/(auto|scroll|hidden|clip)/.test(css.overflowX) && (box.left < rect.left - 1 || box.right > rect.right + 1)) failures.push(`${parent.className}:x`)
      if (/(auto|scroll|hidden|clip)/.test(css.overflowY) && (box.top < rect.top - 1 || box.bottom > rect.bottom + 1)) failures.push(`${parent.className}:y`)
    }
    return failures
  })
  assert.deepEqual(failures, [], '关键控件在所有裁切祖先内完整可见')
}
async function apply(person, label, again = false) {
  if (await person.page.getByRole('button', { name: `撤回${label}申请`, exact: true }).count()) {
    await person.page.getByRole('button', { name: `撤回${label}申请`, exact: true }).click()
    await person.page.getByRole('button', { name: '确认撤回', exact: true }).click(); await ready(person.page)
  }
  await person.page.getByRole('button', { name: `${again ? '重新申请' : '申请'}${label}权限`, exact: true }).click()
  await person.page.getByRole('button', { name: '确认申请', exact: true }).click()
  await person.page.getByRole('button', { name: `撤回${label}申请`, exact: true }).waitFor()
  await ready(person.page)
}
async function adminPage(person, business, label) {
  await person.page.getByRole('button', { name: `${label}业务`, exact: true }).click()
  if (business === 'domestic') await person.page.waitForURL(/workspace=domestic/)
  else await person.page.waitForURL(/overseas\/tasks/)
  await person.page.goto(`${base}/${business === 'domestic' ? '?workspace=domestic' : ''}#/${business === 'domestic' ? 'management' : 'overseas/admin'}/users`)
  await person.page.getByRole('heading', { name: `${label}成员目录`, exact: true }).waitFor()
}
async function decide(admin, applicant, label, decision) {
  await admin.page.getByRole('tab', { name: '加入申请', exact: true }).click()
  await admin.page.getByRole('button', { name: '刷新申请', exact: true }).click()
  const row = admin.page.getByRole('row').filter({ hasText: applicant.name })
  await row.getByRole('button', { name: '审批申请', exact: true }).click()
  const dialog = admin.page.getByRole('dialog', { name: `审批${label}业务加入申请`, exact: true })
  await dialog.getByRole('button', { name: '确认审批', exact: true }).click()
  await dialog.getByText('请选择本业务的有效角色', { exact: true }).waitFor()
  if (decision === 'approve') {
    await dialog.getByRole('combobox', { name: '审批业务角色' }).press('Enter')
    await admin.page.getByRole('option', { name: '设计', exact: true }).or(admin.page.getByRole('option', { name: '设计人员', exact: true })).click()
  } else {
    await dialog.getByText('拒绝', { exact: true }).click()
    await dialog.getByRole('button', { name: '确认审批', exact: true }).click()
    await dialog.getByText('请填写拒绝原因', { exact: true }).waitFor()
    await dialog.getByRole('textbox', { name: '拒绝原因' }).fill('请确认工作业务后重新申请')
  }
  await dialog.getByRole('button', { name: '确认审批', exact: true }).click()
  await confirm(admin.page, '确认审批')
  await dialog.waitFor({ state: 'hidden' })
}
try {
  for (const business of (process.env.MEMBER_TEST_BUSINESS ? [process.env.MEMBER_TEST_BUSINESS] : ['overseas', 'domestic'])) {
    const label = business === 'domestic' ? '国内' : '海外', prefix = business === 'domestic' ? '/api/v1/management/users' : '/api/overseas/v1/members'
    const admin = await login(`mi-${business}-admin`), applicant = await login(process.env.MEMBER_APPLICANT_CODE || 'mi-ui-applicant'), rejected = await login('mi-ui-rejected')
    await adminPage(admin, business, label)
    const before = await (await admin.context.request.get(`${base}${prefix}?page=1&pageSize=100&directory=members`)).json()
    await apply(applicant, label)
    await applicant.page.getByRole('button', { name: `撤回${label}申请`, exact: true }).click()
    await applicant.page.getByRole('button', { name: '确认撤回', exact: true }).click()
    await applicant.page.getByRole('button', { name: `申请${label}权限`, exact: true }).waitFor(); await ready(applicant.page)
    await apply(applicant, label)
    const still = await (await admin.context.request.get(`${base}${prefix}?page=1&pageSize=100&directory=members`)).json()
    assert.equal(still.total, before.total, '申请不计正式成员')
    await decide(admin, applicant, label, 'approve')
    await applicant.page.reload(); await ready(applicant.page)
    assert.equal(await applicant.page.getByRole('button', { name: `${label}业务`, exact: true }).isEnabled(), true)
    const after = await (await admin.context.request.get(`${base}${prefix}?page=1&pageSize=100&directory=members`)).json()
    assert.equal(after.total, before.total + 1)
    await admin.page.getByRole('tab', { name: '成员', exact: true }).click()
    await admin.page.getByRole('row').filter({ hasText: applicant.name }).waitFor()
    await admin.page.getByText(`共 ${after.total} 位成员`, { exact: true }).waitFor()
    await admin.page.getByRole('tab', { name: '历史待核对', exact: true }).click()
    await admin.page.getByText('历史来源尚未确认，仅供核对；需本人明确申请并审批，普通编辑不能授权。', { exact: true }).waitFor()
    assert.equal(await admin.page.getByRole('button', { name: /^(编辑|分配角色 \/ 状态)$/ }).count(), 0)
    await apply(rejected, label); await decide(admin, rejected, label, 'reject')
    await rejected.page.reload(); await ready(rejected.page)
    await rejected.page.getByText('拒绝原因：请确认工作业务后重新申请', { exact: true }).waitFor()
    await apply(rejected, label, true)
    await admin.page.getByRole('button', { name: '刷新申请', exact: true }).click()
    await admin.page.getByRole('row').filter({ hasText: rejected.name }).waitFor()
    await admin.page.screenshot({ path: `${output}/${business}-applications.png`, fullPage: true })
    await admin.page.setViewportSize({ width: 390, height: 844 })
    await admin.page.reload()
    await admin.page.getByRole('heading', { name: `${label}成员目录`, exact: true }).waitFor()
    await admin.page.getByRole('tab', { name: '加入申请', exact: true }).click()
    await admin.page.getByRole('button', { name: '刷新申请', exact: true }).scrollIntoViewIfNeeded()
    await admin.page.locator('.menu-left-close').waitFor({ state: 'attached' })
    assert.ok(await admin.page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), '窄屏无整页横向溢出')
    await unclipped(admin.page.getByRole('button', { name: '刷新申请', exact: true }))
    const mobileApprove = admin.page.getByRole('row').filter({ hasText: rejected.name }).getByRole('button', { name: '审批申请', exact: true })
    await unclipped(mobileApprove); await mobileApprove.click()
    const mobileDialog = admin.page.getByRole('dialog', { name: `审批${label}业务加入申请`, exact: true })
    await unclipped(mobileDialog.getByRole('button', { name: '确认审批', exact: true }))
    await mobileDialog.getByRole('button', { name: '确认审批', exact: true }).click()
    await unclipped(mobileDialog.getByText('请选择本业务的有效角色', { exact: true }))
    await admin.page.screenshot({ path: `${output}/${business}-approval-mobile.png`, fullPage: true })
    await mobileDialog.getByRole('button', { name: '取消', exact: true }).click()
    await mobileDialog.waitFor({ state: 'hidden' })
    await admin.page.locator('.el-table .el-scrollbar__wrap').first().evaluate(el => { el.scrollLeft = 0 })
    await unclipped(admin.page.getByRole('heading', { name: `${label}成员目录`, exact: true }))
    await admin.page.screenshot({ path: `${output}/${business}-mobile.png`, fullPage: true, animations: 'disabled' })
    await rejected.page.setViewportSize({ width: 390, height: 844 })
    await rejected.page.getByRole('button', { name: `撤回${label}申请`, exact: true }).scrollIntoViewIfNeeded()
    await unclipped(rejected.page.getByRole('button', { name: `撤回${label}申请`, exact: true }))
    const rect = await rejected.page.getByRole('button', { name: `撤回${label}申请`, exact: true }).boundingBox()
    assert.ok(rect && rect.x >= 0 && rect.x + rect.width <= 390, '申请动作完整可见')
    await rejected.page.screenshot({ path: `${output}/${business}-entry-mobile.png`, fullPage: true })
    for (const person of [admin, applicant, rejected]) assert.deepEqual(person.errors, [])
    assert.equal(admin.writes.filter(p => p.endsWith('/auth/identity/session')).length, 1, '仅进入选定业务建立一个会话')
    results.push(`${label}：只读选择、明确申请撤回、角色审批、拒绝重申、独立计数、待核对只读、390px PASS`)
  }
  if (!process.env.MEMBER_TEST_BUSINESS) {
    const person = await login('mi-ui-applicant')
    await person.page.getByRole('button', { name: '海外业务', exact: true }).click()
    await person.page.locator('.hx-page').first().waitFor()
    const before = person.writes.filter(p => p.endsWith('/auth/identity/session')).length
    const changed = await person.context.request.post(`${base}/api/identity/v1/dingtalk/container`, { headers, data: { code: 'mi-ui-same-name' } })
    assert.equal(changed.status(), 200)
    assert.equal((await changed.json()).name, person.name, '必须用两个实际同名身份验证')
    await person.page.evaluate(() => window.dispatchEvent(new Event('focus')))
    await person.page.locator('.hx-page').first().waitFor({ state: 'hidden' })
    await person.page.reload(); await ready(person.page)
    assert.equal(await person.page.getByRole('button', { name: /^海外业务/ }).isEnabled(), false)
    assert.equal(await person.page.getByRole('button', { name: /^国内业务/ }).isEnabled(), false)
    assert.equal(person.writes.filter(p => p.endsWith('/auth/identity/session')).length, before, '同名换号不得续接旧会话或自动创建新会话')
    assert.deepEqual(person.errors, [])
    results.push('同名换号：实际不同provider身份、旧业务页清除、双边仍未加入、恢复无会话兑换 PASS')
    const race = await login('mi-ui-same-name')
    let swapped = false
    await race.page.route(`${base}/api/identity/v1/me`, async route => {
      if (swapped) { await route.continue(); return }
      const response = await route.fetch()
      assert.equal(response.status(), 200)
      const changed = await race.context.request.post(`${base}/api/identity/v1/dingtalk/container`, { headers, data: { code: 'mi-ui-rejected' } })
      assert.equal(changed.status(), 200); swapped = true
      await route.fulfill({ response })
    })
    const deniedTicket = race.page.waitForResponse(response => response.url().endsWith('/api/identity/v1/tickets') && response.status() === 401)
    await race.page.getByRole('button', { name: '申请海外权限', exact: true }).click()
    await race.page.getByRole('button', { name: '确认申请', exact: true }).click()
    await deniedTicket
    await race.page.getByRole('button', { name: '钉钉登录', exact: true }).waitFor()
    assert.equal(race.writes.some(p => p.includes('/auth/identity/application')), false, '确认后换号不能向新身份提交申请')
    assert.equal(race.writes.some(p => p.endsWith('/auth/identity/session')), false)
    assert.deepEqual(race.errors, [])
    results.push('申请确认后/me与票据之间换号：真实票据401，业务申请与会话HTTP零调用 PASS')
  }
  console.log(JSON.stringify(results, null, 2))
} catch (error) {
  console.log(JSON.stringify(results, null, 2))
  for (const [i, context] of contexts.entries()) for (const page of context.pages()) await page.screenshot({ path: `${output}/failure-${i}.png`, fullPage: true }).catch(() => {})
  throw error
} finally { for (const context of contexts) await context.close(); await browser.close() }
