import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3015'
const browser = await chromium.launch({ headless: true }), context = await browser.newContext({ viewport: { width: 1280, height: 900 } }), page = await context.newPage()
page.setDefaultTimeout(15000)
let mode = 'normal', caps = ['task.read', 'task.design'], version = 2, status = 'generationFailed', calls = [], queries = []
const errors = [], url = (id, v) => `/api/overseas/v1/pictures/${id}/versions/${v}/content`
const make = (id, sku, v = 1) => ({ id, taskId: 't1', sku, position: 0, title: `${sku}主图`, version: v, approved: false, status: v ? 'ready' : 'failed', url: v ? url(id, v) : null, width: v ? 32 : null, height: v ? 32 : null, history: v ? [{ version: v, url: url(id, v), width: 32, height: 32, note: '完整历史意见', createdAt: '2026-10-12' }] : [] })
let items = [make('p1', 'A'), make('p2', 'B', 0)]
const task = () => ({ id: 't1', name: '图片验证任务', productName: '手机壳', brand: 'HX', platform: 'Amazon', market: '美国', remarks: '', skus: [{ code: 'A' }, { code: 'B' }], status, version, createdAt: '2026-10-12', updatedAt: '2026-10-12', createdBy: { id: 'actor', name: '测试' }, designer: { id: 'actor', name: '设计', status: 'active', eligible: true }, capabilities: caps, events: [] })
const button = name => page.getByRole('button', { name, exact: true }), opinion = () => page.getByRole('textbox', { name: '整体补充要求' })
async function visit(path = '/overseas/tasks/t1') { await page.goto(`${base}/#${path}`); await page.reload(); await page.getByRole('heading', { name: path.includes('archive') ? '成品库' : '图片审核', exact: true }).waitFor(); if (page.viewportSize().width < 800) { await page.waitForFunction(() => !document.querySelector('.menu-left-open') && document.getAnimations().every(a => a.playState !== 'running')) } }
async function unclipped(locator) { await locator.scrollIntoViewIfNeeded(); assert.deepEqual(await locator.evaluate(el => { const b = el.getBoundingClientRect(), out = []; for (let p = el.parentElement; p; p = p.parentElement) { const r = p.getBoundingClientRect(), s = getComputedStyle(p); if (/(auto|scroll|hidden|clip)/.test(s.overflowX) && (b.left < r.left - 1 || b.right > r.right + 1)) out.push('x'); if (/(auto|scroll|hidden|clip)/.test(s.overflowY) && (b.top < r.top - 1 || b.bottom > r.bottom + 1)) out.push('y') } return out }), []) }
page.on('pageerror', e => errors.push(e.message))
try {
 await context.route(`${base}/api/**`, async route => {
  const req = route.request(), u = new URL(req.url()), p = u.pathname; let body = {}, code = 200
  if (p.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
  else if (p === '/api/identity/v1/me') body = { name: '测试', sessionId: 'identity-test' }
  else if (p.endsWith('/tickets')) body = { ticket: 'test' }
  else if (p === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
  else if (p.includes('/auth/')) { body = { id: 'actor', name: '测试', identitySessionId: 'identity-test', status: 'active', roles: ['designer'], capabilities: caps }; if (p.endsWith('/access')) body = { state: 'allowed', member: body } }
  else if (p.endsWith('/execution-events')) body = { items: [], cursor: 0 }
  else if (p.endsWith('/jobs')) body = { items: [] }
  else if (p.endsWith('/materials')) body = []
  else if (p.endsWith('/plans')) body = { items: [], taskVersion: version }
  else if (p.endsWith('/pictures')) { if (mode === 'denied') code = 403; if (mode === 'readfail') code = 500; body = { items, taskVersion: version } }
  else if (p.endsWith('/content')) { await route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAACAAAAAgCAIAAAD8GO2jAAAAJklEQVR4nO3NMQEAAAgDILV/51nBzwciQKnmfOr1AQAAAAAAAAAA4G8WcQEBR3rH1QAAAABJRU5ErkJggg==', 'base64') }); return }
  else if (p.endsWith('/approve') || p.endsWith('/revisions') || p.endsWith('/retry') || p.endsWith('/archive')) {
   calls.push({ p, body: req.postDataJSON(), key: req.headers()['idempotency-key'] })
   if (mode === 'unknown') { await route.abort(); return }
   if (mode === 'conflict') { version++; code = 409 }
   else { version++; if (p.endsWith('/retry')) { items[1] = make('p2', 'B'); status = 'review' } else if (p.endsWith('/approve')) items.find(i => p.includes(i.id)).approved = true; else if (p.endsWith('/revisions')) { const old = items[0]; items[0] = make('p1', 'A', old.version + 1); items[0].history.push(...old.history) } else status = 'archived' }
   body = task()
  }
  else if (p.endsWith('/archives')) { queries.push(Object.fromEntries(u.searchParams)); if (mode === 'archivefail') code = 500; if (mode === 'denied') code = 403; body = { items: mode === 'empty' ? [] : [{ id: 'a1', taskId: 't1', productName: '手机壳', brand: 'HX', skus: [{ code: 'A' }, { code: 'B' }], pictureCount: 2, createdAt: '2026-10-12' }], total: mode === 'empty' ? 0 : 21, page: Number(u.searchParams.get('page') || 1), pageSize: 20 } }
  else if (p.endsWith('/download')) { await route.fulfill({ contentType: 'application/zip', body: 'ZIP bytes' }); return }
  else if (p.endsWith('/tasks/t1')) body = task()
  else throw Error(`Unexpected ${p}`)
  await route.fulfill({ status: code, contentType: 'application/json', body: JSON.stringify(body) }).catch(() => {})
 })
 await visit(); await button('重试失败 SKU B').waitFor(); assert.equal(await button('整套归档到成品库').isDisabled(), true)
 await page.getByRole('tab', { name: 'B', exact: true }).click(); await page.getByText('尚无生成产物').waitFor(); await button('重试失败 SKU B').click(); await page.getByText('B主图 · v1').waitFor()
 await page.getByRole('tab', { name: 'A', exact: true }).click(); await button('审核通过').click(); await page.getByText('待审核 · 已通过').waitFor(); assert.equal(items[1].approved, false)
 await button('标注修改').click(); await opinion().fill('完整意见不能被截断；修改这一张'); await button('预览并提交修改').click(); await page.getByText('确认本次单图修改', { exact: true }).waitFor(); mode = 'conflict'; await button('确认提交修改').click(); await page.getByText('任务或资料已发生变化，请刷新后重试。').last().waitFor(); assert.equal(await opinion().inputValue(), '完整意见不能被截断；修改这一张')
 mode = 'unknown'; await button('确认提交修改').click(); await button('核实并重试图片原请求').waitFor(); const frozen = calls.at(-1); assert.equal(await opinion().isDisabled(), true)
 mode = 'normal'; await button('核实并重试图片原请求').click(); await page.getByText('A主图 · v2').waitFor(); assert.deepEqual(calls.at(-1), frozen); assert.equal(items[0].approved, false); assert.equal(items[1].version, 1)
 await page.getByText('版本历史', { exact: true }).click(); await button('下载 v1').waitFor(); const dl = page.waitForEvent('download'); await button('下载 v1').click(); await dl
 await mkdir('../../output/playwright/phase23', { recursive: true }); await page.screenshot({ path: '../../output/playwright/phase23/pictures-desktop.png', fullPage: true })
 await page.setViewportSize({ width: 390, height: 844 }); await unclipped(button('标注修改')); await button('标注修改').click(); await unclipped(opinion()); await page.screenshot({ path: '../../output/playwright/phase23/annotation-mobile.png', fullPage: true }); await button('取消').click()
 await button('审核通过').click(); await page.getByRole('tab', { name: 'B', exact: true }).click(); await button('审核通过').click(); await page.waitForFunction(() => [...document.querySelectorAll('button')].some(b => b.textContent.includes('整套归档到成品库') && !b.disabled)); await button('整套归档到成品库').click(); await page.getByText('已归档', { exact: true }).waitFor(); assert.equal(await button('标注修改').count(), 0)
 await visit('/overseas/archive'); await button('下载整套成品').waitFor(); await page.getByRole('textbox', { name: '筛选品名', exact: true }).fill('手机'); await page.getByRole('textbox', { name: '筛选品牌', exact: true }).fill('HX'); await page.getByRole('textbox', { name: '筛选 SKU', exact: true }).fill('A'); await page.getByRole('textbox', { name: '搜索成品', exact: true }).fill('case'); await page.waitForTimeout(500); assert.deepEqual(queries.at(-1), { product: '手机', brand: 'HX', sku: 'A', search: 'case', page: '1', pageSize: '20' }); await page.locator('.el-pagination .btn-next').click(); await page.waitForTimeout(300); assert.equal(queries.at(-1).page, '2')
 const zip = page.waitForEvent('download'); await button('下载整套成品').click(); await zip; await unclipped(button('下载整套成品'))
 mode = 'empty'; await button('刷新成品').click(); await page.getByText('暂无匹配成品；全部图片通过后由设计整套归档').waitFor(); mode = 'archivefail'; await button('刷新成品').click(); await page.getByText('服务暂不可用，请重试').waitFor(); mode = 'normal'; await button('刷新成品').click(); await button('下载整套成品').waitFor(); await page.screenshot({ path: '../../output/playwright/phase23/archive-mobile.png', fullPage: true })
 caps = ['task.read']; status = 'review'; await visit(); await page.getByText('当前为只读视角，图片处理需由负责设计或设计主管操作。').waitFor(); assert.equal(await button('标注修改').count(), 0)
 mode = 'readfail'; await button('刷新图片').click(); await page.getByText('服务暂不可用，请重试').waitFor(); mode = 'normal'; await button('刷新图片').click(); await page.getByText('A主图 · v2').waitFor(); mode = 'denied'; await button('刷新图片').click(); await page.locator('.hx-page').filter({ hasText: /工作流任务|暂无此功能权限/ }).first().waitFor(); assert.equal(await page.locator('.pictures-panel').count(), 0)
 assert.deepEqual(errors, []); console.log('PASS pictures: partial SKU retry, isolated approval/revision, full confirmation, conflict preservation, frozen-key network retry, original/history download, archive gate, search/pagination/ZIP/empty/error, narrow annotation, readonly, revoke')
} catch (e) { console.error(await page.locator('body').innerText()); throw e } finally { await browser.close() }
