// Every API/image request is intercepted in a fresh browser context; no production IO.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve, isAbsolute } from 'node:path'
import { pathToFileURL } from 'node:url'
const moduleName = process.env.PLAYWRIGHT_MODULE || 'playwright'
const { chromium } = await import(isAbsolute(moduleName) ? pathToFileURL(moduleName).href : moduleName)
const base = process.env.API_UI_URL || 'http://127.0.0.1:3028/'
assert.equal(new URL(base).hostname, '127.0.0.1')
const output = resolve('output/playwright/api-activity')
await mkdir(output, { recursive: true })
const picture = { fileId: 'image', name: '原图.png', url: '/fixture/image.svg' }
const task = { id: 'activity-fixture', name: '国内任务隔离验收', prompt: '隔离测试', created: '2026-10-15T08:00:00Z',
  status: 'succeeded', operator: '隔离测试', batch: { current: 1, total: 1, running: 0 }, material: picture,
  events: [], error: null, metrics: { requestCount: 1, retryCount: 0, elapsedSeconds: 5 },
  cliActivity: 'queued', canDelete: false, deleteBlockedReason: 'CLI 修改正在排队', deletionState: 'idle', deletionError: null,
  items: [{ id: 'item-1', position: 1, source: picture, state: 'succeeded', cliActivity: 'queued', retries: 0, nextAttemptAt: null,
    result: picture, error: null, currentVersion: 1, versions: [{ number: 1, picture, created: '2026-10-15T08:00:00Z',
      operator: '隔离测试', text: '', annotation: null, baseVersion: null }], revision: null }] }
