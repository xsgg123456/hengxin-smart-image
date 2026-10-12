import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3015'
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
const page = await context.newPage(), errors = [], calls = [], queries = []
page.setDefaultTimeout(15000)
page.on('pageerror', error => errors.push(error.message))
let capabilities = ['members.manage'], mode = 'normal', patches = 0
let member = { id: 'target', name: '海外测试成员', department: '海外设计部', roles: ['designer'], status: 'active', version: 1, createdAt: '2026-10-12', updatedAt: '2026-10-12' }
let delay = false, release
async function unclipped(locator) {
  await locator.scrollIntoViewIfNeeded()
  const result = await locator.evaluate(el => {
    const box = el.getBoundingClientRect(), failures = []
    for (let parent = el.parentElement; parent; parent = parent.parentElement) {
      const rect = parent.getBoundingClientRect(), css = getComputedStyle(parent)
      if (/(auto|scroll|hidden|clip)/.test(css.overflowX) && (box.left < rect.left - 1 || box.right > rect.right + 1)) failures.push(`${parent.className}:x`)
      if (/(auto|scroll|hidden|clip)/.test(css.overflowY) && (box.top < rect.top - 1 || box.bottom > rect.bottom + 1)) failures.push(`${parent.className}:y`)
    }
    return { width: box.width, height: box.height, failures }
  })
  assert.ok(result.width > 0 && result.height > 0); assert.deepEqual(result.failures, [])
}
try {
  await context.route(`${base}/api/**`, async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname
    calls.push(path)
    let status = 200, body = {}
    if (path.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (path === '/api/identity/v1/me') body = { name: '测试管理员' }
    else if (path.endsWith('/tickets')) body = { ticket: 'test-ticket' }
    else if (path === '/api/v1/auth/identity/session') status = 403
    else if (path.includes('/auth/')) body = { id: 'actor', name: '测试管理员', status: 'active', roles: ['super_admin'], capabilities }
    else if (path === '/api/overseas/v1/members') {
      queries.push(Object.fromEntries(url.searchParams))
      if (delay) await new Promise(resolve => { release = resolve })
      if (mode === 'network') { await route.abort(); return }
      status = mode === '401' ? 401 : mode === '403' ? 403 : 200
      body = { items: url.searchParams.get('search') === '不存在' ? [] : [member], total: 41, page: Number(url.searchParams.get('page')), pageSize: Number(url.searchParams.get('pageSize')) }
    } else if (path === '/api/overseas/v1/members/target') {
      if (request.method() === 'PATCH') {
        patches++
        if (mode === 'conflict') { status = 409; body = { detail: { code: 'version_conflict' } }; member.version++ }
        else { const value = request.postDataJSON(); assert.deepEqual(Object.keys(value).sort(), ['roles', 'status', 'version']); member = { ...member, ...value, version: member.version + 1 }; body = member }
      } else body = member
    } else throw Error(`Unexpected ${path}`)
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.goto(`${base}/#/overseas/admin/users`)
  await page.getByText('海外测试成员', { exact: true }).waitFor()
  assert.equal(await page.locator('.hx-admin-table-card').evaluate(el => getComputedStyle(el).borderRadius), '16px')
  await Promise.all([page.waitForResponse(r => new URL(r.url()).searchParams.get('page') === '2'), page.locator('.el-pager').getByText('2', { exact: true }).click()])
  await page.getByText('海外测试成员', { exact: true }).waitFor()
  assert.equal(queries.at(-1).page, '2')
  await page.getByRole('combobox', { name: '成员状态筛选', exact: true }).press('Enter')
  await Promise.all([page.waitForResponse(r => new URL(r.url()).searchParams.get('status') === 'active'), page.getByRole('option', { name: '启用', exact: true }).click()])
  await page.getByText('海外测试成员', { exact: true }).waitFor()
  assert.equal(queries.at(-1).status, 'active'); assert.equal(queries.at(-1).page, '1')
  await page.getByRole('combobox', { name: '成员角色筛选', exact: true }).press('Enter')
  await Promise.all([page.waitForResponse(r => new URL(r.url()).searchParams.get('role') === 'designer'), page.getByRole('option', { name: '设计', exact: true }).click()])
  await page.getByText('海外测试成员', { exact: true }).waitFor()
  assert.equal(queries.at(-1).role, 'designer')
  delay = true
  await page.getByRole('button', { name: '刷新成员', exact: true }).click()
  await page.locator('.el-loading-mask').first().waitFor()
  await unclipped(page.locator('.el-loading-mask').first())
  assert.equal(await page.getByText('海外测试成员', { exact: true }).count(), 0)
  await page.waitForFunction(() => !!document.querySelector('.el-loading-mask'))
  while (!release) await new Promise(resolve => setTimeout(resolve, 10))
  delay = false; release(); release = undefined
  await page.getByText('海外测试成员', { exact: true }).waitFor()
  assert.equal(await page.getByRole('button', { name: '新增成员', exact: true }).count(), 0)
  assert.equal(await page.getByRole('radiogroup', { name: '体验角色' }).count(), 0)
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '编辑海外成员', exact: true })
  assert.equal(await dialog.getByRole('textbox', { name: '成员姓名' }).getAttribute('readonly'), '')
  await dialog.getByRole('combobox', { name: '海外业务角色', exact: true }).press('Enter')
  const roleList = await dialog.getByRole('combobox', { name: '海外业务角色', exact: true }).getAttribute('aria-controls')
  await page.locator(`#${roleList}`).getByRole('option', { name: '运营主管', exact: true }).click()
  await page.keyboard.press('Escape')
  await page.getByRole('button', { name: '保存成员', exact: true }).click()
  await dialog.waitFor({ state: 'hidden' }); assert.deepEqual(member.roles, ['designer', 'operator_manager'])
  mode = 'conflict'
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  await page.getByRole('button', { name: '保存成员', exact: true }).click()
  await page.getByRole('button', { name: '刷新最新资料', exact: true }).waitFor()
  assert.equal(await page.getByRole('button', { name: '保存成员', exact: true }).isEnabled(), false)
  mode = 'normal'
  await page.getByRole('button', { name: '刷新最新资料', exact: true }).click()
  await dialog.locator('.el-switch').click()
  await page.getByRole('button', { name: '保存成员', exact: true }).click()
  const before = patches
  await page.getByRole('button', { name: '确认禁用', exact: true }).waitFor(); assert.equal(patches, before)
  await page.getByRole('button', { name: '确认禁用', exact: true }).click()
  await dialog.waitFor({ state: 'hidden' }); assert.equal(member.status, 'disabled')
  await page.getByRole('textbox', { name: '搜索成员' }).fill('不存在'); await page.getByRole('textbox', { name: '搜索成员' }).press('Enter'); await page.getByRole('textbox', { name: '搜索成员' }).blur()
  await page.getByText('暂无符合条件的海外成员', { exact: true }).waitFor()
  await unclipped(page.getByText('暂无符合条件的海外成员', { exact: true }))
  await page.getByRole('textbox', { name: '搜索成员' }).fill(''); await page.getByRole('textbox', { name: '搜索成员' }).blur()
  await page.getByText('海外测试成员', { exact: true }).waitFor()
  await page.setViewportSize({ width: 390, height: 844 })
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
  await page.setViewportSize({ width: 1280, height: 900 })
  mode = 'network'
  await page.getByRole('button', { name: '刷新成员', exact: true }).click()
  await page.getByRole('button', { name: '重新连接', exact: true }).waitFor()
  await unclipped(page.getByRole('alert').first())
  assert.equal(await page.getByText('海外测试成员', { exact: true }).count(), 0)
  assert.equal(await page.getByRole('menuitem', { name: '管理中心', exact: true }).count(), 0)
  mode = 'normal'; await page.getByRole('button', { name: '重新连接', exact: true }).click()
  await page.getByText('海外测试成员', { exact: true }).waitFor()
  for (const failure of ['403', '401']) {
    mode = failure
    await page.getByRole('button', { name: '刷新成员', exact: true }).click()
    await page.getByRole('button', { name: '重新连接', exact: true }).waitFor()
    assert.equal(await page.getByText('海外测试成员', { exact: true }).count(), 0)
    mode = 'normal'; await page.getByRole('button', { name: '重新连接', exact: true }).click()
    await page.getByText('海外测试成员', { exact: true }).waitFor()
  }
  capabilities = []
  await page.getByRole('button', { name: '编辑', exact: true }).click()
  await page.getByRole('heading', { name: '海外业务', exact: true }).waitFor()
  assert.equal(await page.getByRole('menuitem', { name: '管理中心', exact: true }).count(), 0)
  assert.equal(calls.some(p => p.startsWith('/api/v1/') && !p.endsWith('/auth/identity/session')), false)
  assert.deepEqual(errors, [])
  console.log('PASS：多角色/只读身份/冲突刷新/禁用确认/空态/窄屏/断网恢复/401/403/撤权与国内隔离')
} catch (error) { console.error(await page.locator('body').innerText()); throw error }
finally { release?.(); await context.close(); await browser.close() }
