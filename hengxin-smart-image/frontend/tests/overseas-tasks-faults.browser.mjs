import assert from 'node:assert/strict'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3015'
const browser = await chromium.launch({ headless: true }), context = await browser.newContext({ viewport: { width: 1280, height: 900 } }), page = await context.newPage()
page.setDefaultTimeout(15000)
const errors = [], keys = [], queries = []
page.on('pageerror', e => errors.push(e.message))
let mode = 'normal', caps = ['task.create', 'task.read', 'task.reassign'], saved, attempts = 0, version = 1
const parsed = { version: 1, status: 'ready', parserVersion: 'test', text: 'product,feature', error: null, createdAt: '2026-10-12' }
const material = { ...parsed, id: 'material-1', kind: 'competitor', name: '竞品.csv', sizeBytes: 12, contentType: 'text/csv', taskId: null, versions: [parsed] }
const task = () => ({ id: 'task-1', name: '真实多SKU任务', productName: '手机壳', brand: 'HX', platform: 'Amazon', market: '美国', remarks: '核对图需', skus: [{ code: 'A' }, { code: 'B' }], status: 'created', version, createdAt: '2026-10-12T12:00:00Z', updatedAt: '2026-10-12T12:00:00Z', createdBy: { id: 'actor', name: '测试运营' }, designer: { id: 'd1', name: '设计一', status: 'active', eligible: true }, capabilities: caps.filter(c => c !== 'task.create'), events: [{ id: 'e1', kind: 'task.created', actorId: 'actor', actorName: '测试运营', title: '图需已保存', at: '2026-10-12T12:00:00Z', beforeDesignerId: null, afterDesignerId: 'd1', version: 1 }] })
async function unclipped(locator) {
  await locator.scrollIntoViewIfNeeded()
  const failures = await locator.evaluate(el => { const b = el.getBoundingClientRect(), out = []; for (let p = el.parentElement; p; p = p.parentElement) { const r = p.getBoundingClientRect(), s = getComputedStyle(p); if (/(auto|scroll|hidden|clip)/.test(s.overflowX) && (b.left < r.left - 1 || b.right > r.right + 1)) out.push(`${p.className}:x`); if (/(auto|scroll|hidden|clip)/.test(s.overflowY) && (b.top < r.top - 1 || b.bottom > r.bottom + 1)) out.push(`${p.className}:y`) } return out })
  assert.deepEqual(failures, [])
}
const button = name => page.getByRole('button', { name, exact: true })
async function choose(name) { await page.locator('input[aria-label="负责设计"]:not([disabled])').waitFor(); await page.locator('.el-select').filter({ has: page.getByRole('combobox', { name: '负责设计', exact: true }) }).click(); await page.getByRole('option', { name, exact: true }).click() }
try {
  await context.route(`${base}/api/**`, async route => {
    const req = route.request(), u = new URL(req.url()), p = u.pathname
    let status = 200, body = {}
    if (p.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (p === '/api/identity/v1/me') body = { name: '测试运营' }
    else if (p.endsWith('/tickets')) body = { ticket: 'test' }
    else if (p === '/api/v1/auth/identity/session') status = 403
    else if (p.includes('/auth/')) body = { id: 'actor', name: '测试运营', status: 'active', roles: ['operator', 'design_manager'], capabilities: caps }
    else if (p.endsWith('/jobs')) body = { items: [] }
    else if (p.endsWith('/execution-events')) body = { items: [], cursor: Number(u.searchParams.get('after')) }
    else if (p.endsWith('/task-designers')) {
      if (mode === 'candidate-fail') { await route.abort(); return }
      const n = Number(u.searchParams.get('page')); queries.push(Object.fromEntries(u.searchParams))
      body = { items: mode === 'empty' ? [] : [{ id: `d${n}`, name: `设计${n === 1 ? '一' : '二'}`, department: '海外设计' }], total: mode === 'empty' ? 0 : 21, page: n, pageSize: 20 }
    } else if (p.endsWith('/assignment')) {
      if (mode === 'conflict') { version++; status = 409 } else { version++; body = { ...task(), designer: { id: 'd2', name: '设计二', status: 'active', eligible: true } } }
    } else if (p.endsWith('/materials')) { body = req.method() === 'POST' ? material : [material] } else if (p.endsWith('/tasks') && req.method() === 'POST') {
      attempts++; keys.push(req.headers()['idempotency-key']); saved = req.postDataJSON()
      if (mode === 'unknown') { await route.abort(); return }
      body = task(); status = 201
    } else if (p.endsWith('/tasks')) {
      queries.push(Object.fromEntries(u.searchParams))
      if (mode === 'loading') await new Promise(resolve => setTimeout(resolve, 800))
      if (mode === 'network') { await route.abort(); return }
      if (mode === '403' || mode === '401') status = Number(mode)
      body = { items: mode === 'empty' ? [] : [task()], total: mode === 'empty' ? 0 : 41, page: Number(u.searchParams.get('page')), pageSize: 20 }
    } else if (p.endsWith('/tasks/task-1')) { if (mode === '403') status = 403; body = task() }
    else throw Error(`Unexpected ${p}`)
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  })
  mode = 'empty'; await page.goto(`${base}/#/overseas/create`); await page.getByText('暂无可用设计，请调整搜索或联系管理员。').waitFor(); await unclipped(page.getByText('暂无可用设计，请调整搜索或联系管理员。'))
  assert.equal(await page.getByText('使用示例资料').count(), 0)
  assert.equal(await page.getByText('上传图需资料', { exact: true }).count(), 0)
  mode = 'candidate-fail'; await button('刷新设计人选').click(); await page.getByText('服务连接失败，请稍后重试').waitFor(); await unclipped(page.locator('.el-alert'))
  mode = 'normal'; await button('刷新设计人选').click(); await page.getByRole('combobox', { name: '负责设计', exact: true }).waitFor()
  await page.locator('.el-pager').getByText('2', { exact: true }).click(); await choose('设计二 · 海外设计'); assert.equal(queries.at(-1).page, '2')
  const input = label => page.locator('.el-form-item').filter({ has: page.locator('.el-form-item__label', { hasText: label }) }).locator('input')
  await input('任务名称').fill('真实多SKU任务'); await input('品名').fill('手机壳'); await input('品牌').fill('HX'); await input('目标站点').fill('美国')
  await page.getByRole('textbox', { name: 'SKU 1 编码', exact: true }).fill('A'); await button('添加 SKU').click(); await page.getByRole('textbox', { name: 'SKU 2 编码', exact: true }).fill('B')
  assert.equal(await button('提交图需').isDisabled(), true)
  await page.locator('input[type=file][accept=".xls,.xlsx,.csv"]').setInputFiles({ name: '竞品.csv', mimeType: 'text/csv', buffer: Buffer.from('product,feature') }); await page.getByText(/竞品.csv · 解析成功/).waitFor()
  mode = 'unknown'; await button('提交图需').click(); await page.getByText('服务连接失败，请稍后重试').waitFor(); assert.equal(await input('任务名称').inputValue(), '真实多SKU任务')
  mode = 'normal'; await button('提交图需').click(); await page.getByRole('heading', { name: '任务信息', exact: true }).waitFor(); assert.equal(attempts, 2); assert.equal(keys[0], keys[1]); assert.equal(saved.skus.length, 2); assert.equal(saved.designerId, 'd2')
  assert.equal(await page.getByText('预览图需资料').count(), 0)
  await button('改派设计').click(); await choose('设计一 · 海外设计'); await page.locator('.el-pager').getByText('2', { exact: true }).click(); await choose('设计二 · 海外设计')
  mode = 'conflict'; await button('确认改派').click(); await page.getByText('任务或资料已发生变化，请刷新后重试。').waitFor(); assert.equal(await button('确认改派').isDisabled(), true)
  mode = 'normal'; await choose('设计一 · 海外设计'); assert.equal(await button('确认改派').isDisabled(), true)
  await page.locator('.el-pager').getByText('2', { exact: true }).click(); await choose('设计二 · 海外设计'); await button('确认改派').click(); await page.getByText('负责设计：设计二', { exact: false }).waitFor()
  await button('返回任务列表').click(); await page.getByRole('button', { name: '查看详情', exact: true }).waitFor(); await page.locator('.el-pager').getByText('2', { exact: true }).click(); await page.waitForTimeout(300); assert.equal(queries.at(-1).page, '2')
  await page.getByRole('textbox', { name: '搜索任务', exact: true }).fill('SKU-A'); await page.waitForTimeout(400); assert.equal(queries.at(-1).page, '1'); assert.equal(queries.at(-1).search, 'SKU-A')
  mode = 'loading'; await button('刷新任务').click(); await page.getByText('正在加载任务…').waitFor(); await unclipped(page.getByText('正在加载任务…')); await button('查看详情').waitFor();
  mode = 'network'; await button('刷新任务').click(); await page.getByText('服务连接失败，请稍后重试').waitFor(); assert.equal(await button('查看详情').count(), 0); await unclipped(page.locator('.el-alert'))
  mode = 'empty'; await button('刷新任务').click(); await page.getByText('暂无匹配任务，请提交图需或清空筛选').waitFor(); await unclipped(page.getByText('暂无匹配任务，请提交图需或清空筛选'))
  await page.setViewportSize({ width: 390, height: 844 }); await unclipped(button('刷新任务')); await unclipped(page.getByText('暂无匹配任务，请提交图需或清空筛选'))
  mode = 'normal'; await button('提交图需').click(); await unclipped(button('提交图需')); await unclipped(button('刷新设计人选'))
  await button('返回任务列表').click(); await button('查看详情').waitFor(); mode = '403'; caps = []; await button('刷新任务').click(); await page.getByRole('heading', { name: '企业身份已连接' }).waitFor(); assert.equal(await page.getByText('真实多SKU任务', { exact: true }).count(), 0)
  mode = 'empty'; caps = ['task.read']; await page.goto(`${base}/#/overseas/tasks`); await page.reload(); await page.getByText('暂无匹配任务，请清空筛选或联系运营').waitFor(); assert.equal(await button('提交图需').count(), 0); assert.equal(await page.getByText('暂无匹配任务，请提交图需或清空筛选').count(), 0); await unclipped(page.getByText('暂无匹配任务，请清空筛选或联系运营'))
  mode = '401'; await page.reload(); await page.getByText('身份已失效，请重新登录').waitFor(); assert.equal(await button('查看详情').count(), 0);
  assert.deepEqual(errors, []); console.log('PASS task browser: candidates empty/failure/page; multi-SKU; uncertain retry; detail; assignment 409; list pagination/search/error/empty; narrow ancestor clipping; revoke')
} catch (e) { console.error(await page.locator('body').innerText()); console.error({ errors, attempts, saved, keys }); throw e } finally { await browser.close() }
