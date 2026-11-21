// Run only against the disposable local creative-workflow fixture with its two test identities.
import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = new URL(process.env.OVERSEAS_LOCAL_URL || 'http://127.0.0.1:4231/overseas/')
assert.ok(['127.0.0.1', 'localhost', '127.0.0.2'].includes(base.hostname))
const browser = await chromium.launch()
const failures = []
let lastPage
async function member(role) {
  const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
  await context.addCookies([{ name: 'local-qa-identity', value: role, url: base.origin }])
  const me = await (await context.request.get(base.origin + '/api/identity/v1/me')).json()
  assert.equal(me.sessionId, 'qa-' + role, 'requires isolated fixture')
  const page = await context.newPage()
  page.on('pageerror', error => failures.push(error.message))
  page.setDefaultTimeout(15000)
  lastPage = page
  await page.goto(new URL('#/overseas/design-center', base).href)
  if (role !== 'non_designer') await page.locator('aside').getByText('创作工具集', { exact: true }).click()
  await page.getByRole('heading', { name: '创作工具集', exact: true }).waitFor()
  return page
}
async function create(page, key, sku, productName, { lostResponse = false } = {}) {
  const card = page.locator('[data-scene="' + key + '"] button')
  await card.click()
  const dialog = page.getByRole('dialog')
  const submit = dialog.getByRole('button', { name: '进入 AI 设计工作台' })
  await submit.click()
  if (key === 'custom-size') {
    await dialog.getByText('请用一个加号分隔商品名称和 SKU，两项均须填写').waitFor()
    assert.equal(await dialog.getByRole('textbox').count(), 1)
    await dialog.getByLabel('商品名称+SKU', { exact: true }).fill(productName + '＋' + sku)
  } else {
    await dialog.getByText('请填写商品 SKU', { exact: true }).waitFor()
    assert.ok(await dialog.getByRole('combobox', { name: '目标平台' }).isDisabled())
    const brand = dialog.getByRole('textbox', { name: '品牌', exact: true })
    if (['outon', 'outonlife', 'beleev'].includes(key)) {
      assert.equal(await brand.inputValue(), key.toUpperCase())
      assert.equal(await brand.getAttribute('readonly'), '')
    } else assert.equal(await brand.count(), 0)
    await dialog.getByLabel('商品 SKU', { exact: true }).fill(sku)
    await dialog.getByLabel('品名', { exact: true }).fill(productName)
    await dialog.getByRole('combobox', { name: '语言' }).press('Enter')
    await page.getByRole('option', { name: '英语' }).click()
  }
  let original, keyUsed
  const path = '**/api/overseas/v1/tasks/creative-tools'
  if (lostResponse) {
    await page.route(path, async route => {
      keyUsed = route.request().headers()['idempotency-key']
      const response = await route.fetch()
      assert.equal(response.status(), 201)
      original = await response.json()
      await route.abort()
    }, { times: 1 })
    await submit.click()
    await dialog.getByText('服务连接失败，请稍后重试').waitFor()
  }
  const written = page.waitForResponse(r => r.request().method() === 'POST' && r.url().endsWith('/tasks/creative-tools'))
  await submit.click()
  const response = await written
  assert.ok(response.ok(), await response.text())
  const task = await response.json()
  assert.equal(task.toolKey, key)
  assert.equal(task.productName, productName)
  assert.equal(task.skus[0].code, sku)
  assert.equal(task.workflow, 'studio')
  assert.equal(task.createdBy.id, task.designer.id)
  if (lostResponse) {
    assert.equal(response.status(), 200)
    assert.equal(task.id, original.id)
    assert.equal(response.request().headers()['idempotency-key'], keyUsed)
  }
  await page.waitForURL('**/#/overseas/tasks/' + task.id)
  await page.getByText('与 Codex 协作', { exact: true }).waitFor()
  return task
}
try {
  const designer = await member('designer')
  const sku = 'FORM-' + Date.now()
  const a = await create(designer, 'outon', sku, '设计验收', { lostResponse: true })
  assert.equal(a.creatorIdentity, 'designer')
  const page = await member('non_designer')
  assert.equal(await page.locator('aside').getByText('设计任务中心', { exact: true }).count(), 0)
  await page.locator('aside').getByText('成品库', { exact: true }).waitFor()
  for (const [key, title] of [['outonlife','OUTONLIFE'], ['beleev','BELEEV'], ['walmart',''], ['home-depot',''], ['mercado-libre','']]) {
    await page.locator('[data-scene="' + key + '"] button').click()
    const dialog = page.getByRole('dialog')
    assert.ok(await dialog.getByRole('combobox', { name: '目标平台' }).isDisabled())
    const brand = dialog.getByRole('textbox', { name: '品牌' })
    if (title) assert.equal(await brand.inputValue(), title)
    else assert.equal(await brand.count(), 0)
    await dialog.getByRole('button', { name: '取消' }).click()
  }
  const b = await create(page, 'wayfair', sku, '非设计验收')
  assert.equal(b.creatorIdentity, 'non_designer')
  const button = name => page.getByRole('button', { name, exact: true })
  const mine = page.getByRole('dialog', { name: '我的创作' })
  await button('返回我的创作').click()
  await mine.getByRole('button', { name: /非设计验收/ }).first().waitFor()
  assert.equal(await mine.getByRole('button', { name: /^设计验收/ }).count(), 0)
  await mine.getByLabel('搜索品名或 SKU').fill('no-match-' + sku)
  await mine.getByText('没有找到匹配的创作').waitFor()
  await mine.getByLabel('搜索品名或 SKU').fill(sku)
  await mine.getByRole('button', { name: /非设计验收/ }).click()
  await page.waitForURL('**/#/overseas/tasks/' + b.id)
  await page.reload()
  await page.getByText('与 Codex 协作', { exact: true }).waitFor()
  const denied = page.waitForResponse(r => new URL(r.url()).pathname.endsWith('/tasks/' + a.id))
  await page.goto(new URL('#/overseas/tasks/' + a.id, base).href)
  assert.ok([403, 404].includes((await denied).status()))
  assert.equal(await page.getByText('与 Codex 协作', { exact: true }).count(), 0)
  await page.goto(new URL('#/overseas/creative-tools', base).href)
  await page.setViewportSize({ width: 390, height: 844 })
  const c = await create(page, 'custom-size', sku + '-C', '手动尺寸')
  assert.equal(c.designType, 'custom')
  await button('返回我的创作').click()
  await mine.getByRole('button', { name: /手动尺寸/ }).first().waitFor()
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
  assert.deepEqual(failures, [])
  console.log('PASS eight forms, real idempotency replay, owned search/resume, scoped navigation, private URL, desktop/mobile; no model invoked')
} catch (error) {
  console.error(lastPage?.url(), (await lastPage?.locator('body').innerText())?.slice(-1800))
  throw error
} finally {
  await browser.close()
}