let deletion = { state: 'deleting', message: null }, deleted = false, deletes = 0, lists = 0
const errors = [], checks = [], receipts = []
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await context.newPage()
page.setDefaultTimeout(20000)
page.on('pageerror', error => errors.push(error.message))
await context.route('**/*', async route => {
  const url = new URL(route.request().url()), method = route.request().method()
  if (url.origin !== new URL(base).origin) return route.abort()
  const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  const receipt = (body, status = 200) => { receipts.push({ method, status, ...body }); return json(body, status) }
  if (url.pathname === '/fixture/image.svg') return route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800"><rect width="100%" height="100%" fill="#e8f2ff"/><text x="100" y="200" font-size="30">原有正式成品</text></svg>' })
  if (!url.pathname.startsWith('/api/')) return route.continue()
  if (url.pathname.endsWith('/auth/me')) return json({ id: 'test-user', name: '隔离测试', role: 'super_admin', status: 'active' })
  if (url.pathname.endsWith('/status')) return json({ enabled: true, paused: false, reason: null })
  if (url.pathname.endsWith('/deletion')) return receipt(deletion)
  if (url.pathname.endsWith('/tasks/' + task.id)) {
    if (method === 'DELETE') { deletes++; task.deletionState = 'deleting'; task.canDelete = false; task.deleteBlockedReason = '正在永久删除任务'; return receipt({ state: 'deleting', message: null }, 202) }
    return json(task)
  }
  if (url.pathname.endsWith('/tasks')) {
    lists++
    return json({ items: deleted ? [] : [{ ...task, cover: picture, counts: { total: 1, success: 1, failed: 0, uncertain: 0 } }], total: deleted ? 0 : 1, page: 1, pageSize: 20 })
  }
  errors.push(`${method} ${url.pathname}`)
  return route.fulfill({ status: 501, body: '{}' })
})
const row = () => page.getByRole('row').filter({ hasText: task.name })
const drawer = () => page.getByRole('dialog', { name: task.name, exact: true })
const refresh = () => page.getByRole('button', { name: '刷新', exact: true }).click()
function activity(value) { task.cliActivity = value; task.items[0].cliActivity = value; task.canDelete = value === 'idle'; task.deleteBlockedReason = value === 'idle' ? null : 'CLI 修改尚未确认结束' }
async function shot(name) { await page.locator('.el-loading-mask:visible').first().waitFor({ state: 'hidden' }); await page.screenshot({ path: resolve(output, name + '.png'), animations: 'disabled' }) }
try {
  await page.goto(base + '#/api-image-edits/records?task=' + task.id)
  await drawer().getByText('等待修改', { exact: true }).waitFor()
  assert.equal(await row().getByText('全部成功', { exact: true }).count(), 1)
  assert.equal(await row().getByRole('button', { name: '删除', exact: true }).isDisabled(), true)
  await drawer().getByText('当前 V1 · 点击放大', { exact: true }).waitFor()
  await shot('queued-detail')
  await drawer().getByRole('button', { name: '返回换图记录' }).click()
  activity('running')
  await row().getByText('图片修改中', { exact: true }).waitFor()
  assert.ok(lists >= 2)
  await shot('running-list')
  await row().getByRole('button', { name: '查看详情' }).click()
  await drawer().getByText('图片修改中', { exact: true }).waitFor()
  assert.equal(await drawer().getByText('当前 V1 · 点击放大', { exact: true }).count(), 1)
  checks.push('关闭详情后列表轮询显示执行；重开卡片显示同状态且保留V1')
  await page.setViewportSize({ width: 390, height: 844 })
  const tag = drawer().locator('.cli-activity-tag')
  await tag.scrollIntoViewIfNeeded()
  assert.equal(await tag.evaluate(el => { const r = el.getBoundingClientRect(), p = el.closest('.el-card').getBoundingClientRect(); return r.left >= p.left && r.right <= p.right && r.top >= p.top && r.bottom <= p.bottom }), true)
  await shot('running-narrow')
  await page.setViewportSize({ width: 1440, height: 1000 })
  activity('uncertain')
  await drawer().getByRole('button', { name: '刷新详情' }).click()
  await drawer().locator('.cli-activity-tag').hover()
  await page.getByRole('tooltip').getByText('执行结果待核实，确认结束前不可删除任务', { exact: true }).waitFor()
  activity('idle')
  await drawer().getByText('图片修改中', { exact: true }).waitFor({ state: 'hidden' })
  await drawer().getByRole('button', { name: '返回换图记录' }).click()
  await row().getByText('图片修改中', { exact: true }).waitFor({ state: 'hidden' })
  checks.push('未知状态保持提示；轮次结束后列表和卡片标签由现有轮询自动消失')
  await row().getByRole('button', { name: '删除', exact: true }).click()
  const confirm = page.getByRole('dialog', { name: '永久删除换图任务', exact: true })
  await confirm.getByText(new RegExp(task.name)).waitFor()
  await confirm.getByText(/Codex CLI会话和工作资料，无法恢复/).waitFor()
  await confirm.getByRole('button', { name: '取消', exact: true }).click()
  assert.equal(deletes, 0)
  await row().getByRole('button', { name: '删除', exact: true }).click()
  await confirm.getByRole('button', { name: '确认删除', exact: true }).click()
  await row().getByRole('button', { name: '删除中…', exact: true }).waitFor()
  assert.equal(await page.getByText(/已永久删除/).count(), 0)
  assert.equal(deletes, 1)
  await refresh()
  await page.locator('.el-loading-mask:visible').first().waitFor({ state: 'hidden' })
  assert.ok(receipts.some(reply => reply.method === 'GET' && reply.state === 'deleting' && reply.message === null))
  assert.equal(await page.getByText(/删除状态尚未确认/).count(), 0)
  deletion = { state: 'failed', message: '删除未完成，请重试' }; task.deletionState = 'failed'; task.canDelete = true; task.deleteBlockedReason = null; task.deletionError = deletion.message
  await refresh()
  await row().getByRole('button', { name: '重试删除' }).waitFor()
  await shot('delete-failed')
  const retryButton = row().getByRole('button', { name: '重试删除', exact: true })
  assert.equal(await retryButton.isVisible(), true)
  assert.equal(await retryButton.evaluate(el => { const r = el.getBoundingClientRect(), p = el.closest('td').getBoundingClientRect(); return r.left >= p.left && r.right <= p.right && r.top >= p.top && r.bottom <= p.bottom }), true)
  await row().getByText('删除未完成，请重试', { exact: true }).waitFor()
  assert.equal(await page.getByText(/已永久删除/).count(), 0)
  assert.ok(receipts.some(reply => reply.method === 'GET' && reply.state === 'failed' && reply.message === deletion.message))
  await row().getByRole('button', { name: '重试删除' }).click()
  deletion = { state: 'deleting', message: null }
  await confirm.getByRole('button', { name: '确认删除', exact: true }).click()
  await row().getByRole('button', { name: '删除中…', exact: true }).waitFor()
  assert.equal(deletes, 2)
  assert.equal(await page.getByText(/已永久删除/).count(), 0)
  await page.reload()
  await row().getByRole('button', { name: '删除中…', exact: true }).waitFor()
  deletion = { state: 'deleted', message: {} }
  await refresh()
  await page.getByText(/删除状态尚未确认/).waitFor()
  assert.equal(await row().count(), 1)
  assert.equal(await page.getByText(/已永久删除/).count(), 0)
  checks.push('非法deleted回执保留任务并提示尚未确认，不触发假成功')
  deletion = { state: 'deleted', message: null }; deleted = true
  await page.getByText(`“${task.name}”已永久删除`, { exact: true }).waitFor()
  assert.equal(await row().count(), 0)
  assert.equal(await page.getByText(/删除状态尚未确认/).count(), 0)
  assert.equal(receipts.filter(reply => reply.method === 'DELETE' && reply.status === 202 && reply.state === 'deleting' && reply.message === null).length, 2)
  assert.ok(receipts.some(reply => reply.method === 'GET' && reply.state === 'deleted' && reply.message === null))
  checks.push('真实完整DTO的DELETE 202、GET deleting/failed/deleted通过：确认具名永久范围，取消无请求，受理不成功，失败可重试，刷新恢复，最终成功移除')
  await shot('deleted')
  assert.deepEqual(errors, [])
  await writeFile(resolve(output, 'report.json'), JSON.stringify({ checks, lists, deletes, receipts, errors }, null, 2))
  console.log(JSON.stringify({ checks, lists, deletes, receipts, errors }, null, 2))
} finally { await context.close(); await browser.close() }
