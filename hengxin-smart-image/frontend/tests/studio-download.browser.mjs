// Real Vue/Element components with controlled API fault responses; never touches production.
import assert from 'node:assert/strict'
import { mkdir, readFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3032'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1366, height: 900 } }), page = await context.newPage()
page.setDefaultTimeout(20000)
const errors = [], unexpected = [], sends = [], caps = ['task.read', 'task.design', 'task.create']
page.on('pageerror', e => errors.push(e.message))
const task = { id: 't', name: '多会话交互验收', productName: '灯具', brand: 'HX', platform: 'Amazon', market: '美国', remarks: '', skus: [{ code: 'A' }], workflow: 'studio', status: 'studio', version: 1, createdAt: '2026-10-24', updatedAt: '2026-10-24', createdBy: { id: 'u', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: caps, events: [] }
const make = (id, name) => ({ id, name, version: 1, createdAt: '2026-10-24T01:00:00Z', updatedAt: '2026-10-24T01:00:00Z', activeTurnId: null, status: 'empty', turnCount: 0 })
const rows = [make('a', '主图方案'), make('b', '详情方案')], turns = { a: [], b: [] }
let failImage = false, holdImage = false, releaseImage, downloads = 0
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jD1sAAAAASUVORK5CYII=', 'base64')
const picture = id => ({ id, name: '同名.png', url: `/api/overseas/v1/tasks/t/studio/pictures/${id}/content`, width: 1, height: 1, turnId: 'turn1', sku: null, archived: false })
turns.a = [{ id: 'turn1', conversationId: 'a', text: '生成', status: 'succeeded', skillName: null, reply: '完成', error: null, jobId: 'job1', jobVersion: 1, attachments: [], referencePictures: [], pictures: [picture('p1'), picture('p2')], createdAt: '2026-11-02' }]
page.on('download', () => downloads++)
let completed = false, version = 1, deferredSend, deletionCount = 0, archiveId = null
const state = (id = rows[0]?.id || null) => ({ taskId: 't', taskVersion: version, archiveId, completed, reopened: version > 1 && !completed, conversationId: id,
  conversations: rows, maxConversations: 10, activeConversationCount: rows.filter(r => r.activeTurnId).length,
  turns: turns[id] || [], materials: [], skills: [{ id: 's', name: 'skill', displayName: '测试Skill', description: '' }], activeTurnId: rows.find(r => r.id === id)?.activeTurnId || null })
const button = name => page.getByRole('button', { name, exact: true })
const input = page.getByRole('textbox', { name: '设计要求', exact: true })
const choose = name => page.locator('.session-switch').filter({ has: page.getByText(name, { exact: true }) }).click()
async function ready() { await page.locator('.session-current strong').filter({ hasText: '方案' }).waitFor(); await input.waitFor(); await page.waitForFunction(() => !document.querySelector('[aria-label="设计要求"]').disabled) }
async function visibleWithin(locator) {
  assert.ok(await locator.evaluate(el => { const r = el.getBoundingClientRect(); if (!r.width || !r.height || r.left < 0 || r.right > innerWidth || r.top < 0 || r.bottom > innerHeight) return false;
    for (let p = el.parentElement; p; p = p.parentElement) { const style = getComputedStyle(p), bounds = p.getBoundingClientRect(); if (/(auto|scroll|hidden|clip)/.test(style.overflowY) && (r.top < bounds.top - 1 || r.bottom > bounds.bottom + 1)) return false } return true }))
}
try {
  await context.route('**/*', async route => {
    const url = new URL(route.request().url()), path = url.pathname, method = route.request().method(), requested = url.searchParams.get('conversationId')
    if (['api.iconify.design', 'api.unisvg.com', 'api.simplesvg.com'].includes(url.hostname)) return route.fulfill({ contentType: 'application/json', body: '{}' })
    if (url.origin !== base && !['data:', 'blob:'].includes(url.protocol)) { unexpected.push(url.href); return route.abort() }
    if (!path.startsWith('/api/')) return route.continue()
    if (path.includes('/studio/pictures/')) {
      if (!url.searchParams.has('thumbnail')) {
        if (failImage) return route.fulfill({ status: 503, body: 'failed' })
        if (holdImage) await new Promise(resolve => { releaseImage = resolve })
      }
      return route.fulfill({ contentType: 'image/png', body: method === 'HEAD' ? '' : png })
    }
    let body = {}, status = 200
    if (path.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (path === '/api/identity/v1/me') body = { name: '设计', sessionId: 'identity-test' }
    else if (path.endsWith('/tickets')) body = { ticket: 'test' }
    else if (path === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
    else if (path.includes('/auth/')) { body = { id: 'd', name: '设计', identitySessionId: 'identity-test', status: 'active', roles: ['designer'], capabilities: caps }; if (path.endsWith('/access')) body = { state: 'allowed', member: body } }
    else if (path.endsWith('/tasks/t/materials')) body = []
    else if (path.endsWith('/task-designers')) body = { items: [{ id: 'd', name: '设计', department: '设计部' }], total: 1, page: 1, pageSize: 20 }
    else if (path.endsWith('/studio/transcript')) { assert.ok(requested); body = { items: [], cursor: 0, hasMore: false } }
    else if (path.endsWith('/studio/turns')) {
      const data = route.request().postDataJSON(); sends.push(data); assert.ok(data.conversationId)
      const row = rows.find(r => r.id === data.conversationId); row.activeTurnId = `turn-${sends.length}`; row.status = 'queued'; row.updatedAt = '2026-10-24T02:00:00Z'; row.turnCount++
      if (data.text === '延迟请求') await new Promise(resolve => { deferredSend = resolve })
      body = state(data.conversationId)
    } else if (path.endsWith('/studio/conversations')) { const id = `n${rows.length}`; rows.push(make(id, `会话${rows.length + 1}`)); turns[id] = []; body = state(id) }
    else if (path.includes('/studio/conversations/')) {
      const id = path.split('/').at(-1), row = rows.find(r => r.id === id), data = route.request().postDataJSON()
      assert.ok(data.version); assert.ok(route.request().headers()['idempotency-key'])
      if (method === 'PATCH') { row.name = data.name; row.version++; body = state(id) }
      else { deletionCount++; row.deletionStatus = 'deleting'; body = state(id) }
    } else if (path.endsWith('/studio/complete')) { completed = true; task.status = 'completed'; version++; task.version = version; body = state() }
    else if (path.endsWith('/studio/reopen')) { completed = false; task.status = 'studio'; version++; task.version = version; body = state() }
    else if (path.endsWith('/studio')) body = state(requested || undefined)
    else if (path.endsWith('/tasks/t')) body = { ...task, status: completed ? 'completed' : 'studio', version }
    else { unexpected.push(path); status = 404 }
    return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  })
  const out = '../../output/playwright/studio-download'
  await mkdir(out, { recursive: true })
  await page.goto(`${base}/#/overseas/tasks/t`); await ready()
  assert.equal(await button('下载所选图片（0）').isDisabled(), true)
  await page.locator('.studio-picture-footer .el-checkbox').first().click()
  const partial = page.waitForEvent('download'); await button('下载所选图片（1）').click()
  await (await partial).saveAs(`${out}/partial.zip`)
  await page.getByText('全选本组', { exact: true }).click()
  const full = page.waitForEvent('download'); await button('下载所选图片（2）').click()
  await (await full).saveAs(`${out}/full.zip`)
  const parse = bytes => { const entries = []; let i = 0; while (bytes.readUInt32LE(i) === 0x04034b50) { const n = bytes.readUInt16LE(i + 26), size = bytes.readUInt32LE(i + 18), start = i + 30 + n; entries.push({ name: bytes.subarray(i + 30, start).toString(), data: bytes.subarray(start, start + size) }); i = start + size } return entries }
  for (const [file, count] of [['partial', 1], ['full', 2]]) { const files = parse(await readFile(`${out}/${file}.zip`)); assert.equal(files.length, count); assert.equal(new Set(files.map(f => f.name)).size, count); for (const f of files) assert.deepEqual(f.data, png) }
  failImage = true; await button('下载所选图片（2）').click(); await page.getByText('原图加载失败，请重试', { exact: true }).first().waitFor(); assert.equal(downloads, 2)
  failImage = false; const retry = page.waitForEvent('download'); await button('下载所选图片（2）').click(); await retry; assert.equal(downloads, 3)
  await page.screenshot({ path: `${out}/desktop.png`, fullPage: true })
  holdImage = true; await button('下载所选图片（2）').click()
  const deadline = Date.now() + 20000
  while (!releaseImage && Date.now() < deadline) await new Promise(resolve => setTimeout(resolve, 20))
  assert.ok(releaseImage, '下载应发起原图读取')
  await choose('详情方案'); releaseImage(); holdImage = false
  await button('下载所选图片（0）').waitFor(); assert.equal(downloads, 3)
  await choose('主图方案'); await page.setViewportSize({ width: 390, height: 844 }); await button('展开工作台').click()
  await page.locator('.session-list').getByRole('button', { name: '收起', exact: true }).click(); await button('任务素材 · 0').click()
  await visibleWithin(button('下载所选图片（2）')); await page.screenshot({ path: `${out}/mobile.png`, fullPage: true })
  await page.setViewportSize({ width: 1366, height: 900 }); await page.goto(`${base}/#/overseas/create`)
  await page.getByRole('heading', { name: '提交图需', exact: true }).waitFor()
  const field = label => page.locator('.el-form-item').filter({ has: page.locator('.el-form-item__label').filter({ hasText: label }) })
  assert.equal(await field('任务名称').locator('input').getAttribute('placeholder'), null)
  assert.ok((await field('目标平台').textContent()).includes('请选择目标平台'))
  await field('目标平台').locator('.el-select').click()
  await page.locator('.el-select-dropdown__item:visible').first().waitFor()
  assert.deepEqual(await page.locator('.el-select-dropdown:visible .el-select-dropdown__item').allTextContents(), ['亚马逊/Amazon','威费尔/Wayfair','美客多/Mercado Libre','沃尔玛/Walmart','家得宝/The Home Depot','虾皮/Shopee'])
  await page.keyboard.press('Escape'); await page.locator('.el-select-dropdown__item:visible').first().waitFor({ state: 'hidden' }); assert.ok((await field('品牌').textContent()).includes('请选择品牌'))
  await field('品牌').locator('.el-select').click()
  await page.getByRole('option', { name: 'OUTON', exact: true }).waitFor()
  assert.deepEqual(await page.locator('.el-select-dropdown:visible .el-select-dropdown__item').allTextContents(), ['OUTON','OUTONLIFE','BELEEV'])
  await page.getByRole('option', { name: 'OUTONLIFE', exact: true }).click(); assert.ok((await field('品牌').textContent()).includes('OUTONLIFE'))
  await page.screenshot({ path: `${out}/form.png`, fullPage: true })
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, [])
  console.log('PASS: 原图部分/全部ZIP字节校验、同名、空选、失败重试、切会话取消、桌面/窄屏裁切、新建表单平台/品牌/placeholder')
} catch (error) { console.error({ errors, unexpected, body: (await page.locator('body').innerText()).slice(0, 2000) }); throw error } finally { releaseImage?.(); await context.close(); await browser.close() }
