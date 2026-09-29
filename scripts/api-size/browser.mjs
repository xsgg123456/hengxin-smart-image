import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.API_UI_URL || 'http://127.0.0.1:3018/'
const output = path.resolve('output/playwright/api-size')
await mkdir(output, { recursive: true })
const pic = (id, width, height) => ({ fileId: id, name: `${id}.png`, url: `/fixture/${id}.svg`, width, height })
const source = pic('source', 790, 1166), v1 = pic('v1', 832, 1248), v2 = pic('v2', 790, 1166)
const task = { id: 'size-fixture', name: 'API 尺寸隔离验收', prompt: '隔离测试', created: '2026-09-29T08:00:00Z',
  status: 'succeeded', operator: '隔离测试', batch: { current: 1, total: 1, running: 0 }, material: pic('material', 800, 800),
  events: [], error: null, metrics: { requestCount: 2, retryCount: 0, elapsedSeconds: 5 },
  items: [{ id: 'item-1', position: 1, source, state: 'succeeded', retries: 0, nextAttemptAt: null,
    result: v2, error: null, currentVersion: 2, versions: [v1, v2].map((picture, i) => ({ number: i + 1, picture,
      created: '2026-09-29T08:00:00Z', operator: '隔离测试', text: '', annotation: null, baseVersion: null })), revision: null }] }
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await context.newPage(), errors = [], checks = []
page.on('pageerror', e => errors.push(e.message))
page.setDefaultTimeout(20000)
await context.route('**/*', async route => {
  const u = new URL(route.request().url())
  if (u.origin !== new URL(base).origin) return route.abort()
  if (u.pathname.startsWith('/fixture/')) {
    const id = u.pathname.split('/').at(-1).split('.')[0]
    const picture = [source, v1, v2, task.material].find(p => p.fileId === id)
    const width = picture?.width || 790, height = picture?.height || 1166
    return route.fulfill({ contentType: 'image/svg+xml', body: `<svg xmlns="http://www.w3.org/2000/svg" width="${width}" height="${height}"><rect width="100%" height="100%" fill="#e8f2ff"/><text x="30" y="70" font-size="28">${id} — ${width} x ${height}</text></svg>` })
  }
  if (!u.pathname.startsWith('/api/')) return route.continue()
  let body
  if (u.pathname === '/api/v1/auth/me') body = { id: 'browser-user', name: '隔离测试', role: 'super_admin', status: 'active' }
  else if (u.pathname.endsWith('/status')) body = { enabled: true, paused: false, reason: null }
  else if (u.pathname.endsWith('/tasks/' + task.id)) body = task
  else if (u.pathname.endsWith('/tasks')) body = { items: [{
    id: task.id, name: task.name, created: task.created, status: task.status,
    operator: task.operator, cover: task.items[0].result,
    counts: { total: 1, success: 1, failed: 0, uncertain: 0 }, batch: task.batch
  }], total: 1, page: 1, pageSize: 20 }
  else { errors.push('Unexpected API: ' + u.pathname); return route.fulfill({ status: 501, body: '{}' }) }
  return route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
})
async function screenshot(name) { await page.screenshot({ path: path.join(output, name + '.png'), animations: 'disabled' }) }
async function openComparison() {
  await page.getByRole('button', { name: '查看原图 / 对照成品', exact: true }).click()
  const dialog = page.getByRole('dialog', { name: '原图与成品对照 · 第 1 张', exact: true })
  await dialog.waitFor()
  return dialog
}
try {
  await page.goto(base + '#/api-image-edits/records?task=' + task.id)
  await page.getByRole('button', { name: '查看原图 / 对照成品', exact: true }).waitFor()
  await page.getByRole('row').filter({ hasText: task.name }).waitFor()
  assert.equal(await page.getByText(/服务返回的数据不/).count(), 0)
  await screenshot('baseline-detail')
  let dialog = await openComparison()
  assert.equal(await dialog.getByText('790 × 1166 px', { exact: true }).count(), 2)
  assert.equal(await dialog.getByText('尺寸不一致', { exact: true }).count(), 0)
  await screenshot('matching-wide')
  checks.push('当前PNG成品与原图均显示790×1166，不用显示框尺寸')
  await dialog.getByRole('button', { name: '关闭对照', exact: true }).click()
  await page.getByRole('button', { name: '历史版本 · 2', exact: true }).click()
  const history = page.getByRole('dialog', { name: '历史版本 · 原图 1', exact: true })
  await history.getByRole('button').filter({ has: page.getByText('V1', { exact: true }) }).click()
  await history.getByText('832 × 1248 px', { exact: true }).waitFor()
  await history.getByText('尺寸不一致', { exact: true }).waitFor()
  await screenshot('historical-mismatch')
  await page.setViewportSize({ width: 390, height: 844 })
  for (const caption of await history.locator('.version-comparison h3').all()) {
    await caption.scrollIntoViewIfNeeded()
    assert.equal(await caption.evaluate(el => {
      const r = el.getBoundingClientRect(), parent = el.closest('.version-layout').getBoundingClientRect()
      return r.left >= parent.left - 1 && r.right <= parent.right + 1 && r.top >= parent.top - 1 && r.bottom <= parent.bottom + 1
    }), true)
  }
  assert.equal(await history.evaluate(el => el.scrollWidth > el.clientWidth + 1), false)
  await screenshot('historical-narrow')
  checks.push('历史弹窗390px所选/当前尺寸标题可滚动完整查看')
  await page.setViewportSize({ width: 1440, height: 1000 })
  await history.getByRole('button').filter({ has: page.getByText('V2', { exact: true }) }).click()
  assert.equal(await history.getByText('790 × 1166 px', { exact: true }).count(), 2)
  await history.getByText('尺寸不一致', { exact: true }).waitFor({ state: 'hidden' })
  await history.getByRole('button', { name: '关闭', exact: true }).click()
  checks.push('历史V1/当前V2尺寸与不一致提示随选择即时切换')
  task.items[0].currentVersion = 1; task.items[0].result = v1
  await page.getByRole('button', { name: '刷新详情', exact: true }).click()
  await page.getByText('当前 V1 · 点击放大', { exact: true }).waitFor()
  dialog = await openComparison()
  await dialog.getByText('832 × 1248 px', { exact: true }).waitFor()
  await dialog.getByText('尺寸不一致', { exact: true }).waitFor()
  await page.setViewportSize({ width: 390, height: 844 })
  await screenshot('mismatch-narrow')
  const overflow = await dialog.evaluate(el => el.scrollWidth > el.clientWidth + 1)
  assert.equal(overflow, false)
  for (const caption of await dialog.locator('section > p').all()) {
    await caption.scrollIntoViewIfNeeded()
    assert.equal(await caption.evaluate(el => {
      const r = el.getBoundingClientRect(), grid = el.closest('.comparison-grid').getBoundingClientRect()
      return r.left >= grid.left - 1 && r.right <= grid.right + 1 && r.top >= grid.top - 1 && r.bottom <= grid.bottom + 1
    }), true)
  }
  checks.push('当前版本刷新更新，390px窄屏左右标题滚动可见且无横向裁切')
  await dialog.getByRole('button', { name: '关闭对照', exact: true }).click()
  await page.setViewportSize({ width: 1440, height: 1000 })
  delete source.width; delete source.height; delete v1.width; delete v1.height
  await page.getByRole('button', { name: '刷新详情', exact: true }).click()
  dialog = await openComparison()
  assert.equal(await dialog.getByText('尺寸未知', { exact: true }).count(), 2)
  assert.equal(await dialog.getByText('尺寸不一致', { exact: true }).count(), 0)
  await screenshot('legacy-unknown')
  checks.push('历史缺少元数据时显示未知，不读取图片自然尺寸冒充记录')
  await dialog.getByRole('button', { name: '关闭对照', exact: true }).click()
  await page.goto(base + '#/api-image-edits/create')
  await page.getByText('按原图尺寸 · PNG', { exact: true }).waitFor()
  await screenshot('create-specification')
  checks.push('创建页成品规格与动态尺寸PNG交付一致')
  assert.deepEqual(errors, [])
  await writeFile(path.join(output, 'result.json'), JSON.stringify({ checks, errors }, null, 2))
  console.log(JSON.stringify({ checks, errors }, null, 2))
} finally { await context.close(); await browser.close() }
