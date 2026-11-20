// Exercises the isolated design-center preview in a fresh, local-only browser context.
import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = new URL(process.env.DESIGN_CENTER_PREVIEW_URL || 'http://127.0.0.1:3086/preview-overseas-design-center/')
assert.ok(['localhost', '127.0.0.1'].includes(base.hostname))
const browser = await chromium.launch({ headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1440, height: 960 } })
  const errors = []
  page.on('pageerror', err => errors.push(err.message))
  await page.route('**/*', route => new URL(route.request().url()).origin === base.origin
    ? route.continue() : route.abort())
  const home = new URL('#/overseas/design-center', base).href
  const taskIds = []
  const customCard = page.getByRole('button', { name: '自定义生图，开始创作' })
  const dialog = page.getByRole('dialog', { name: '新建自定义生图' })
  const name = '测试同名台灯+SKU-1120'
  for (let i = 0; i < 2; i++) {
    await page.goto(home)
    await customCard.waitFor()
    assert.equal(await page.locator('.dc-card[data-platform]').count(), 5)
    await page.locator('.dc-card[data-platform]').last().focus()
    await page.keyboard.press('Tab')
    assert.ok(await customCard.evaluate(el => el === document.activeElement && el.matches(':focus-visible')))
    assert.equal(await customCard.locator('.dc-art').evaluate(el => getComputedStyle(el).transitionDuration), '3s')
    await page.keyboard.press('Enter')
    assert.equal(await dialog.locator('input').count(), 1)
    const input = dialog.getByRole('textbox', { name: '商品名称+SKU' })
    await input.fill('SKU-1120')
    await dialog.getByRole('button', { name: '进入 AI 设计工作台' }).click()
    await dialog.getByText(/请用一个加号/).waitFor()
    await input.fill(' 测试同名台灯 + SKU-1120 ')
    await input.press('Enter')
    await page.getByRole('heading', { name, exact: true }).waitFor()
    taskIds.push(page.url().split('/').pop())
    await page.getByRole('button', { name: '返回设计任务中心' }).click()
  }
  assert.notEqual(...taskIds)
  await page.getByText('全部设计类型', { exact: true }).click()
  await page.getByRole('option', { name: '自定义生图', exact: true }).click()
  await page.getByLabel('搜索任务').fill('SKU-1120')
  const rows = page.locator('tbody tr').filter({ hasText: name })
  assert.equal(await rows.count(), 2)
  for (let i = 0; i < 2; i++) {
    assert.ok((await rows.nth(i).innerText()).includes('自定义生图'))
    await rows.nth(i).getByRole('button', { name: '继续设计' }).click()
    await page.getByRole('heading', { name, exact: true }).waitFor()
    assert.equal(page.url().split('/').pop(), taskIds[1 - i])
    await page.getByRole('button', { name: '返回设计任务中心' }).click()
  }
  await page.reload()
  await page.getByLabel('搜索任务').fill('测试同名台灯')
  assert.equal(await rows.count(), 2)
  await page.setViewportSize({ width: 375, height: 640 })
  await page.goto(home)
  await customCard.click()
  for (const node of [dialog.getByRole('textbox'), dialog.getByRole('button', { name: '进入 AI 设计工作台' })]) {
    const { x, y, width, height } = await node.boundingBox()
    assert.ok(x >= 0 && y >= 0 && x + width <= 375 && y + height <= 640)
  }
  assert.deepEqual(errors, [])
  console.log('PASS 5 platform cards, 3s keyboard animation, single-field validation, independent duplicate-name tasks, design type and SKU searches, reload and mobile dialog')
} finally { await browser.close() }
