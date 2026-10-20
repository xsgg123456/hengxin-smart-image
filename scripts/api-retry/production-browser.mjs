import assert from 'node:assert/strict'
import { readFile, writeFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE)
const token = (await readFile(process.env.HX_QA_COOKIE, 'utf8')).trim()
const output = process.env.HX_QA_OUTPUT
const origin = 'https://zhitu.qhhengxin.top'
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
await context.addCookies([{ name: 'hx_session', value: token, domain: 'zhitu.qhhengxin.top', path: '/', httpOnly: true, secure: true, sameSite: 'Lax' }])
const page = await context.newPage(), errors = [], blocked = [], checks = []
page.on('pageerror', error => errors.push(error.message))
await context.route('**/*', route => {
  if (!['GET', 'HEAD', 'OPTIONS'].includes(route.request().method())) { blocked.push(route.request().method()); return route.abort() }
  return route.continue()
})
const get = async path => { const response = await context.request.get(origin + path); assert.equal(response.status(), 200); return response.json() }
try {
  const channel = await get('/api/v1/api-image-edits/status')
  assert.equal(channel.enabled, true); assert.equal(channel.paused, false)
  assert.ok(Object.hasOwn(channel, 'cooldownUntil') && Object.hasOwn(channel, 'recovering'))
  const list = await get('/api/v1/api-image-edits/tasks?page=1&pageSize=100&view=summary')
  const candidates = list.items || list.data
  assert.ok(Array.isArray(candidates) && candidates.length)
  let task, unfinished
  for (const row of candidates.slice(0, 15)) {
    const detail = await get('/api/v1/api-image-edits/tasks/' + row.id)
    if (!task && detail.items[0]?.result) task = detail
    if (!unfinished && detail.items.some(item => item.state === 'failed')) unfinished = detail
    if (task && unfinished) break
  }
  assert.ok(task)
  await page.goto(origin + '/#/api-image-edits/records?task=' + task.id, { waitUntil: 'domcontentloaded', timeout: 60000 })
  const compare = page.getByRole('button', { name: '查看原图 / 对照成品', exact: true })
  await compare.first().waitFor({ timeout: 30000 })
  const drawer = page.getByRole('dialog', { name: task.name, exact: true })
  assert.doesNotMatch(await drawer.innerText(), /核实已停止|网络尝试|发送名额|本轮 \d+\/20/)
  await page.screenshot({ path: output + '/production-records.png', animations: 'disabled' })
  checks.push('正式记录页与历史终态详情可读，新通道状态字段真实返回')
  await compare.first().click()
  const dialog = page.getByRole('dialog', { name: /原图与成品对照/ })
  await dialog.waitFor()
  await page.waitForFunction(() => {
    const images = document.querySelector('.comparison-grid')?.querySelectorAll('img')
    return images?.length === 2 && Array.from(images).every(image => image.complete && image.naturalWidth > 0)
  }, null, { timeout: 60000 })
  await page.screenshot({ path: output + '/production-existing-images.png', animations: 'disabled' })
  await dialog.getByRole('button', { name: '关闭对照', exact: true }).click()
  const saved = task.items.find(item => item.result)
  const download = await context.request.get(origin + '/api/v1/api-image-edits/files/' + saved.result.fileId + '/content?download=true')
  assert.equal(download.status(), 200); assert.ok(download.headers()['content-type'].startsWith('image/')); assert.ok((await download.body()).length > 0)
  checks.push('既有原图、成品实际渲染且原文件下载成功')
  await page.setViewportSize({ width: 390, height: 844 })
  await page.screenshot({ path: output + '/production-narrow.png', animations: 'disabled' })
  await page.setViewportSize({ width: 1440, height: 1000 })
  if (unfinished) {
    await page.goto(origin + '/#/api-image-edits/records?task=' + unfinished.id, { waitUntil: 'domcontentloaded', timeout: 60000 })
    await page.reload()
    const failureDrawer = page.getByRole('dialog', { name: unfinished.name, exact: true })
    await failureDrawer.getByRole('button', { name: '重试这张', exact: true }).first().waitFor()
    assert.equal(await failureDrawer.getByRole('button', { name: /核实/ }).count(), 0)
    await page.screenshot({ path: output + '/production-failed-retry.png', animations: 'disabled' })
    checks.push('正式失败记录展示直接重试按钮，无管理员核实按钮；未点击重试')
  }
  await page.goto(origin + '/#/api-image-edits/create', { waitUntil: 'domcontentloaded', timeout: 60000 })
  await page.getByText('按原图尺寸 · PNG', { exact: true }).waitFor()
  await page.getByText('未完成的图片会自动重试', { exact: true }).waitFor()
  assert.doesNotMatch(await page.locator('body').innerText(), /20 次|45 分钟|管理员核实/)
  await page.screenshot({ path: output + '/production-create.png', animations: 'disabled' })
  checks.push('正式新建入口与移动端可打开，仅只读查看，未提交生图')
  assert.deepEqual(errors, []); assert.deepEqual(blocked, [])
  const result = { checks, taskId: task.id, channel, errors, blockedWrites: blocked, generationCalls: 0 }
  await writeFile(output + '/browser-verification.json', JSON.stringify(result, null, 2))
  console.log(JSON.stringify({ checks, errors, generationCalls: 0 }))
} catch (error) {
  await page.screenshot({ path: output + '/production-failure.png' })
  throw error
} finally { await context.close(); await browser.close() }
