// 仅本地隔离harness；真实身份/海外/国内HTTP，外部钉钉provider替身。
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3015'
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless: true }), results = []
const headers = { 'X-HX-Request': '1', Origin: base }
try {
  for (const role of ['operator', 'operator_manager', 'designer', 'design_manager', 'admin', 'dual']) {
    const context = await browser.newContext({ viewport: { width: 1366, height: 900 } })
    try {
      const response = await context.request.post(`${base}/api/identity/v1/dingtalk/container`, { headers, data: { code: `p18-${role}` } })
      assert.equal(response.status(), 200)
      const page = await context.newPage(), errors = [], paths = []
      page.on('pageerror', error => errors.push(error.message))
      page.on('request', req => paths.push(new URL(req.url()).pathname))
      await page.goto(`${base}/#/overseas`)
      await page.getByRole('heading', { name: '海外业务', exact: true }).waitFor()
      assert.equal(await page.getByRole('menuitem', { name: '管理中心', exact: true }).count(), role === 'admin' ? 1 : 0)
      assert.equal(await page.getByRole('radiogroup', { name: '体验角色' }).count(), 0)
      assert.equal(await page.getByRole('menuitem', { name: '提交图需', exact: true }).count(), 0)
      await page.goto(`${base}/#/overseas/admin/users`)
      if (role === 'admin') {
        await page.getByRole('heading', { name: '海外成员目录' }).waitFor()
        await page.getByRole('button', { name: '编辑', exact: true }).first().waitFor()
        const list = await context.request.get(`${base}/api/overseas/v1/members?page=1&pageSize=100`)
        assert.equal(list.status(), 200)
        const { items } = await list.json()
        const target = items.find(m => m.roles.length === 1 && m.roles[0] === 'designer')
        assert.ok(target)
        const row = page.getByRole('row').filter({ hasText: target.name })
        await row.getByRole('button', { name: '编辑', exact: true }).click()
        const dialog = page.getByRole('dialog', { name: '编辑海外成员', exact: true })
        assert.equal(await dialog.getByRole('textbox', { name: '成员姓名' }).inputValue(), target.name)
        await dialog.getByRole('combobox', { name: '海外业务角色' }).press('Enter')
        await page.getByRole('option', { name: '运营', exact: true }).click(); await page.keyboard.press('Escape')
        await dialog.getByRole('button', { name: '保存成员', exact: true }).click()
        await dialog.waitFor({ state: 'hidden' })
        const changed = await (await context.request.get(`${base}/api/overseas/v1/members/${target.id}`)).json()
        assert.deepEqual([...changed.roles].sort(), ['designer', 'operator'])
        const audit = await (await context.request.get(`${base}/api/overseas/v1/members/${target.id}/audit`)).json()
        assert.ok(audit.items.length > 0)
        const restore = await context.request.patch(`${base}/api/overseas/v1/members/${target.id}`, { headers, data: { roles: target.roles, status: target.status, version: changed.version } })
        assert.equal(restore.status(), 200)
        await page.reload(); await page.getByRole('button', { name: '编辑', exact: true }).first().waitFor()
        await mkdir('../../output/playwright/phase18', { recursive: true })
        await page.screenshot({ path: '../../output/playwright/phase18/members-real.png', fullPage: true })
        await page.setViewportSize({ width: 390, height: 844 })
        await page.locator('.menu-left-close').waitFor()
        await page.getByRole('button', { name: '刷新成员', exact: true }).hover()
        assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
        const scroll = page.locator('.el-table .el-scrollbar__wrap').first()
        assert.ok(await scroll.evaluate(el => el.scrollWidth > el.clientWidth), '窄屏表格允许横向滚动')
        await scroll.evaluate(el => { el.scrollLeft = el.scrollWidth })
        const mobileEdit = page.getByRole('button', { name: '编辑', exact: true }).first()
        await mobileEdit.scrollIntoViewIfNeeded(); await mobileEdit.click()
        await page.getByRole('dialog', { name: '编辑海外成员', exact: true }).waitFor()
        const saveBox = await page.getByRole('button', { name: '保存成员', exact: true }).boundingBox()
        assert.ok(saveBox && saveBox.x >= 0 && saveBox.x + saveBox.width <= 390 && saveBox.y + saveBox.height <= 844, '窄屏保存按钮完整可见')
        await page.getByRole('button', { name: '取消', exact: true }).click()
        await page.getByRole('dialog', { name: '编辑海外成员', exact: true }).waitFor({ state: 'hidden' })
        await page.screenshot({ path: '../../output/playwright/phase18/members-real-mobile.png', fullPage: true })
      } else {
        await page.getByText('暂无成员管理权限', { exact: true }).waitFor()
        assert.equal(await page.getByRole('button', { name: '编辑', exact: true }).count(), 0)
        assert.equal((await context.request.get(`${base}/api/overseas/v1/members`)).status(), 403)
      }
      assert.equal(paths.some(p => p.startsWith('/api/v1/') && !p.endsWith('/auth/identity/session')), false)
      await page.getByRole('button', { name: '切换业务', exact: true }).click()
      await page.getByRole('button', { name: '海外业务', exact: true }).waitFor()
      await page.getByRole('button', { name: '退出登录', exact: true }).click()
      await page.getByRole('button', { name: '钉钉登录', exact: true }).waitFor()
      for (const path of ['/api/identity/v1/me', '/api/overseas/v1/auth/me']) assert.equal((await context.request.get(`${base}${path}`)).status(), 401)
      assert.deepEqual(errors, [])
      results.push(`${role}: 菜单/直链/刷新/统一切换退出 PASS`)
    } finally { await context.close() }
  }
  console.log(JSON.stringify(results, null, 2))
} finally { await browser.close() }
