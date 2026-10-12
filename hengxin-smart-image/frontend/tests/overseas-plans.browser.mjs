import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3015'
const browser = await chromium.launch({ headless: true }), context = await browser.newContext({ viewport: { width: 1280, height: 900 } }), page = await context.newPage()
page.setDefaultTimeout(15000)
let mode = 'normal', caps = ['task.read', 'task.design'], version = 2, status = 'plan', calls = [], events = 0
const errors = [], picture = { title: '主图建议', description: '保留完整设计说明\n第二行说明', prompt: '完整生成提示词', width: 1024, height: 1024 }
const plan = (v, state = 'ready') => ({ id: `p${v}`, taskId: 't1', version: v, status: state, jobId: `j${v}`, feedback: v > 1 ? '调整排版' : '', content: state === 'ready' || state === 'confirmed' ? { skus: [{ code: 'A', pictures: [picture] }, { code: 'B', pictures: [{ ...picture, title: 'B主图' }] }] } : null, createdAt: '2026-10-12' })
let items = [plan(2), plan(1)]
const task = () => ({ id: 't1', name: '方案验证任务', productName: '手机壳', brand: 'HX', platform: 'Amazon', market: '美国', remarks: '', skus: [{ code: 'A' }, { code: 'B' }], status, version, createdAt: '2026-10-12', updatedAt: '2026-10-12', createdBy: { id: 'actor', name: '测试' }, designer: { id: 'actor', name: '设计', status: 'active', eligible: true }, capabilities: caps, events: [] })
const button = name => page.getByRole('button', { name, exact: true }), opinion = () => page.getByRole('textbox', { name: '方案修改意见' })
async function visit() { await page.goto(`${base}/#/overseas/tasks/t1`); await page.reload(); await button('刷新方案').waitFor() }
async function unclipped(locator) { await locator.scrollIntoViewIfNeeded(); assert.deepEqual(await locator.evaluate(el => { const b = el.getBoundingClientRect(), out = []; for (let p = el.parentElement; p; p = p.parentElement) { const r = p.getBoundingClientRect(), s = getComputedStyle(p); if (/(auto|scroll|hidden|clip)/.test(s.overflowX) && (b.left < r.left - 1 || b.right > r.right + 1)) out.push('x'); if (/(auto|scroll|hidden|clip)/.test(s.overflowY) && (b.top < r.top - 1 || b.bottom > r.bottom + 1)) out.push('y') } return out }), []) }
page.on('pageerror', e => errors.push(e.message))
try {
  await context.route(`${base}/api/**`, async route => {
    const req = route.request(), p = new URL(req.url()).pathname; let body = {}, code = 200
    if (p.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (p === '/api/identity/v1/me') body = { name: '测试' }
    else if (p.endsWith('/tickets')) body = { ticket: 'test' }
    else if (p === '/api/v1/auth/identity/session') code = 403
    else if (p.includes('/auth/')) body = { id: 'actor', name: '测试', status: 'active', roles: ['designer'], capabilities: caps }
    else if (p.endsWith('/execution-events')) body = { items: events > Number(new URL(req.url()).searchParams.get('after')) ? [{ id: events, jobId: 'j1', status: 'succeeded', message: '分析完成', createdAt: '2026-10-12' }] : [], cursor: events }
    else if (p.endsWith('/jobs')) body = { items: [] }
    else if (p.endsWith('/materials')) body = []
    else if (p.endsWith('/pictures')) body = { items: [], taskVersion: 1 }
    else if (p.endsWith('/plans')) { if (mode === 'denied') code = 403; if (mode === 'readfail') code = 500; body = { items, taskVersion: version } }
    else if (p.endsWith('/analysis') || p.endsWith('/confirm')) {
      calls.push({ p, body: req.postDataJSON(), key: req.headers()['idempotency-key'] })
      if (mode === 'unknown') { await route.abort(); return }
      if (mode === 'conflict') { version++; code = 409 }
      else { version++; status = p.endsWith('/confirm') ? 'generating' : 'analyzing'; items = p.endsWith('/confirm') ? [plan(2, 'confirmed'), plan(1)] : [plan((items[0]?.version || 0) + 1, 'pending'), ...items] }
      body = task()
    }
    else if (p.endsWith('/tasks/t1')) body = task()
    else throw Error(`Unexpected ${p}`)
    await route.fulfill({ status: code, contentType: 'application/json', body: JSON.stringify(body) }).catch(() => {})
  })
  await visit(); await opinion().waitFor(); assert.equal(await button('不通过，重新分析').isDisabled(), true)
  await page.getByRole('tab', { name: 'B', exact: true }).click(); await page.getByRole('heading', { name: 'B主图' }).waitFor()
  await page.locator('.el-select').filter({ has: page.getByRole('combobox', { name: '方案版本' }) }).click(); await page.getByRole('option', { name: '方案 v1 · 待确认（历史只读）', exact: true }).click(); assert.equal(await button('确认方案，开始生图').count(), 0)
  await page.locator('.el-select').filter({ has: page.getByRole('combobox', { name: '方案版本' }) }).click(); await page.getByRole('option', { name: '方案 v2 · 待确认（最新）', exact: true }).click()
  await opinion().fill('保留我的意见'); mode = 'conflict'; await button('确认方案，开始生图').click(); await page.getByText('任务或资料已发生变化，请刷新后重试。').waitFor(); assert.equal(await opinion().inputValue(), '保留我的意见')
  mode = 'unknown'; await button('不通过，重新分析').click(); await button('核实并重试原请求').waitFor(); const key = calls.at(-1).key; assert.equal(await opinion().isDisabled(), true)
  mode = 'normal'; await button('核实并重试原请求').click(); await page.getByText('分析任务已提交，正在等待执行结果。排队与执行状态见下方执行记录。').waitFor(); assert.equal(calls.at(-1).key, key)
  items = [plan(3), plan(2), plan(1)]; status = 'plan'; version++; events++; await button('刷新执行状态').click(); await opinion().waitFor(); await opinion().fill('自动刷新不打断编辑'); events++; await button('刷新执行状态').click(); assert.equal(await opinion().inputValue(), '自动刷新不打断编辑')
  await mkdir('../../output/playwright/phase22', { recursive: true }); await page.screenshot({ path: '../../output/playwright/phase22/plans-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 }); await page.waitForTimeout(700); await unclipped(button('确认方案，开始生图')); await unclipped(opinion()); await page.screenshot({ path: '../../output/playwright/phase22/plans-mobile.png', fullPage: true })
  await button('确认方案，开始生图').click(); await page.getByText('生成中', { exact: true }).waitFor(); assert.equal(await opinion().count(), 0)
  items = [plan(4, 'failed'), plan(3)]; status = 'analysisFailed'; version++; await visit(); await button('重试分析').waitFor(); await button('重试分析').click(); await page.getByText('分析任务已提交，正在等待执行结果。排队与执行状态见下方执行记录。').waitFor()
  items = [plan(5, 'uncertain')]; await visit(); await page.getByText('分析结果尚未确认，请联系管理员核实，切勿重复提交。').waitFor(); assert.equal(await button('重试分析').count(), 0)
  items = []; status = 'created'; await visit(); await page.getByText('暂无图片排版方案。').waitFor(); mode = 'readfail'; await button('刷新方案').click(); await page.getByText('服务暂不可用，请重试').waitFor(); mode = 'normal'; await button('刷新方案').click(); await page.getByText('暂无图片排版方案。').waitFor()
  caps = ['task.read']; status = 'plan'; items = [plan(2)]; await visit(); await page.getByText('当前为只读视角，方案处理需由负责设计或设计主管操作。').waitFor(); assert.equal(await button('确认方案，开始生图').count(), 0)
  mode = 'denied'; await button('刷新方案').click(); await page.getByRole('heading', { name: '企业身份已连接' }).waitFor(); assert.equal(await page.locator('.plans-panel').count(), 0)
  assert.deepEqual(errors, []); console.log('PASS plans: history; SKU; feedback; conflict refresh; unknown same-key retry; execution refresh preserves edits; confirm; failed retry; uncertain; empty; read failure; narrow clipping; readonly; revoke')
} catch (e) { console.error(await page.locator('body').innerText()); throw e } finally { await browser.close() }
