import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3016'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless: true }), errors = []
const headers = { 'X-HX-Request': '1', Origin: base }
try {
  for (const role of ['admin', 'operator', 'designer', 'operator_manager', 'design_manager']) {
    const context = await browser.newContext({ viewport: { width: 1366, height: 900 } })
    try {
      assert.equal((await context.request.post(`${base}/api/identity/v1/dingtalk/container`, { headers, data: { code: `p18-${role}` } })).status(), 200)
      const page = await context.newPage(); page.on('pageerror', e => errors.push(e.message))
      await page.goto(`${base}/#/overseas`)
      await page.locator('.hx-page').filter({ hasText: /工作流任务|暂无此功能权限/ }).first().waitFor()
      const go = async (route, heading) => { await page.goto(`${base}/#/overseas/admin/${route}`); await page.getByRole('heading', { name: heading, exact: true }).waitFor() }
      await go('usage', '调用统计')
      await page.getByRole('button', { name: '刷新统计', exact: true }).waitFor()
      await page.getByText(/共 \d+ 个作业/).waitFor()
      const tasks = await context.request.get(`${base}/api/overseas/v1/tasks?search=Phase24管理验证旧快照`)
      const list = (await tasks.json()).items
      assert.equal(list.length, 1)
      await page.getByLabel('任务 ID', { exact: true }).fill(list[0].id)
      await page.getByRole('button', { name: '应用筛选', exact: true }).click()
      await page.getByText('共 1 个作业', { exact: true }).waitFor()
      assert.equal(await page.locator('.hx-admin-kpi').filter({ hasText: '输入 Token' }).locator('strong').innerText(), '10')
      assert.equal(await page.locator('.hx-admin-kpi').filter({ hasText: '输出 Token' }).locator('strong').innerText(), '20')
      await page.getByRole('button', { name: '查看记录', exact: true }).click()
      await page.getByText('海外执行记录', { exact: true }).waitFor()
      await page.keyboard.press('Escape')
      await go('monitor', '执行监控')
      if (role === 'admin') {
        await go('skills', 'Skill 管理')
        await page.getByRole('button', { name: '刷新 Skill', exact: true }).waitFor()
        const catalog = await (await context.request.get(`${base}/api/overseas/v1/management/skills`)).json()
        for (const skill of catalog.items) await page.getByText(skill.displayName, { exact: true }).waitFor()
        assert.equal(await page.getByRole('button', { name: '添加 Skill', exact: true }).count(), 0)
        assert.equal(await page.getByRole('columnheader', { name: '描述', exact: true }).count(), 1)
        await go('settings', '系统配置')
        await page.getByLabel('执行时限', { exact: true }).waitFor()
        const settingsResponse = await context.request.get(`${base}/api/overseas/v1/management/settings`)
        const initial = await settingsResponse.json()
        const { autoCleanup, ...draft } = initial
        assert.equal(autoCleanup, false)
        assert.equal((await context.request.patch(`${base}/api/overseas/v1/management/settings`, { headers, data: { ...draft, timeoutSeconds: 300 } })).status(), 200)
        await page.getByLabel('执行时限', { exact: true }).fill('240')
        await page.getByRole('button', { name: '保存配置', exact: true }).click()
        await page.getByText('配置已变化，已刷新版本并保留草稿；请核对后保存', { exact: true }).waitFor()
        assert.equal(await page.getByLabel('执行时限', { exact: true }).inputValue(), '240')
        await page.getByRole('button', { name: '保存配置', exact: true }).click()
        await page.getByText('配置已保存', { exact: true }).waitFor()
        await page.reload()
        await page.getByLabel('执行时限', { exact: true }).waitFor()
        assert.equal(await page.getByLabel('执行时限', { exact: true }).inputValue(), '240')
        await page.getByLabel('执行时限', { exact: true }).fill(String(initial.timeoutSeconds))
        await page.getByRole('button', { name: '保存配置', exact: true }).click()
        await page.getByText('配置已保存', { exact: true }).waitFor()
      } else {
        assert.equal((await context.request.get(`${base}/api/overseas/v1/management/settings`)).status(), 403)
        await page.goto(`${base}/#/overseas/admin/settings`)
        await page.getByText('暂无此管理页面权限', { exact: true }).waitFor()
        await go('usage', '调用统计')
      }
      await page.setViewportSize({ width: 390, height: 844 })
      await page.waitForFunction(() => !document.querySelector('.menu-left-open') && document.getAnimations().every(a => a.playState !== 'running'))
      await mkdir('../../output/playwright/phase24', { recursive: true })
      await page.screenshot({ path: `../../output/playwright/phase24/real-${role}.png`, fullPage: true })
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
    } finally { await context.close() }
  }
  assert.deepEqual(errors, [])
  console.log('PASS real management browser: five roles, scoped tokens/monitor, immutable Skill versions, disable, settings stale409/draft/persistence, narrow viewport')
} finally { await browser.close() }
