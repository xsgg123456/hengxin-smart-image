import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3015'
const browser = await chromium.launch({ headless: true }), context = await browser.newContext({ viewport: { width: 1280, height: 900 } }), page = await context.newPage()
page.setDefaultTimeout(15000)
let mode = 'normal', state = 'queued', caps = ['task.read', 'task.design', 'task.reassign'], cancelCount = 0, eventId = 1, reads = 0
const errors = [], cursors = [], job = () => ({ id: 'j1', taskId: 't1', kind: 'analysis', status: state, version: eventId, error: null, createdAt: '2026-10-12', startedAt: null, completedAt: null })
const task = () => ({ id: 't1', name: '执行验证任务', productName: '手机壳', brand: 'HX', platform: 'Amazon', market: '美国', remarks: '', skus: [{ code: 'A' }], status: 'submitted', version: 1, createdAt: '2026-10-12', updatedAt: '2026-10-12', createdBy: { id: 'actor', name: '测试' }, designer: { id: 'actor', name: '测试设计', status: 'active', eligible: true }, capabilities: caps, events: [] })
const button = name => page.getByRole('button', { name, exact: true })
async function unclipped(locator) {
  await locator.scrollIntoViewIfNeeded()
  assert.deepEqual(await locator.evaluate(el => { const b = el.getBoundingClientRect(), out = []; for (let p = el.parentElement; p; p = p.parentElement) { const r = p.getBoundingClientRect(), s = getComputedStyle(p); if (/(auto|scroll|hidden|clip)/.test(s.overflowX) && (b.left < r.left - 1 || b.right > r.right + 1)) out.push('x'); if (/(auto|scroll|hidden|clip)/.test(s.overflowY) && (b.top < r.top - 1 || b.bottom > r.bottom + 1)) out.push('y') } return out }), [])
}
page.on('pageerror', e => errors.push(e.message))
try {
  await context.route(`${base}/api/**`, async route => {
    const req = route.request(), url = new URL(req.url()), p = url.pathname
    let status = 200, body = {}
    if (p.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (p === '/api/identity/v1/me') body = { name: '测试' }
    else if (p.endsWith('/tickets')) body = { ticket: 'test' }
    else if (p === '/api/v1/auth/identity/session') status = 403
    else if (p.includes('/auth/')) body = { id: 'actor', name: '测试', status: 'active', roles: ['designer'], capabilities: caps }
    else if (p.endsWith('/execution-events')) {
      reads++; const after = Number(url.searchParams.get('after')); cursors.push(after)
      if (mode === 'network') { await route.abort(); return }
      if (mode === 'denied' || mode === '401') status = mode === '401' ? 401 : 403
      body = { items: mode !== 'empty' && after < eventId ? [{ id: eventId, jobId: 'j1', status: state, message: `记录${eventId}`, createdAt: '2026-10-12' }] : [], cursor: mode === 'empty' ? after : Math.max(after, eventId) }
    } else if (p.endsWith('/jobs')) body = { items: mode === 'empty' ? [] : [job()] }
    else if (p.endsWith('/cancel')) {
      cancelCount++; assert.equal(req.headers()['x-hx-request'], '1'); assert.equal(req.postDataJSON().version, eventId)
      eventId++; state = mode === 'conflict' ? 'running' : 'cancelling'
      if (mode === 'conflict') status = 409
      if (mode === 'cancel-network') { await route.abort(); return }
      body = job()
    } else if (p.endsWith('/assignment')) { mode = 'denied'; caps = []; status = 403 }
    else if (p.endsWith('/task-designers')) body = { items: [{ id: 'd2', name: '另一设计', department: '海外' }], total: 1, page: 1, pageSize: 20 }
    else if (p.endsWith('/materials')) body = []
    else if (p.endsWith('/tasks/t1')) body = task()
    else if (p.endsWith('/tasks')) body = { items: [task()], total: 1, page: 1, pageSize: 20 }
    else throw Error(`Unexpected ${p}`)
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) }).catch(() => {})
  })
  mode = 'empty'; await page.goto(`${base}/#/overseas/tasks/t1`); await page.getByText('暂无执行记录，尚未开始分析或生成。').waitFor(); await unclipped(page.getByText('暂无执行记录，尚未开始分析或生成。'))
  mode = 'normal'; await button('刷新执行状态').click(); await button('停止执行').waitFor(); await button('执行记录').click(); await page.getByText('2026-10-12 · 记录1', { exact: true }).waitFor()
  mode = 'network'; await button('刷新执行状态').click(); await page.getByText('服务连接失败，请稍后重试').waitFor(); assert.equal(cursors.at(-1), 1)
  mode = 'normal'; eventId = 2; state = 'running'; await button('刷新执行状态').click(); await page.getByText('2026-10-12 · 记录2', { exact: true }).waitFor(); assert.equal(await page.getByText('2026-10-12 · 记录1', { exact: true }).count(), 1)
  await button('停止执行').click(); await button('继续执行').click(); assert.equal(cancelCount, 0)
  await button('停止执行').click(); await button('确认停止').waitFor(); await page.goto(base + '/#/overseas/tasks'); await button('查看详情').waitFor(); await button('确认停止').waitFor({ state: 'hidden' }); await button('查看详情').click(); await button('停止执行').waitFor(); assert.equal(cancelCount, 0)
  mode = 'conflict'; await button('停止执行').click(); await button('确认停止').click(); await page.getByText('执行状态已变化，已重新读取，请核对后操作。').waitFor()
  mode = 'normal'; await button('刷新执行状态').click(); await button('停止执行').click(); await button('确认停止').click(); await page.getByText('正在停止执行', { exact: true }).waitFor(); assert.equal(cancelCount, 2)
  state = 'running'; eventId++; mode = 'normal'; await button('刷新执行状态').click(); mode = 'cancel-network'; await button('停止执行').click(); await button('确认停止').click(); await page.getByText('停止请求结果尚未确认，正在核实最新状态，请勿重复提交。').waitFor(); assert.equal(cancelCount, 3); assert.equal(await button('停止执行').count(), 0); mode = 'normal'
  state = 'uncertain'; eventId++; await button('刷新执行状态').click(); const warning = page.getByText('执行结果尚未确认，请联系管理员核实，切勿重复执行。'); await warning.waitFor(); assert.equal(await button('停止执行').count(), 0)
  await mkdir('../../output/playwright/phase21', { recursive: true }); await page.screenshot({ path: '../../output/playwright/phase21/execution-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 }); await page.waitForTimeout(700); await unclipped(warning); await unclipped(button('刷新执行状态')); await page.screenshot({ path: '../../output/playwright/phase21/execution-mobile.png' })
  await button('返回任务列表').click(); const before = reads; await page.waitForTimeout(2300); assert.equal(reads, before)
  await button('查看详情').click(); await warning.waitFor(); await button('改派设计').click(); await page.locator('input[aria-label="负责设计"]:not([disabled])').waitFor(); await page.locator('.el-select').filter({ has: page.getByRole('combobox', { name: '负责设计', exact: true }) }).click(); await page.getByRole('option', { name: '另一设计 · 海外', exact: true }).click(); await button('确认改派').click(); await page.getByRole('heading', { name: '企业身份已连接' }).waitFor(); assert.equal(await warning.count(), 0)
  mode = 'normal'; caps = ['task.read']; await page.goto(`${base}/#/overseas/tasks/t1`); await page.reload(); await warning.waitFor(); state = 'running'; eventId++; await button('刷新执行状态').click(); assert.equal(await button('停止执行').count(), 0)
  mode = 'denied'; caps = []; await button('刷新执行状态').click(); await page.getByRole('heading', { name: '企业身份已连接' }).waitFor(); assert.equal(await page.locator('.execution-panel').count(), 0)
  mode = 'normal'; caps = ['task.read']; await page.goto(`${base}/#/overseas/tasks/t1`); await page.reload(); await button('刷新执行状态').waitFor(); mode = '401'; await button('刷新执行状态').click(); await page.getByText('身份已失效，请重新登录').waitFor(); assert.equal(await page.locator('.execution-panel').count(), 0)
  assert.deepEqual(errors, []); console.log('PASS execution: empty; cursor resume; cancel confirmation/conflict/success; uncertain; narrow clipping; route cleanup; reassign/revoke; 401/403; read-only')
} catch (error) { console.error(await page.locator('body').innerText()); console.error({ errors, mode, cursors }); throw error } finally { await browser.close() }






