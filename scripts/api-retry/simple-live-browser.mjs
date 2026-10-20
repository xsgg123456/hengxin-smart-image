import assert from 'node:assert/strict'
import { readFile, writeFile, mkdir } from 'node:fs/promises'
import path from 'node:path'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = 'http://127.0.0.1:18924'
const output = path.resolve('output/api-retry-simple-20261020')
await mkdir(output, { recursive: true })
const fixture = JSON.parse(await readFile(path.join(output, 'live-fixture.json'), 'utf8'))
const api = base + '/api/v1/api-image-edits/tasks/' + fixture.taskId
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } })
const page = await context.newPage()
page.setDefaultTimeout(20000)
const errors = [], writes = [], checks = []
page.on('pageerror', error => errors.push(error.message))
page.on('request', request => {
  if (request.method() === 'POST') writes.push({ url: request.url(), key: request.headers()['idempotency-key'] })
})
const drawer = page.getByRole('dialog', { name: fixture.initialTask.name, exact: true })
const card = index => drawer.locator('.result-grid > .el-card').nth(index)
const detail = async () => (await context.request.get(api)).json()
const refresh = () => drawer.getByRole('button', { name: '刷新详情', exact: true }).click()
const screenshot = name => page.screenshot({ path: path.join(output, name + '.png'), animations: 'disabled' })
try {
  await page.goto(base + '/#/api-image-edits/records?task=' + fixture.taskId)
  await card(0).getByText('已完成', { exact: true }).waitFor()
  await card(1).getByText('未完成', { exact: true }).waitFor()
  await card(2).getByText('重试中', { exact: true }).waitFor()
  assert.equal(await drawer.getByRole('button', { name: /重试未完成的/ }).count(), 0)
  assert.doesNotMatch(await drawer.innerText(), /管理员|需核实|发送名额|探测|20 次/)
  assert.ok([404, 405].includes((await context.request.post(api + '/items/' + fixture.initialTask.items[1].id + '/resolve', { data: {} })).status()))
  const schema = await (await context.request.get(base + '/openapi.json')).json()
  assert.ok(!Object.keys(schema.paths).some(route => route.endsWith('/resolve')))
  const originalResult = (await detail()).items[0].result.fileId
  await screenshot('live-mixed')
  checks.push('真实HTTP与PostgreSQL：普通用户可见成功/失败/自动重试，resolve接口已删除，混合任务无批量入口')
  await card(1).getByRole('button', { name: '重试这张', exact: true }).click()
  await card(1).getByText('等待中', { exact: true }).waitFor()
  let task = await detail()
  assert.equal(task.items[1].retry.attempts, 0)
  assert.notEqual(task.items[1].retry.cycleId, fixture.initialTask.items[1].retry.cycleId)
  assert.equal(task.items[0].result.fileId, originalResult)
  await context.request.post(base + '/__qa__/step')
  await refresh()
  await card(1).getByText('已完成', { exact: true }).waitFor()
  await card(2).getByRole('button', { name: '停止自动重试', exact: true }).click()
  await card(2).getByText('已停止', { exact: true }).waitFor()
  await drawer.getByRole('button', { name: '重试未完成的 1 张', exact: true }).waitFor()
  await screenshot('live-partial')
  checks.push('普通用户直接单张重试成功，成功图片ID保持；停止后整套终态显示批量重试')
  await page.setViewportSize({ width: 390, height: 844 })
  for (const button of await drawer.locator('.card-actions button, .detail-actions button').all()) {
    if (!(await button.isVisible())) continue
    await button.scrollIntoViewIfNeeded()
    assert.ok(await button.evaluate(el => {
      const r = el.getBoundingClientRect(), v = el.closest('.el-drawer__body').getBoundingClientRect()
      return r.left >= v.left - 1 && r.right <= v.right + 1 && r.top >= v.top - 1 && r.bottom <= v.bottom + 1
    }), await button.innerText())
  }
  await card(2).scrollIntoViewIfNeeded()
  await screenshot('live-narrow-stopped')
  await page.setViewportSize({ width: 1440, height: 1100 })
  await drawer.getByRole('button', { name: '重试未完成的 1 张', exact: true }).click()
  await card(2).getByText('等待中', { exact: true }).waitFor()
  await page.waitForTimeout(5200)
  await context.request.post(base + '/__qa__/step')
  await refresh()
  await card(2).getByText('已完成', { exact: true }).waitFor()
  task = await detail()
  assert.equal(task.status, 'succeeded')
  assert.equal(task.items[0].result.fileId, originalResult)
  assert.equal(task.items[0].retry.attempts, 1)
  assert.equal(task.items[1].retry.attempts, 1)
  assert.equal(task.items[2].retry.attempts, 1)
  assert.equal(await drawer.getByRole('button', { name: /重试这张|重试未完成的/ }).count(), 0)
  await screenshot('live-completed')
  await page.reload()
  await card(2).getByText('已完成', { exact: true }).waitFor()
  const download = page.waitForEvent('download')
  await card(0).getByRole('button', { name: '下载图片', exact: true }).click()
  assert.equal(await (await download).failure(), null)
  assert.deepEqual(errors, [])
  checks.push('390px按钮可见；真实批量接口只重试未完成图片；全部成功后刷新与下载正常')
  await writeFile(path.join(output, 'live-evidence.json'), JSON.stringify({ checks, writes, errors, finalTask: task }, null, 2))
  console.log(JSON.stringify({ checks, errors }, null, 2))
} catch (error) {
  await screenshot('live-failure')
  console.error(JSON.stringify({ errors, writes, url: page.url() }))
  throw error
} finally {
  await context.close()
  await browser.close()
}
