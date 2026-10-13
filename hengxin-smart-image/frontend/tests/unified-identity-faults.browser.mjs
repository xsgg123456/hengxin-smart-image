import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3014'
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
let unavailable = true, logoutFailure = true, authenticated = true
const calls = [], errors = []
try {
  await context.route(`${base}/api/**`, async route => {
    const path = new URL(route.request().url()).pathname
    calls.push(path)
    let status = 200, value = {}
    if (path === '/api/identity/v1/config') value = { configured: true, corpId: 'test', clientId: 'test' }
    else if (path === '/api/identity/v1/me') { status = authenticated ? 200 : 401; value = { name: '测试成员', sessionId: 'identity-test' } }
    else if (path.endsWith('/tickets')) value = { ticket: 'one-use-ticket' }
    else if (path === '/api/v1/auth/identity/access') value = { state: 'unregistered' }
    else if (path === '/api/overseas/v1/auth/identity/access' || path === '/api/overseas/v1/auth/identity/session' || path === '/api/overseas/v1/auth/me') {
      status = unavailable ? 503 : 200; value = { id: 'test', name: '测试成员', status: 'active', identitySessionId: 'identity-test', roles: ['designer'], capabilities: ['task.read', 'task.design', 'stats.read'] }
      if (path.endsWith('/access')) value = { state: 'allowed', member: value }
    } else if (path === '/api/overseas/v1/tasks') value = { items: [], total: 0, page: 1, pageSize: 20 }
    else if (path === '/api/identity/v1/logout') { status = logoutFailure ? 503 : 204; if (!logoutFailure) authenticated = false }
    else if (path.endsWith('/logout')) status = 204
    else throw new Error(`不应调用 ${path}`)
    await route.fulfill({ status, contentType: 'application/json', body: status === 204 ? '' : JSON.stringify(value) })
  })
  const page = await context.newPage()
  page.on('pageerror', error => errors.push(error.message))
  await page.goto(`${base}/#/auth/business`)
  const domestic = page.getByRole('button', { name: '国内业务 · 尚未加入', exact: true })
  await domestic.waitFor(); assert.equal(await domestic.isEnabled(), false)
  const failure = page.getByRole('button', { name: '海外业务 · 连接失败，请重试', exact: true })
  await failure.waitFor(); assert.equal(await failure.isEnabled(), false)
  unavailable = false
  await page.getByRole('button', { name: '重新连接', exact: true }).click()
  const overseas = page.getByRole('button', { name: '海外业务', exact: true })
  await overseas.waitFor(); await overseas.click()
  await page.locator('.hx-page').filter({ hasText: /工作流任务|暂无此功能权限/ }).first().waitFor()
  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await page.getByRole('alert').filter({ hasText: '服务暂不可用' }).waitFor()
  assert.equal(calls.includes('/api/v1/auth/logout'), false, '统一退出失败不得提前清业务')
  logoutFailure = false
  await page.getByRole('button', { name: '退出登录', exact: true }).click()
  await page.getByRole('button', { name: '钉钉登录', exact: true }).waitFor()
  assert.equal(calls.includes('/api/v1/auth/me'), false)
  assert.deepEqual(errors, [])
  console.log('PASS：503可重试、403禁用、海外身份页、统一退出故障重试、国内bootstrap隔离')
} finally { await context.close(); await browser.close() }
