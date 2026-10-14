import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3015'
const browser = await chromium.launch({ headless: true }), context = await browser.newContext({ viewport: { width: 1280, height: 900 } }), page = await context.newPage()
page.setDefaultTimeout(15000)
let mode = 'normal', caps = ['task.create', 'task.read'], uploadCount = 0
const errors = [], requests = [], keys = []
const material = () => ({ status: 'ready', createdAt: '2026-10-12', id: 'm1', kind: 'competitor', name: '竞品.csv', sizeBytes: 20, contentType: 'text/csv', taskId: null })
const button = name => page.getByRole('button', { name, exact: true })
const upload = (name = '竞品.csv', content = 'product,feature\ncase,clear') => page.locator('[data-material-kind="competitor"] input[type=file]').setInputFiles({ name, mimeType: 'text/csv', buffer: Buffer.from(content) })
async function unclipped(locator) {
  await locator.scrollIntoViewIfNeeded()
  assert.deepEqual(await locator.evaluate(el => { const b = el.getBoundingClientRect(), out = []; for (let p = el.parentElement; p; p = p.parentElement) { const r = p.getBoundingClientRect(), s = getComputedStyle(p); if (/(auto|scroll|hidden|clip)/.test(s.overflowX) && (b.left < r.left - 1 || b.right > r.right + 1)) out.push('x'); if (/(auto|scroll|hidden|clip)/.test(s.overflowY) && (b.top < r.top - 1 || b.bottom > r.bottom + 1)) out.push('y') } return out }), [])
}
page.on('pageerror', error => errors.push(error.message))
try {
  await context.route(`${base}/api/**`, async route => {
    const req = route.request(), path = new URL(req.url()).pathname; requests.push(req.method() + ' ' + path)
    let status = 200, body = {}
    if (path.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (path === '/api/identity/v1/me') body = { name: '测试运营', sessionId: 'identity-test' }
    else if (path.endsWith('/tickets')) body = { ticket: 'test' }
    else if (path === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
    else if (path.includes('/auth/')) { body = { id: 'actor', name: '测试运营', identitySessionId: 'identity-test', status: 'active', roles: ['operator'], capabilities: caps }; if (path.endsWith('/access')) body = { state: 'allowed', member: body } }
    else if (path.endsWith('/task-designers')) body = { items: [{ id: 'd1', name: '设计一', department: '海外' }], total: 1, page: 1, pageSize: 20 }
    else if (path.endsWith('/materials') && req.method() === 'POST') {
      uploadCount++; assert.equal(req.headers()['x-hx-request'], '1'); assert.match(req.headers()['content-type'], /multipart\/form-data/)
      if (mode === 'network') { await route.abort(); return }
      if (mode === 'malformed') body = { ...material(), sizeBytes: -1 }
      else { if (mode === 'slow') await new Promise(resolve => setTimeout(resolve, 1600)); body = material() }
      if (mode === '403') { status = 403; caps = [] }
    }
    else if (path.endsWith('/materials/m1') && req.method() === 'DELETE') { if (mode === 'delete-conflict') status = 409; else status = 204 }
    else if (path.endsWith('/content')) { if (mode === 'content-denied') { status = 403; caps = [] } else if (mode === 'content-missing') status = 404; else if (mode === 'content-store') status = 503; else { await route.fulfill({ status: 200, headers: { 'Content-Type': 'text/csv', 'Content-Disposition': "attachment; filename*=UTF-8''%E7%AB%9E%E5%93%81.csv" }, body: req.method() === 'HEAD' ? '' : 'real bytes' }); return } }
    else if (path.endsWith('/tasks') && req.method() === 'POST') { keys.push(req.headers()['idempotency-key']); await route.abort(); return }
    else if (path.endsWith('/tasks')) body = { items: [], total: 0, page: 1, pageSize: 20 }
    else throw Error(`Unexpected ${req.method()} ${path}`)
    await route.fulfill({ status, contentType: 'application/json', body: status === 204 ? undefined : JSON.stringify(body) }).catch(() => {})
  })
  await page.goto(`${base}/#/overseas/create`); await button('提交图需').waitFor(); assert.equal(await button('提交图需').isDisabled(), true)
  await upload('空.csv', ''); await page.getByText('文件为空，请选择包含内容的文件', { exact: true }).waitFor(); assert.equal(uploadCount, 0)
  await page.locator('[data-material-kind="competitor"] input[type=file]').evaluate(input => { const file = new File(['x'], '超限.csv'); Object.defineProperty(file, 'size', { value: 500_000_001 }); const transfer = new DataTransfer(); transfer.items.add(file); input.files = transfer.files; input.dispatchEvent(new Event('change', { bubbles: true })) }); await page.getByText('单个文件不能超过 500 MB', { exact: true }).waitFor(); assert.equal(uploadCount, 0)
  mode = 'slow'; await upload(); await button('取消上传').waitFor(); assert.equal(await button('提交图需').isDisabled(), true); await button('取消上传').click(); await page.waitForTimeout(1800); assert.equal(await page.getByText(/竞品.csv/).count(), 0)
  mode = 'network'; await upload(); await page.getByText('资料服务连接失败，请重试', { exact: true }).waitFor(); assert.equal(await button('提交图需').isDisabled(), true)
  mode = 'malformed'; await upload(); await page.getByText('服务响应格式错误，请重试', { exact: true }).waitFor()
  mode = 'normal'; await upload(); await page.getByText('竞品.csv', { exact: true }).waitFor(); assert.equal(await button('提交图需').isDisabled(), false)
  assert.equal(await button('预览资料').count(), 0); assert.equal(await button('重试解析').count(), 0)
  const beforeFailure = requests.filter(p => p.startsWith('GET ') && p.endsWith('/content')).length
  mode = 'content-store'; await button('下载原文件').click(); await page.getByRole('alert').filter({ hasText: /下载|服务|读取/ }).waitFor()
  assert.equal(requests.filter(p => p.startsWith('GET ') && p.endsWith('/content')).length, beforeFailure, 'failed HEAD must not start native GET')
  mode = 'delete-conflict'; await button('移除资料').click(); await button('确认移除').click(); await page.getByText('资料已被绑定或任务已变化，请刷新后重试', { exact: true }).waitFor(); assert.equal(await button('提交图需').isDisabled(), true)
  mode = 'normal'; await upload(); await page.getByText(/竞品.csv/).waitFor(); await button('移除资料').click(); await button('取消').click(); assert.equal(await page.getByText(/竞品.csv/).count(), 1)
  await button('移除资料').click(); await button('确认移除').click(); await page.locator('[data-material-kind="competitor"] input[type=file]').waitFor({ state: 'attached' }); assert.equal(await button('提交图需').isDisabled(), true)
  await page.setViewportSize({ width: 390, height: 844 }); await unclipped(page.locator('[data-material-kind="competitor"]')); await unclipped(page.getByText(/至少上传一份资料/)); await unclipped(button('提交图需'))
  mode = 'slow'; await upload(); await button('取消上传').waitFor(); await button('返回任务列表').click(); await page.waitForTimeout(1800); await button('提交图需').click(); assert.equal(await page.getByText(/竞品.csv/).count(), 0); assert.equal(await button('提交图需').isDisabled(), true)
  mode = 'normal'; await upload(); await page.getByText(/竞品.csv/).waitFor(); mode = 'content-denied'; await button('下载原文件').click(); await page.locator('.hx-page').filter({ hasText: /工作流任务|暂无此功能权限/ }).first().waitFor(); assert.equal(await page.locator('.reader-paper').count(), 0)
  assert.deepEqual(errors, []); console.log('PASS material browser faults: 500MB/empty; real XHR progress; cancel/route late response; malformed/network; storage failure blocks native download; delete conflict/cancel; no parsing UI; narrow clipping; revoked download clears state')
} catch (error) { console.error(await page.locator('body').innerText()); console.error({ errors, requests }); throw error } finally { await browser.close() }
