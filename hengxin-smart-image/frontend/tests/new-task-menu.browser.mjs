import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) })
const context = await browser.newContext()
const page = await context.newPage()
try {
  await page.goto(`${process.env.DEMO_URL || 'http://127.0.0.1:3010/'}?role=super_admin#/image-processing/wallpaper`)
  await page.getByRole('button', { name: '使用示例素材', exact: true }).click()
  await page.getByRole('textbox', { name: '任务名称', exact: true }).fill('保留的上一单')
  await page.getByRole('button', { name: '提交生成任务', exact: true }).click()
  await page.locator('.hx-detail').waitFor()
  await page.locator('.hx-detail .el-tag').filter({ hasText: /^(排队中|执行中)$/ }).first().waitFor({ timeout: 5000 })
  const taskUrl = page.url()
  await page.keyboard.press('Escape')
  await page.locator('.hx-detail').waitFor({ state: 'hidden' })
  if (!await page.getByRole('menuitem', { name: '替换壁纸', exact: true }).isVisible()) {
    await page.getByText('图片处理', { exact: true }).first().click()
  }
  for (const label of ['替换壁纸', '替换商品', '替换文字']) {
    await page.getByRole('menuitem', { name: label, exact: true }).click()
    await page.waitForURL(/newTask=/)
    const firstUrl = page.url()
    await page.getByRole('textbox', { name: '任务名称', exact: true }).waitFor()
    assert.equal(await page.getByRole('textbox', { name: '任务名称', exact: true }).inputValue(), '')
    assert.equal(await page.getByRole('button', { name: '查看已受理任务', exact: true }).count(), 0)
    assert.equal(await page.locator('.compact-picture').count(), 0)
    await page.getByRole('textbox', { name: '任务名称', exact: true }).fill('准备新单')
    await page.getByRole('menuitem', { name: label, exact: true }).click()
    await page.waitForURL(url => url.href !== firstUrl)
    await page.waitForFunction(() => document.querySelector('input[aria-label="任务名称"]')?.value === '')
    assert.equal(await page.getByRole('textbox', { name: '任务名称', exact: true }).inputValue(), '')
  }
  await page.goto(taskUrl)
  await page.locator('.hx-detail').waitFor()
  await page.locator('.hx-detail').getByText('保留的上一单', { exact: true }).waitFor()
  console.log('PASS: three menu entries create fresh sessions, repeated same-menu click resets draft, accepted receipt not reused, previous task retained')
} finally { await context.close(); await browser.close() }
