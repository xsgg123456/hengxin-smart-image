import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.OVERSEAS_URL || 'http://127.0.0.1:3012'
const output = path.resolve('../../output/playwright/overseas-20261012')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await context.newPage(), errors = [], checks = []
page.setDefaultTimeout(20000)
page.on('pageerror', e => errors.push(e.message))
const btn = name => page.getByRole('button', { name, exact: true })
try {
  await page.goto(`${base}/overseas-preview.html`)
  await btn('钉钉登录').click(); await btn('海外业务').click()
  await page.locator('.art-card').first().waitFor()
  const overseasBox = await page.locator('.art-card').first().evaluate(el => ({
    mode: document.documentElement.getAttribute('data-box-mode'),
    radius: getComputedStyle(el).borderRadius,
  }))
  assert.equal(overseasBox.mode, 'border-mode')
  await page.getByRole('menuitem', { name: '工作流任务', exact: true }).click()
  await page.getByText('暂无匹配任务，请提交图需或清空筛选', { exact: true }).waitFor()
  await page.getByRole('menuitem', { name: '提交图需', exact: true }).click()
  await btn('填入示例').click()
  await page.locator('.file-row').getByRole('button', { name: '移除', exact: true }).click()
  await btn('确认并提交，开始分析').click()
  await page.getByRole('alert').filter({ hasText: '至少提供一份' }).waitFor()
  await page.locator('input[type=file]').first().setInputFiles({ name: 'wrong.png', mimeType: 'image/png', buffer: Buffer.from('test') })
  await page.getByRole('alert').filter({ hasText: '请选择有效资料文件' }).waitFor()
  await page.locator('input[type=file]').nth(1).setInputFiles({ name: '竞品分析.csv', mimeType: 'text/csv', buffer: Buffer.from('name,price\nsample,10') })
  await btn('确认并提交，开始分析').click()
  await page.getByRole('heading', { name: '确认图片排版方案', exact: true }).waitFor()
  await btn('← 返回工作流任务').click()
  await btn('删除').click(); await page.getByRole('dialog').getByRole('button', { name: '删除任务', exact: true }).click()
  await page.getByText('暂无匹配任务，请提交图需或清空筛选', { exact: true }).waitFor()
  checks.push('复用侧栏导航、任务空态、无资料阻止、文件类型校验、仅竞品资料上传提交、删除确认')
  await page.keyboard.press('Control+k')
  await page.locator('.search-modal .el-dialog').waitFor()
  await page.keyboard.press('Escape')
  await btn('切换业务').click(); await btn('海外业务').click()
  await page.keyboard.press('Control+k'); await page.locator('.search-modal .el-dialog').waitFor(); await page.keyboard.press('Escape')
  checks.push('复用全局搜索及业务切换后重新挂载')
  await btn('切换业务').click(); await page.setViewportSize({ width: 390, height: 844 })
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
  await btn('海外业务').scrollIntoViewIfNeeded()
  await page.screenshot({ path: path.join(output, '10-entry-mobile.png'), fullPage: true })
  await page.setViewportSize({ width: 1440, height: 1000 })
  await btn('国内业务').click()
  await page.waitForURL(/#\/api-image-edits\/create/)
  await page.locator('.hx-page h1').filter({ hasNotText: '恒鑫智图' }).waitFor()
  await page.locator('.layout-sidebar .el-menu').first().waitFor()
  const domesticBox = await page.locator('.art-card').first().evaluate(el => ({
    mode: document.documentElement.getAttribute('data-box-mode'),
    radius: getComputedStyle(el).borderRadius,
  }))
  assert.deepEqual(overseasBox, domesticBox)
  checks.push('海外与一期卡片模式、实际圆角一致')
  await page.screenshot({ path: path.join(output, '11-domestic-baseline.png'), fullPage: true })
  checks.push('国内入口进入一期原有模拟页面，保存同视口视觉基准')
  assert.deepEqual(errors, [])
  await writeFile(path.join(output, 'shell-result.json'), JSON.stringify({ checks, errors }, null, 2))
  console.log(JSON.stringify({ passed: checks.length, checks, errors }, null, 2))
} catch (error) { console.error(await page.locator('body').innerText()); await page.screenshot({ path: path.join(output, 'shell-failure.png'), fullPage: true }); throw error }
finally { await context.close(); await browser.close() }
