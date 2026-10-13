import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3016'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless: true }), errors = []
try {
  for (const role of ['designer', 'operator']) {
    const context = await browser.newContext({ viewport: { width: 1366, height: 900 }, acceptDownloads: true })
    try {
      const login = await context.request.post(`${base}/api/identity/v1/dingtalk/container`, {
        headers: { 'X-HX-Request': '1', Origin: base }, data: { code: `p18-${role}` }
      })
      assert.equal(login.status(), 200)
      const page = await context.newPage(); page.on('pageerror', e => errors.push(e.message))
      await page.goto(`${base}/#/overseas`)
      await page.locator('.hx-page').filter({ hasText: /工作流任务|暂无此功能权限/ }).first().waitFor()
      const response = await context.request.get(`${base}/api/overseas/v1/tasks?search=Phase23真实图片`)
      assert.equal(response.status(), 200)
      const tasks = (await response.json()).items
      assert.equal(tasks.length, 1)
      await page.goto(`${base}/#/overseas/tasks/${tasks[0].id}`)
      await page.getByRole('heading', { name: '图片审核', exact: true }).waitFor()
      const result = await context.request.get(`${base}/api/overseas/v1/tasks/${tasks[0].id}/pictures`)
      assert.equal(result.status(), 200)
      const pictures = (await result.json()).items
      assert.deepEqual(pictures.map(p => p.version).sort(), [1, 2])
      assert.ok(pictures.every(p => p.approved))
      await page.getByRole('tab', { name: 'P23-B', exact: true }).last().click()
      await page.getByText('版本历史', { exact: true }).click()
      await page.getByAltText('历史 v1', { exact: true }).waitFor()
      await page.waitForFunction(() => Array.from(document.images).filter(i => i.src.includes('/pictures/')).every(i => i.complete && i.naturalWidth === 32))
      assert.equal(await page.getByRole('button', { name: '审核通过', exact: true }).count(), 0)
      await mkdir('../../output/playwright/phase23', { recursive: true })
      await page.screenshot({ path: `../../output/playwright/phase23/real-${role}.png`, fullPage: true })
      await page.goto(`${base}/#/overseas/archive`)
      await page.getByRole('heading', { name: '成品库', exact: true }).waitFor()
      await page.getByLabel('筛选品牌', { exact: true }).fill('HX23')
      await page.getByLabel('筛选 SKU', { exact: true }).fill('P23-B')
      await page.getByText('Charger23', { exact: true }).waitFor()
      const downloadEvent = page.waitForEvent('download')
      await page.getByRole('button', { name: '下载整套成品', exact: true }).click()
      const download = await downloadEvent
      assert.equal(await download.failure(), null)
      assert.ok(download.suggestedFilename().endsWith('.zip'))
      await page.setViewportSize({ width: 390, height: 844 })
      await page.waitForFunction(() => !document.querySelector('.menu-left-open') && document.getAnimations().every(a => a.playState !== 'running'))
      await page.screenshot({ path: `../../output/playwright/phase23/archive-mobile-${role}.png`, fullPage: true })
      assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1))
    } finally { await context.close() }
  }
  assert.deepEqual(errors, [])
  console.log('PASS real pictures browser: real images/history, immutable approval, archive filtering/download, narrow viewport and no page errors')
} finally { await browser.close() }
