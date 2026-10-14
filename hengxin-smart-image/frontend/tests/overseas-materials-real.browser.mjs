import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3015', headers = { 'X-HX-Request': '1', Origin: base }
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless: true, channel: 'chromium' }), sessions = {}, errors = []
const button = (page, name) => page.getByRole('button', { name, exact: true })
async function api(context, method, path, data, key) { return context.request[method](`${base}/api/overseas/v1${path}`, { headers: { ...headers, ...(key ? { 'Idempotency-Key': key } : {}) }, data }) }
async function upload(page, name, content, kind = 'competitor') { await page.locator(`[data-material-kind="${kind}"] input[type=file]`).setInputFiles({ name, mimeType: kind === 'competitor' ? 'text/csv' : 'application/pdf', buffer: Buffer.from(content) }) }
async function unclipped(locator) {
  await locator.scrollIntoViewIfNeeded()
  const failures = await locator.evaluate(el => { const b = el.getBoundingClientRect(), out = []; for (let p = el.parentElement; p; p = p.parentElement) { const r = p.getBoundingClientRect(), s = getComputedStyle(p); if (/(auto|scroll|hidden|clip)/.test(s.overflowX) && (b.left < r.left - 1 || b.right > r.right + 1)) out.push(`${p.className}:x`); if (/(auto|scroll|hidden|clip)/.test(s.overflowY) && (b.top < r.top - 1 || b.bottom > r.bottom + 1)) out.push(`${p.className}:y`) } return out })
  assert.deepEqual(failures, [])
}
try {
  for (const role of ['operator', 'operator_manager', 'designer', 'design_manager', 'admin', 'operator2', 'designer2']) {
    const context = await browser.newContext({ viewport: { width: 1366, height: 900 } })
    assert.equal((await context.request.post(`${base}/api/identity/v1/dingtalk/container`, { headers, data: { code: `${role.endsWith('2') ? 'p19' : 'p18'}-${role}` } })).status(), 200)
    const page = await context.newPage(); page.on('pageerror', e => errors.push(e.message)); await page.goto(`${base}/#/overseas`); await page.locator('.hx-page').filter({ hasText: /工作流任务|暂无此功能权限/ }).first().waitFor()
    sessions[role] = { context, page, member: await (await api(context, 'get', '/auth/me')).json() }
  }
  const { page, context } = sessions.operator
  const draft = { name: `资料补充-${Date.now()}`, productName: '手机壳', brand: 'HX', platform: 'Amazon', market: '美国', remarks: '', skus: [{ code: 'P20-A' }], designerId: sessions.designer.member.id }
  const metadata = await api(context, 'post', '/tasks', draft, crypto.randomUUID()); assert.equal(metadata.status(), 201); const task = await metadata.json(); assert.equal(task.status, 'created')
  await page.goto(`${base}/#/overseas/tasks/${task.id}`); await button(page, '提交补充资料').waitFor(); assert.equal(await button(page, '提交补充资料').isDisabled(), true)
  await upload(page, '旧资料.pptx', 'original', 'requirement'); await page.getByText('旧资料.pptx', { exact: true }).waitFor(); assert.equal(await button(page, '提交补充资料').isDisabled(), false)
  assert.equal(await button(page, '预览资料').count(), 0); assert.equal(await button(page, '重试解析').count(), 0)
  await button(page, '移除资料').click(); await button(page, '取消').click(); assert.equal(await page.getByText('旧资料.pptx', { exact: true }).count(), 1)
  await button(page, '移除资料').click(); await button(page, '确认移除').click(); await page.getByText('旧资料.pptx', { exact: true }).waitFor({ state: 'detached' })
  // Arbitrary originals, including invalid PDF, remain downloadable without parsing.
  await upload(page, '原件.pdf', '%PDF-1.4 broken', 'requirement'); await page.getByText('原件.pdf', { exact: true }).waitFor()
  const longName = 'ZZZ-13圆形杂志桌灯-竞品listing-杨陈玉-20260804-'.repeat(3) + '.csv'
  await upload(page, longName, 'product,feature\nCase,<script>alert(1)</script>'); await page.getByText(longName, { exact: true }).waitFor()
  assert.equal(await button(page, '新窗口打开').count(), 0); assert.equal(await button(page, '放大查看').count(), 0)
  const download = page.waitForEvent('download'); await button(page, '下载原文件').last().click(); const saved = await download
  assert.equal(saved.suggestedFilename(), longName); const chunks = []; for await (const chunk of await saved.createReadStream()) chunks.push(chunk)
  assert.equal(Buffer.concat(chunks).toString(), 'product,feature\nCase,<script>alert(1)</script>')
  await button(page, '提交补充资料').click(); await page.getByRole('heading', { name: '图需审核', exact: true }).waitFor(); assert.equal(await button(page, '移除资料').count(), 0)
  const materials = await (await api(context, 'get', `/tasks/${task.id}/materials`)).json(); assert.equal(materials.length, 2); const id = materials.find(m => m.kind === 'competitor').id
  assert.equal((await api(context, 'delete', `/materials/${id}`)).status(), 409)
  assert.equal((await api(context, 'post', `/materials/${id}/retry`, {})).status(), 404)
  for (const role of Object.keys(sessions)) {
    const allowed = !['operator2', 'designer2'].includes(role), result = await api(sessions[role].context, 'get', `/materials/${id}/content`)
    assert.equal(result.status(), allowed ? 200 : 403, role)
    assert.equal((await api(sessions[role].context, 'head', `/materials/${id}/content`)).status(), allowed ? 200 : 403, role + ' HEAD')
    if (allowed) assert.match(result.headers()['content-disposition'], /^attachment/)
  }
  const assignment = await api(sessions.design_manager.context, 'patch', `/tasks/${task.id}/assignment`, { designerId: sessions.designer2.member.id, version: 2 }, crypto.randomUUID()); assert.equal(assignment.status(), 200)
  assert.equal((await api(sessions.designer.context, 'get', `/materials/${id}/content`)).status(), 403)
  assert.equal((await api(sessions.designer2.context, 'get', `/materials/${id}/content`)).status(), 200)
  await page.setViewportSize({ width: 390, height: 844 }); await page.waitForTimeout(500); await button(page, '下载原文件').last().scrollIntoViewIfNeeded(); assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
  await unclipped(button(page, '下载原文件').last()); await unclipped(page.getByText(longName, { exact: true }));
  await mkdir('../../output/playwright/phase20', { recursive: true }); await page.screenshot({ path: '../../output/playwright/phase20/materials-real-mobile.png', fullPage: true })
  assert.deepEqual(errors, []); console.log('PASS real materials: arbitrary originals retained/submittable; no preview/retry; native download bytes/name; delete confirmation; frozen binding; GET/HEAD five-role and reassignment authorization; long-name narrow UI')
} catch (error) { if (sessions.operator) console.error(await sessions.operator.page.locator('body').innerText()); throw error } finally { await browser.close() }
