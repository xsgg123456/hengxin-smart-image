import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.API_UI_URL || 'http://127.0.0.1:3032/'
const output = path.resolve('output/playwright/api-retry')
await mkdir(output, { recursive: true })
const picture = { fileId: 'success', name: '已保存.png', url: '/fixture/success.svg', width: 790, height: 1500 }
const version = { number: 1, picture, created: '2026-10-20T00:00:00Z', operator: '隔离测试', text: '', annotation: null, baseVersion: null }
const retry = (id, overrides = {}) => ({ cycleId: id, attempts: 7, maxAttempts: 20, startedAt: new Date().toISOString(), deadlineAt: new Date(Date.now() + 2700000).toISOString(), nextAttemptAt: null, stopRequested: false, canStop: true, reason: null, ...overrides })
const item = (id, position, state, extra = {}) => ({ id, position, source: picture, state, retries: 6, nextAttemptAt: null, result: null, error: null, currentVersion: null, versions: [], revision: null, retry: retry(id), ...extra })
const waiting = item('wait', 1, 'retry_wait', { retry: retry('wait', { nextAttemptAt: new Date(Date.now() + 120000).toISOString(), reason: '上游临时不可用，等待重试' }) })
const running = item('run', 2, 'running', { result: picture, currentVersion: 1, versions: [version] })
const failed = item('fail', 3, 'failed', { retry: retry('fail', { attempts: 20, canStop: false, reason: '本轮尝试次数已用完' }) })
const uncertain = item('unknown', 4, 'uncertain', { retry: retry('unknown', { canStop: false, reason: '原请求结果需核实' }) })
const legacy = item('legacy', 5, 'failed', { retry: undefined, retries: 3 })
const saved = item('saved', 6, 'succeeded', { result: picture, currentVersion: 1, versions: [version], retry: retry('saved', { canStop: false, attempts: 1 }) })
const task = { id: 'retry-fixture', name: 'API 重试隔离验收', prompt: '隔离路由，不访问真实 API', created: '2026-10-20T00:00:00Z', status: 'running', operator: '隔离测试', batch: { current: 1, total: 1, running: 1 }, material: picture, items: [waiting, running, failed, uncertain, legacy, saved], events: [], error: null, metrics: { requestCount: 42, retryCount: 37, elapsedSeconds: 120 } }
const channel = { enabled: true, paused: false, reason: null, cooldownUntil: new Date(Date.now() + 120000).toISOString(), recovering: false }
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1100 } })
const page = await context.newPage(), errors = [], checks = [], stops = [], retries = []
page.setDefaultTimeout(20000); page.on('pageerror', error => errors.push(error.message))
let holdStop, denyStop = false
await context.route('**/*', async route => {
  const request = route.request(), url = new URL(request.url()), p = url.pathname
  if (url.origin !== new URL(base).origin) return route.abort()
  if (p.startsWith('/fixture/')) return route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="790" height="1500"><rect width="100%" height="100%" fill="#e8f2ff"/><text x="60" y="180" font-size="48">已保存的成功图片</text></svg>' })
  if (!p.startsWith('/api/')) return route.continue()
  let body
  if (p.endsWith('/auth/me')) body = { id: 'browser-user', name: '隔离测试', role: 'super_admin', status: 'active' }
  else if (p.endsWith('/status')) body = channel
  else if (/\/items\/[^/]+\/stop$/.test(p)) {
    const target = task.items.find(i => p.includes(`/items/${i.id}/`))
    stops.push({ item: target.id, key: request.headers()['idempotency-key'] })
    if (denyStop) { denyStop = false; return route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ code: 'CONFLICT', message: '当前状态发生变化，请重试停止' }) }) }
    target.retry.stopRequested = true; target.retry.canStop = false
    if (target.state !== 'running') { target.state = 'failed'; target.retry.reason = '用户已停止本轮重试' }
    if (stops.length === 1) { await new Promise(resolve => { holdStop = resolve }); return route.abort('failed') }
    body = { taskId: task.id }
  } else if (/\/items\/[^/]+\/retry$/.test(p)) {
    retries.push(p)
    const target = task.items.find(i => p.includes(`/items/${i.id}/`))
    target.retry = retry('new-' + target.id, { attempts: 0, reason: '等待发送名额' }); target.state = 'queued'; body = { taskId: task.id }
  } else if (p.endsWith('/tasks/' + task.id)) body = task
  else if (p.endsWith('/tasks')) body = { items: [{ id: task.id, name: task.name, created: task.created, status: task.status, operator: task.operator, cover: picture, counts: { total: 6, success: task.items.filter(i => i.state === 'succeeded').length, failed: task.items.filter(i => i.state === 'failed').length, uncertain: 1 }, batch: task.batch }], total: 1, page: 1, pageSize: 20 }
  else { errors.push(`Unexpected API: ${request.method()} ${p}`); return route.fulfill({ status: 501, body: '{}' }) }
  return route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
})
const drawer = page.getByRole('dialog', { name: task.name, exact: true })
const card = index => drawer.locator('.result-grid > .el-card').nth(index)
async function refresh() { await drawer.getByRole('button', { name: '刷新详情', exact: true }).click() }
async function screenshot(name) { await page.screenshot({ path: path.join(output, name + '.png'), animations: 'disabled' }) }
async function inspectBounds() {
  for (const content of await drawer.locator('.retry-status p, .retry-status button, .card-actions button').all()) {
    await content.scrollIntoViewIfNeeded()
    assert.equal(await content.evaluate(el => {
      const r = el.getBoundingClientRect(), card = el.closest('.el-card__body').getBoundingClientRect(), view = el.closest('.el-drawer__body').getBoundingClientRect()
      return r.left >= card.left - 1 && r.right <= card.right + 1 && r.top >= view.top - 1 && r.bottom <= view.bottom + 1 && el.scrollWidth <= el.clientWidth + 1
    }), true, await content.innerText())
  }
}
try {
  await page.goto(base + '#/api-image-edits/records?task=' + task.id)
  await card(0).getByText('本轮 7/20 次', { exact: true }).waitFor()
  await drawer.getByText(/上游冷却中/).waitFor()
  assert.match(await card(4).innerText(), /历史记录：已自动重试 3 次/)
  assert.match(await card(3).innerText(), /不会自动重复生成/)
  assert.equal(await card(5).getByRole('button', { name: '停止重试', exact: true }).count(), 0)
  const before = await card(0).locator('.retry-status').innerText()
  await page.waitForTimeout(1300)
  assert.notEqual(await card(0).locator('.retry-status').innerText(), before)
  await screenshot('wide-states'); await inspectBounds()
  checks.push('真实次数、动态倒计时、冷却、未知、失败及旧记录，无前端调度请求')
  await page.setViewportSize({ width: 390, height: 844 })
  await inspectBounds()
  await card(0).locator('.retry-status').scrollIntoViewIfNeeded(); await screenshot('narrow-waiting')
  checks.push('390px逐一滚动检查所有卡片提示及按钮均处于卡片和抽屉可见边界内')
  await page.setViewportSize({ width: 1440, height: 1100 })
  const stop = card(0).getByRole('button', { name: '停止重试', exact: true })
  await stop.click(); await page.waitForFunction(() => document.querySelector('.retry-status button')?.disabled)
  await card(0).locator('.retry-status button').evaluate(el => el.click()); assert.equal(stops.length, 1)
  holdStop(); await card(0).getByRole('button', { name: '确认原停止请求', exact: true }).waitFor()
  await page.reload()
  await card(0).getByRole('button', { name: '确认原停止请求', exact: true }).click()
  await card(0).getByRole('button', { name: '确认原停止请求', exact: true }).waitFor({ state: 'hidden' })
  assert.deepEqual(stops[0], stops[1]); assert.ok(stops[0].key)
  await card(0).getByText(/本轮已停止重试/).waitFor()
  checks.push('停止loading/防双击、响应丢失后刷新恢复同一幂等键，确认后显示停止完成')
  await card(1).getByRole('button', { name: '停止重试', exact: true }).click()
  await card(1).getByText(/已发出的请求继续收取结果/).waitFor()
  assert.equal(await card(1).getByRole('button', { name: '停止重试', exact: true }).count(), 0)
  assert.equal(await card(1).locator('.result-picture img').count(), 1)
  await screenshot('stopping-inflight')
  running.state = 'succeeded'; await refresh()
  await card(1).getByText('成功', { exact: true }).waitFor()
  assert.equal(await card(1).getByText(/已请求停止后续/).count(), 0)
  assert.equal(await card(1).locator('.result-picture img').count(), 1)
  checks.push('在途停止仅停止后续请求、旧图保留，晚到成功正常呈现')
  assert.equal(await card(2).getByRole('button', { name: '继续重试这张', exact: true }).isEnabled(), true)
  await card(2).getByRole('button', { name: '继续重试这张', exact: true }).click()
  await card(2).getByText('本轮 0/20 次', { exact: true }).waitFor()
  assert.equal(retries.length, 1)
  denyStop = true
  await card(2).getByRole('button', { name: '停止重试', exact: true }).click()
  await card(2).getByText('当前状态发生变化，请重试停止', { exact: true }).waitFor()
  assert.equal(await card(2).getByRole('button', { name: '停止重试', exact: true }).isEnabled(), true)
  await card(2).getByRole('button', { name: '停止重试', exact: true }).click()
  await card(2).getByText(/本轮已停止重试/).waitFor()
  checks.push('冷却期间合法失败项仍能开启新轮排队，明确停止失败后按钮恢复可重试')
  channel.cooldownUntil = null; channel.recovering = true
  await page.reload(); await drawer.getByText(/上游恢复探测中/).waitFor()
  await screenshot('recovering-final')
  await card(5).scrollIntoViewIfNeeded(); await card(5).locator('.result-picture img').waitFor()
  assert.equal(await card(5).locator('.result-picture img').count(), 1)
  assert.deepEqual(errors, [])
  checks.push('恢复探测提示与成功图片保持，未访问生产API或CLI停止')
  await page.goto(new URL('#/api-image-edits/create', base).href)
  await page.getByText('每张每轮最多尝试 20 次（含首次）', { exact: true }).waitFor()
  await page.getByText(/从首次发送起 45 分钟内/).waitFor()
  assert.ok(!(await page.locator('body').innerText()).includes('最多 3 次'))
  await screenshot('create-policy')
  checks.push('正式新建页展示20次/45分钟及随机错峰规则，无旧3次提示')
  await writeFile(path.join(output, 'evidence.json'), JSON.stringify({ checks, stops, retries, errors }, null, 2))
  console.log(JSON.stringify({ checks, requests: stops.length + retries.length, errors }, null, 2))
} catch (error) { await screenshot('failure'); console.error(JSON.stringify({ errors, url: page.url() })); throw error }
finally { await context.close(); await browser.close() }
