import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3038'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
await mkdir('../../output/playwright/overseas-light-live', { recursive: true })
const browser = await chromium.launch({ headless: true, ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : {}) }), context = await browser.newContext({ viewport: { width: 1280, height: 900 } })
const page = await context.newPage(), queries = [], errors = [], unexpected = [], missingAssets = []
page.on('pageerror', error => errors.push(error.message)); page.setDefaultTimeout(15000)
page.on('response', response => { if (new URL(response.url()).pathname.startsWith('/assets/') && response.status() >= 400) missingAssets.push(new URL(response.url()).pathname) })
const people = [{ id: 'a', name: '设计甲' }, { id: 'b', name: '设计乙' }]
const event = { id: 'e', actorId: 'b', actorName: '设计乙', at: '2026-11-06T04:00:00Z', pictures: [{ id: 'p', name: '成品.png', sku: 'SKU-ONE' }] }
const picture = { id: 'p', name: '成品.png', sku: 'SKU-ONE', width: 1, height: 1, contentType: 'image/png', sizeBytes: 68, url: '/api/overseas/v1/archives/archive/pictures/p/content' }
const archive = { id: 'archive', taskId: 't1', sourceDeleted: false, productName: '台灯', brand: 'OUTON', platform: 'Wayfair', skus: [{ code: 'SKU-ONE' }], pictureCount: 1, createdAt: event.at, cover: picture, latestArchive: event }
const tasks = Array.from({ length: 43 }, (_, i) => ({ id: `t${i}`, name: `任务${i}`, productName: '台灯', brand: 'OUTON', platform: 'Wayfair', language: 'en', market: '', remarks: '', skus: [{ code: `SKU-${i}` }], workflow: 'studio', status: i === 2 ? 'submitted' : i % 3 === 0 ? 'pending_review' : i % 3 === 1 ? 'studio' : 'completed', version: 1, createdAt: '2026-11-07T01:00:00Z', updatedAt: '2026-11-07T01:00:00Z', createdBy: people[0], designer: { ...people[i % 2], status: 'active', eligible: true }, capabilities: ['task.read', 'task.reassign', 'task.delete'], events: [], requirementsReviews: [] }))
const jobs = people.map((p, i) => ({ id: `job${i}`, taskId: `t${i}`, taskName: `任务${i}`, operatorId: p.id, operatorName: p.name, kind: 'studio', status: i ? 'failed' : 'running', executionCount: i ? 2 : 1, imageCount: i ? 1 : 0, createdAt: '2026-11-07T01:00:00Z', startedAt: '2026-11-07T01:01:00Z', completedAt: i ? '2026-11-07T01:04:00Z' : null, error: i ? '执行失败' : null }))
jobs.push({ id: 'cancelled', taskId: 't2', taskName: '排队取消任务', operatorId: 'a', operatorName: '设计甲', kind: 'studio', status: 'cancelled', executionCount: 0, imageCount: 0, createdAt: '2026-11-07T01:00:00Z', startedAt: null, completedAt: '2026-11-07T01:00:10Z', error: null })
const newDesigner = { id: 'c', name: '设计丙', department: '设计部' }
const button = name => page.getByRole('button', { name, exact: true })
async function unclipped(el) {
  await el.scrollIntoViewIfNeeded()
  assert.deepEqual(await el.evaluate(e => { const b = e.getBoundingClientRect(), out = []; for (let p = e.parentElement; p; p = p.parentElement) { const r = p.getBoundingClientRect(), s = getComputedStyle(p); if (/auto|scroll|hidden|clip/.test(s.overflowX) && (b.left < r.left - 1 || b.right > r.right + 1)) out.push('x'); if (/auto|scroll|hidden|clip/.test(s.overflowY) && (b.top < r.top - 1 || b.bottom > r.bottom + 1)) out.push('y') } return out }), [])
}
async function dateLayout() {
  const picker = await page.locator('.date-filter .el-date-editor').boundingBox()
  const container = await page.locator('.date-filter').boundingBox()
  const reset = await button('重置筛选').boundingBox()
  assert.ok(picker && container && reset)
  assert.ok(picker.x >= container.x - 1 && picker.x + picker.width <= container.x + container.width + 1, '日期控件超出容器')
  assert.ok(picker.x + picker.width <= reset.x || reset.x + reset.width <= picker.x ||
            picker.y + picker.height <= reset.y || reset.y + reset.height <= picker.y, '日期控件与重置按钮重叠')
}
async function neutral(name) {
  await page.mouse.move(0, 0)
  const colors = await button(name).evaluate(el => { const style = getComputedStyle(el); return [style.color, style.borderColor] })
  assert.deepEqual(colors, ['rgb(96, 98, 102)', 'rgb(220, 223, 230)'], name + ' 按钮样式与预览不符')
}
let archiveFault = false, archiveDeleted = false
try {
  await context.route('**/*', async route => {
    const u = new URL(route.request().url()), p = u.pathname
    if (['api.iconify.design', 'api.unisvg.com', 'api.simplesvg.com'].includes(u.hostname)) return route.fulfill({ contentType: 'application/json', body: '{}' })
    if (u.origin !== base && !['data:', 'blob:'].includes(u.protocol)) { unexpected.push(u.origin); return route.abort() }
    if (!p.startsWith('/api/')) return route.continue()
    let body = {}, status = 200
    if (p.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (p === '/api/identity/v1/me') body = { name: '测试', sessionId: 'identity-test' }
    else if (p.endsWith('/tickets')) body = { ticket: 'test' }
    else if (p === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
    else if (p.includes('/auth/')) { body = { id: 'a', name: '测试', identitySessionId: 'identity-test', status: 'active', roles: ['design_manager'], capabilities: ['stats.read', 'task.read', 'task.create', 'task.reassign', 'task.design', 'task.delete'] }; if (p.endsWith('/access')) body = { state: 'allowed', member: body } }
    else if (p.endsWith('/management/operators')) body = { items: people }
    else if (p.endsWith('/management/people')) { const selected = u.searchParams.get('memberId'); body = { items: people.filter(x => !selected || x.id === selected).map((x, i) => ({ ...x, calls: i + 1, images: i, lastCall: '2026-11-07T01:00:00Z' })) } }
    else if (p.endsWith('/management/usage')) body = { jobs: 2, queued: 0, running: 1, uncertain: 0, succeeded: 0, failed: 1, cancelled: 0, generationImages: 1, revisionImages: 0 }
    else if (p.endsWith('/management/jobs')) {
      queries.push({ path: p, ...Object.fromEntries(u.searchParams) })
      const rows = jobs.filter(x => (!u.searchParams.get('memberId') || x.operatorId === u.searchParams.get('memberId')) && (!u.searchParams.get('statusGroup') || x.status === u.searchParams.get('statusGroup')))
      body = { items: rows, total: rows.length, page: Number(u.searchParams.get('page') || 1), pageSize: 20 }
    } else if (p.endsWith('/task-assignees')) body = { items: tasks.some(t => t.designer.id === 'c') ? [...people, newDesigner] : people }
    else if (p.endsWith('/task-designers')) body = { items: [...people, newDesigner].map(x => ({ ...x, department: '设计部' })), total: 3, page: 1, pageSize: 20 }
    else if (p.endsWith('/tasks')) {
      queries.push({ path: p, ...Object.fromEntries(u.searchParams) })
      const groups = { pending: ['pending_review', 'returned', 'created', 'submitted'], designing: ['studio', 'reworking'], completed: ['completed', 'archived'] }
      const selected = u.searchParams.get('designerId'), group = u.searchParams.get('statusGroup'), search = u.searchParams.get('search') || ''
      const rows = tasks.filter(x => (!selected || x.designer.id === selected) && (!group || groups[group]?.includes(x.status)) && (!search || x.name.includes(search)))
      const number = Number(u.searchParams.get('page') || 1); body = { items: rows.slice((number - 1) * 20, number * 20), total: rows.length, page: number, pageSize: 20 }
    } else if (/\/tasks\/t\d+\/assignment$/.test(p) && route.request().method() === 'PATCH') {
      const id = p.split('/').at(-2), task = tasks.find(x => x.id === id)
      task.designer = { ...newDesigner, status: 'active', eligible: true }; task.version++
      body = task
    } else if (/\/tasks\/t\d+$/.test(p) && route.request().method() === 'DELETE') {
      const id = p.split('/').at(-1), index = tasks.findIndex(x => x.id === id); tasks.splice(index, 1)
      body = { taskId: id, status: 'deleted', error: null }
    } else if (/\/tasks\/t\d+\/materials$/.test(p)) body = []
    else if (/\/tasks\/t\d+$/.test(p)) body = tasks.find(x => p.endsWith('/' + x.id))
    else if (p.endsWith('/archive-operators')) body = { items: archiveDeleted ? [] : people }
    else if (p.endsWith('/archives')) {
      queries.push({ path: p, ...Object.fromEntries(u.searchParams) }); const selected = u.searchParams.get('archiverId'), search = u.searchParams.get('search') || ''
      const rows = !archiveDeleted && (!selected || ['a', 'b'].includes(selected)) && (!search || [archive.productName, archive.brand, archive.skus[0].code].some(x => x.includes(search))) ? [archive] : []
      body = { items: rows, total: rows.length, page: Number(u.searchParams.get('page') || 1), pageSize: 20 }; if (archiveFault) status = 500
    } else if (p === '/api/overseas/v1/archives/archive/deletion-preview') body = { ...archive, deleteToken: 'test-token' }
    else if (p === '/api/overseas/v1/archives/archive' && route.request().method() === 'DELETE') { archiveDeleted = true; body = { archiveId: 'archive', status: 'deleted', error: null } }
    else if (p === '/api/overseas/v1/archives/archive') body = { ...archive, pictures: [picture], archiveHistory: [event], historyIncomplete: false }
    else if (p === picture.url) return route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jQmQAAAAASUVORK5CYII=', 'base64') })
    else { unexpected.push(p); return route.abort() }
    await route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.goto(base + '/#/overseas/admin/usage')
  await page.getByRole('heading', { name: '调用与执行', exact: true }).waitFor()
  await page.getByText('按人员查看使用情况，跟进每一次 Codex 执行。', { exact: true }).waitFor()
  await dateLayout()
  assert.equal(new URL(page.url()).hash, '#/overseas/admin/activity')
  await page.getByRole('columnheader', { name: '调用次数', exact: true }).waitFor()
  await button('设计甲').waitFor(); await neutral('刷新数据'); await neutral('重置筛选')
  for (const name of ['查看排队中记录', '查看执行中记录', '查看失败记录', '查看待核实记录']) {
    assert.equal(await button(name).evaluate(el => getComputedStyle(el).color), 'rgb(96, 98, 102)', name + ' 状态按钮颜色与预览不符')
  }
  await button('设计甲').click(); await page.getByText('任务0', { exact: true }).waitFor()
  assert.equal(queries.filter(q => q.path.endsWith('/jobs')).at(-1).memberId, 'a')
  await button('查看详情').first().click(); await page.getByRole('dialog', { name: '执行详情' }).waitFor(); await button('关闭此对话框').click()
  await button('查看失败记录').click(); await page.getByText('任务1', { exact: true }).waitFor()
  assert.equal(queries.filter(q => q.path.endsWith('/jobs')).at(-1).statusGroup, 'failed')
  assert.equal(queries.filter(q => q.path.endsWith('/jobs')).at(-1).memberId, undefined)
  await page.screenshot({ path: '../../output/playwright/overseas-light-live/activity.png' })
  await page.locator('label').filter({ hasText: '执行状态' }).locator('.el-select').click(); await page.getByRole('option', { name: '已取消', exact: true }).click()
  const cancelledRow = page.getByRole('row').filter({ hasText: '排队取消任务' }); await cancelledRow.getByText('未执行', { exact: true }).waitFor()
  await cancelledRow.getByRole('button', { name: '查看详情' }).click(); await page.getByRole('dialog', { name: '执行详情' }).getByText('未执行', { exact: true }).waitFor(); await button('关闭此对话框').click()
  await page.goto(base + '/#/overseas/tasks'); await page.getByRole('columnheader', { name: '任务状态' }).waitFor()
  await page.getByText('任务0', { exact: true }).waitFor()
  await neutral('刷新任务')
  const taskCard = await page.locator('.workspace-in-portal > .el-card').first().boundingBox()
  const taskHeader = await page.locator('.workspace-in-portal .el-table__header-wrapper').first().boundingBox()
  assert.ok(taskCard && taskHeader)
  assert.equal(await page.locator('.el-table__body tbody tr').count(), 20)
  await page.locator('.task-page-bottom').getByText('1–20 / 43 条', { exact: true }).waitFor()
  await page.getByRole('row').filter({ hasText: '任务2' }).getByText('待开始分析', { exact: true }).waitFor()
  await page.locator('.el-pagination .btn-next').first().click(); await page.getByText('任务20', { exact: true }).waitFor()
  await page.locator('.task-page-bottom').getByText('21–40 / 43 条', { exact: true }).waitFor()
  await page.locator('.el-pagination .btn-next').first().click(); await page.getByText('任务40', { exact: true }).waitFor()
  await page.locator('.task-page-bottom').getByText('41–43 / 43 条', { exact: true }).waitFor()
  await page.locator('.el-pagination .btn-prev').first().click(); await page.getByText('任务20', { exact: true }).waitFor()
  await button('查看详情').nth(1).click(); await button('改派设计').click()
  await page.locator('.designer-picker .el-select').click(); await page.getByRole('option', { name: '设计丙', exact: true }).click(); await button('确认改派').click(); await button('改派设计').waitFor()
  await button('返回任务列表').click(); await page.getByText('任务20', { exact: true }).waitFor()
  await page.getByRole('combobox', { name: '设计负责人筛选' }).fill('设计丙'); await page.getByRole('option', { name: '设计丙', exact: true }).click(); await page.getByText('任务21', { exact: true }).waitFor()
  assert.equal(queries.filter(q => q.path.endsWith('/tasks')).at(-1).designerId, 'c')
  await page.locator('.task-page-bottom').getByText('1–1 / 1 条', { exact: true }).waitFor()
  await page.getByRole('row').filter({ hasText: '任务21' }).getByRole('button', { name: '删除', exact: true }).click()
  await page.getByRole('dialog', { name: '永久删除任务' }).getByRole('button', { name: '确认删除' }).click()
  await page.waitForFunction(() => document.querySelector('[aria-label="设计负责人筛选"]')?.value === '')
  await page.getByText('任务0', { exact: true }).waitFor(); assert.equal(await page.locator('.el-table__body tbody tr').count(), 20)
  await page.getByRole('combobox', { name: '设计负责人筛选' }).fill('设计丙'); assert.equal(await page.getByRole('option', { name: '设计丙', exact: true }).count(), 0)
  await page.getByRole('combobox', { name: '设计负责人筛选' }).fill('设计乙'); await page.getByRole('option', { name: '设计乙', exact: true }).click()
  await page.locator('.hx-filter .el-select').first().click(); await page.getByRole('option', { name: '待处理', exact: true }).click()
  await page.getByText('待设计审核图需').first().waitFor()
  assert.equal(queries.filter(q => q.path.endsWith('/tasks')).at(-1).designerId, 'b')
  assert.equal(queries.filter(q => q.path.endsWith('/tasks')).at(-1).statusGroup, 'pending')
  assert.equal(queries.filter(q => q.path.endsWith('/tasks')).at(-1).page, '1')
  await page.getByRole('textbox', { name: '搜索任务' }).fill('无匹配')
  await page.locator('.task-page-bottom').getByText('0 / 0 条', { exact: true }).waitFor()
  await page.screenshot({ path: '../../output/playwright/overseas-light-live/tasks.png' })
  await page.goto(base + '/#/overseas/archive'); await button('下载整套成品').waitFor()
  await neutral('重置筛选'); await neutral('刷新成品'); await neutral('下载整套成品')
  const archiveCard = await page.locator('.art-card').first().boundingBox()
  const archiveSearch = await page.locator('.hx-filter > .el-input').first().boundingBox()
  assert.ok(archiveCard && archiveSearch && Math.abs(taskCard.x - archiveCard.x) <= 1)
  assert.ok(Math.abs(archiveSearch.width - 255) <= 1, '成品搜索宽度与预览不符')
  assert.ok(Math.abs(taskHeader.y - taskCard.y - 201) <= 2, '任务表头间距与预览不符')
  await page.getByRole('combobox', { name: '归档人筛选' }).fill('设计甲'); await page.getByRole('option', { name: '设计甲', exact: true }).click()
  await page.getByText('设计甲 曾参与归档', { exact: true }).waitFor()
  assert.equal(queries.filter(q => q.path.endsWith('/archives')).at(-1).archiverId, 'a')
  await page.getByRole('textbox', { name: '搜索成品' }).fill('无匹配'); await page.getByText('暂无匹配成品；设计归档后的图片会显示在这里').waitFor()
  await button('清空筛选').click(); await button('下载整套成品').waitFor()
  archiveFault = true; await button('刷新成品').click(); await page.locator('.el-alert--error').waitFor(); archiveFault = false; await button('刷新成品').click(); await button('下载整套成品').waitFor()
  await page.screenshot({ path: '../../output/playwright/overseas-light-live/archive.png' })
  await page.getByRole('combobox', { name: '归档人筛选' }).fill('设计甲'); await page.getByRole('option', { name: '设计甲', exact: true }).click()
  await button('删除整套成品').click(); await page.getByRole('dialog', { name: '永久删除整套成品' }).getByRole('button', { name: '确认删除' }).click()
  await page.waitForFunction(() => document.querySelector('[aria-label="归档人筛选"]')?.value === '')
  await page.getByText('暂无匹配成品；设计归档后的图片会显示在这里').waitFor()
  await page.getByRole('combobox', { name: '归档人筛选' }).fill('设计甲'); assert.equal(await page.getByRole('option', { name: '设计甲', exact: true }).count(), 0)
  await page.setViewportSize({ width: 390, height: 844 }); await page.reload(); await button('刷新成品').waitFor()
  for (const el of [page.getByRole('textbox', { name: '搜索成品' }), page.getByRole('combobox', { name: '归档人筛选' }), button('刷新成品')]) {
    await unclipped(el)
  }
  await page.screenshot({ path: '../../output/playwright/overseas-light-live/archive-mobile.png', fullPage: true })
  await page.goto(base + '/#/overseas/tasks'); await button('刷新任务').waitFor()
  for (const el of [page.getByRole('combobox', { name: '状态筛选' }), page.getByRole('combobox', { name: '设计负责人筛选' }), page.getByRole('textbox', { name: '搜索任务' }), button('刷新任务')]) await unclipped(el)
  await page.screenshot({ path: '../../output/playwright/overseas-light-live/tasks-mobile.png', fullPage: true })
  await page.goto(base + '/#/overseas/admin/activity'); await button('刷新数据').waitFor()
  await dateLayout()
  for (const el of [page.getByRole('combobox', { name: '执行操作者' }), page.getByPlaceholder('开始日期'), page.getByPlaceholder('结束日期'), button('刷新数据')]) await unclipped(el)
  await page.screenshot({ path: '../../output/playwright/overseas-light-live/activity-mobile.png', fullPage: true })
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, []); assert.deepEqual(missingAssets, [])
  console.log('PASS: 调用下钻、排队取消、负责人改派/删除、历史状态、分页范围、归档筛选/删除、错误重试、三页390px控件及资源请求')
} catch (error) {
  await page.screenshot({ path: '../../output/playwright/overseas-light-live/failure.png' })
  console.error('页面内容：', (await page.locator('body').innerText()).slice(0, 1800), '未预期请求：', unexpected)
  throw error
} finally { await browser.close() }
