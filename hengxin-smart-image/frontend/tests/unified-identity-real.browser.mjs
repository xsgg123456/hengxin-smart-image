// 只用于隔离 Phase17 测试服务；provider 替身 code 由测试数据库授予的角色决定。
// 不拦截 /api，不向正式前端传入 role/access 参数。
import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://localhost:3013'
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname), '仅允许本地隔离环境')
const browser = await chromium.launch({ headless: true })
const results = []
try {
  for (const code of ['both', 'domestic', 'overseas', 'neither']) {
    const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
    try {
      const login = await context.request.post(`${base}/api/identity/v1/dingtalk/container`, {
        headers: { 'X-HX-Request': '1', Origin: base }, data: { code },
      })
      assert.equal(login.status(), 200, `隔离provider登录 ${code}`)
      const page = await context.newPage(), errors = [], requests = []
      page.on('pageerror', error => errors.push(error.message))
      page.on('request', request => requests.push(new URL(request.url()).pathname))
      await page.goto(`${base}/#/auth/business`)
      const domestic = page.getByRole('button', { name: /^国内业务/ })
      const overseas = page.getByRole('button', { name: /^海外业务/ })
      await page.getByRole('status').filter({ hasText: '正在验证' }).waitFor({ state: 'hidden' })
      await domestic.waitFor()
      await page.getByText('正在验证企业身份与业务权限…', { exact: true }).waitFor({ state: 'hidden' })
      assert.equal(await domestic.isEnabled(), ['both', 'domestic'].includes(code), await page.locator('body').innerText())
      assert.equal(await overseas.isEnabled(), ['both', 'overseas'].includes(code))
      assert.equal(requests.includes('/api/v1/auth/me'), false, '统一入口不得bootstrap国内业务')
      assert.equal(requests.some(path => path.includes('/workspace')), false)
      if (['both', 'overseas'].includes(code)) {
        await overseas.click()
        await page.getByRole('heading', { name: '海外业务', exact: true }).waitFor()
        await page.reload()
        await page.getByRole('heading', { name: '海外业务', exact: true }).waitFor()
        assert.equal(await page.getByText('提交图需', { exact: true }).count(), 0, '正式入口不挂模拟任务')
        await page.getByRole('button', { name: '切换业务', exact: true }).click()
        await overseas.waitFor()
      }
      await page.getByRole('button', { name: '退出登录', exact: true }).click()
      await page.getByRole('button', { name: '钉钉登录', exact: true }).waitFor()
      for (const path of ['/api/identity/v1/me', '/api/v1/auth/me', '/api/overseas/v1/auth/me']) {
        assert.equal((await context.request.get(`${base}${path}`)).status(), 401, `退出应撤销${path}`)
      }
      assert.deepEqual(errors, [])
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
      results.push(`${code}: 双入口、独立启动、真实会话与退出 PASS`)
    } finally { await context.close() }
  }
  console.log(JSON.stringify(results, null, 2))
} finally { await browser.close() }
