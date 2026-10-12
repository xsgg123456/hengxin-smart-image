import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3016'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless: true }), errors = []
try {
  for (const role of ['designer', 'operator']) {
    const context = await browser.newContext({ viewport: { width: 1366, height: 900 } })
    try {
      const login = await context.request.post(`${base}/api/identity/v1/dingtalk/container`, {
        headers: { 'X-HX-Request': '1', Origin: base }, data: { code: `p18-${role}` }
      })
      assert.equal(login.status(), 200)
      const page = await context.newPage(); page.on('pageerror', e => errors.push(e.message))
      await page.goto(`${base}/#/overseas`)
      await page.getByRole('heading', { name: '企业身份已连接' }).waitFor()
      const response = await context.request.get(`${base}/api/overseas/v1/tasks?search=Phase22真实方案`)
      assert.equal(response.status(), 200)
      const tasks = (await response.json()).items
      assert.equal(tasks.length, 1)
      await page.goto(`${base}/#/overseas/tasks/${tasks[0].id}`)
      await page.getByRole('heading', { name: '确认图片排版方案' }).waitFor()
      await page.getByText('产品完整展示', { exact: true }).waitFor()
      await page.getByRole('tab', { name: 'P22-B', exact: true }).click()
      await page.getByText('产品完整展示', { exact: true }).waitFor()
      assert.equal(await page.getByRole('button', { name: '确认方案，开始生图', exact: true }).count(), 0)
      await page.reload()
      await page.getByText('产品完整展示', { exact: true }).waitFor()
      await mkdir('../../output/playwright/phase22', { recursive: true })
      await page.screenshot({ path: `../../output/playwright/phase22/real-${role}.png`, fullPage: true })
      assert.equal((await context.request.get(`${base}/api/overseas/v1/tasks/${tasks[0].id}/plans`)).status(), 200)
    } finally { await context.close() }
  }
  assert.deepEqual(errors, [])
  console.log('PASS real plans browser: real identity/API, confirmed full SKU plan, reload persistence, read-only confirmed state, no page errors')
} finally { await browser.close() }
