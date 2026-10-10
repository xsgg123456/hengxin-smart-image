import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.API_UI_URL || 'http://127.0.0.1:3024/'
const output = path.resolve('../../output/playwright/legacy-retention')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await context.newPage(), errors = [], materialRequests = [], checks = []
page.setDefaultTimeout(15000)
page.on('pageerror', error => errors.push(error.message))
const uuid = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
const image = Buffer.from(await page.evaluate(() => {
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = 800
  const ctx = canvas.getContext('2d'); ctx.fillStyle = '#d8e5ef'; ctx.fillRect(0, 0, 800, 800)
  ctx.fillStyle = '#206a73'; ctx.fillRect(250, 130, 300, 540)
  return canvas.toDataURL().split(',')[1]
}), 'base64')
const picture = n => ({ name: `第4张-V${n}.png`, fileId: uuid(n), url: `/api/v1/files/${uuid(n)}/content` })
const time = '2026-09-24T08:29:07Z'
const rounds = [1, 2].map(n => ({ id: `round-${n}`, taskId: 'fixture-cli', operatorId: 'browser-user', target: 0,
  note: n === 1 ? '历史修改意见' : '手机壁纸重新更改 <script>不执行</script>', state: '待查看',
  baseVersion: n, baseVersionId: `version-${n}`, createdAt: time, startedAt: time, finishedAt: time, error: null }))
const task = { id: 'fixture-cli', name: '轮次材料隔离验收', mode: 'wallpaper', template: '', skillVersionId: 'skill-1',
  ownerId: 'browser-user', sessionId: 'session-1', state: '待查看', progress: 100, images: [picture(3)], sources: [picture(8)],
  feedback: [], time, archived: false, currentRoundId: 'round-2', executionSource: 'cli' }
const detail = { task, rounds, slots: [{ slot: 0, currentVersionId: 'version-3', error: null,
  versions: [1, 2, 3].map(n => ({ ...picture(n), id: `version-${n}`, version: n, roundId: n === 3 ? 'round-2' : 'round-1', createdAt: time })) }],
  executionControl: { canRevise: true, canRetry: false, blockedReason: null } }
task.retention = { status: 'active', lastActivityAt: time, expiresAt: '2026-10-10T00:00:00Z', cacheClearedAt: null }
const requests = []
await context.route('**/*', async route => {
  const req = route.request(), u = new URL(req.url()), p = u.pathname
  if (u.origin !== new URL(base).origin) return route.abort()
  if (!p.startsWith('/api/')) return route.continue()
  if (p.endsWith('/content')) return route.fulfill({ contentType: 'image/png', body: image })
  let body
  if (p.endsWith('/auth/me')) body = { id: 'browser-user', name: '隔离测试', role: 'super_admin', status: 'active' }
  else if (p.endsWith('/rounds') && req.method() === 'POST') {
    requests.push(req.postDataJSON())
    return route.fulfill({ status: 409, contentType: 'application/json', body: JSON.stringify({ code: 'CONFLICT', message: '隔离测试提交被拒绝，意见保留' }) })
  } else if (p === '/api/v1/tasks/fixture-cli') body = detail
  else if (p === '/api/v1/tasks') body = { items: [task], total: 1, page: 1, pageSize: 20, stats: { total: 1, processing: 0, ready: 1, archived: 0 } }
  else { errors.push('Unexpected API: ' + p); return route.fulfill({ status: 501, body: '{}' }) }
  return route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
})
try {
  await page.goto(base + '#/tasks/index'); await page.getByText(task.name, { exact: true }).click()
  const drawer = page.locator('.hx-detail')
  await drawer.getByText(/CLI 会话闲置 24 小时清缓存/).waitFor()
  await drawer.getByRole('button', { name: '整套修改', exact: true }).click()
  await page.locator('#revision-note').fill('旧会话草稿')
  await page.getByRole('dialog', { name: '整套修改意见', exact: true }).getByRole('button', { name: '取消', exact: true }).click()
  await page.getByRole('dialog', { name: '整套修改意见', exact: true }).waitFor({ state: 'hidden' })
  await page.keyboard.press('Escape'); await drawer.waitFor({ state: 'hidden' })
  task.retention.status = 'expired'; task.sessionId = null
  detail.executionControl.blockedReason = '会话历史已清理，新修改将开启新会话'
  await page.getByText(task.name, { exact: true }).click()
  await drawer.getByText('会话历史已清理，新修改将开启新会话', { exact: true }).waitFor()
  assert.equal(await drawer.locator('.hx-result-grid img').count(), 1)
  assert.equal(await drawer.locator('.hx-result-grid img').getAttribute('src'), picture(3).url)
  await drawer.getByRole('button', { name: '整套修改', exact: true }).click()
  assert.equal(await page.locator('#revision-note').inputValue(), '')
  await page.locator('#revision-note').fill('过期后的新意见')
  await page.getByRole('button', { name: '提交修改', exact: true }).click()
  const confirmation = page.locator('.el-message-box')
  await confirmation.getByText('开启新会话', { exact: true }).first().waitFor()
  assert.equal(requests.length, 0)
  await confirmation.getByRole('button', { name: '取消', exact: true }).click()
  assert.equal(await page.locator('#revision-note').inputValue(), '过期后的新意见')
  await page.getByRole('button', { name: '提交修改', exact: true }).click()
  await confirmation.getByRole('button', { name: '开启新会话', exact: true }).click()
  await page.getByText('隔离测试提交被拒绝，意见保留', { exact: true }).last().waitFor()
  assert.equal(requests.length, 1); assert.equal(requests[0].restartExpired, true)
  assert.equal(requests[0].note, '过期后的新意见')
  assert.equal(await page.locator('#revision-note').inputValue(), '过期后的新意见')
  await page.screenshot({ path: path.join(output, 'expired-restart.png') })
  assert.deepEqual(errors, [])
  checks.push('常驻保留规则、过期正式图保留、旧意见草稿清空、取消确认不提交、新会话显式字段、失败意见保留')
  await writeFile(path.join(output, 'checks.json'), JSON.stringify({ passed: true, checks, requests, errors }, null, 2))
  console.log(JSON.stringify({ passed: true, checks }))
} catch (error) { await page.screenshot({ path: path.join(output, 'failure.png') }); throw error }
finally { await context.close(); await browser.close() }
