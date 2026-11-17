// Formal Art application, isolated browser context and intercepted HTTP only.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve, isAbsolute } from 'node:path'
import { pathToFileURL } from 'node:url'
const moduleName = process.env.PLAYWRIGHT_MODULE || 'playwright'
const { chromium } = await import(isAbsolute(moduleName) ? pathToFileURL(moduleName).href : moduleName)
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3037'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const output = resolve(process.env.BROWSER_OUTPUT || '../../output/playwright/workspace-sessions')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true, channel: process.env.BROWSER_CHANNEL || 'chrome' })
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, serviceWorkers: 'block' })
const page = await context.newPage(), errors = [], unexpected = [], calls = [], checks = [], geometry = []
page.on('pageerror', error => errors.push(error.message)); page.setDefaultTimeout(20000)
const stamp = '2026-11-17T02:00:00Z', root = '/api/v1/management/domestic-studio/sessions'
const keys = ['camera', 'case', 'product', 'scene', 'phone']
const states = ['running', 'queued', 'succeeded', 'failed', 'empty', 'cancelled', 'unknown']
const rows = Array.from({ length: 21 }, (_, index) => ({ id: `session-${index}`, name: `验收会话 ${index}`, ownerId: index < 15 ? 'member-a' : 'member-b', ownerName: index < 15 ? '真实成员甲' : '真实成员乙', workspace: keys[index % 5], status: states[index % 7], turnCount: index === 4 ? 0 : 1, createdAt: stamp, updatedAt: stamp, version: 1, activeTurnId: null }))
const file = (id, kind, name, type) => ({ id: `${kind === 'files' ? 'upload:' : ''}${id}`, name, contentType: type, sizeBytes: 12, url: `${root}/session-0/${kind}/${id}/content`, ...(kind === 'files' ? { source: 'upload' } : {}) })
const picture = { ...file('picture-a', 'pictures', '已保存图片.png', 'image/png'), width: 1, height: 1, turnId: 'turn-session-0', sku: null, archived: false }
let failure = 0, revision = 0, held, release, deleted = false
const members = [{ id: 'member-a', name: '真实成员甲' }, { id: 'member-b', name: '真实成员乙' }]
function snapshot(id) {
  const row = rows.find(item => item.id === id)
  const turn = { id: `turn-${id}`, text: `完整已提交需求 ${id}`, skillName: '本轮实际技能', status: row.status, reply: revision ? '同步后新回复' : '已收到完整需求', error: row.status === 'failed' ? '执行失败原因' : null, jobId: 'job-a', jobVersion: 1, createdAt: stamp, actor: { id: row.ownerId, name: row.ownerName }, replyAt: stamp, replyTimeSource: 'message', conversationId: id, attachments: id === 'session-0' ? [file('input-a', 'files', '图需说明.txt', 'text/plain'), file('vector-a', 'files', '矢量附件.svg', 'image/svg+xml')] : [], pictures: id === 'session-0' ? [picture] : [], referencePictures: [], outputs: id === 'session-0' ? [file('output-a', 'outputs', '正式输出.txt', 'text/plain')] : [] }
  return { session: row, siblingSessions: rows.filter(item => item.ownerId === row.ownerId), workspace: { taskId: row.workspace, taskVersion: 1, conversationId: id, archiveId: null, completed: false, reopened: false, fixedSkillReady: false, skills: [], materials: [], activeTurnId: null, turns: row.turnCount ? [turn] : [] } }
}
await context.route('**/*', async route => {
  const request = route.request(), url = new URL(request.url()), path = url.pathname
  if (url.origin !== new URL(base).origin) return route.abort()
  if (!path.startsWith('/api/')) return route.continue()
  const json = (value, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) })
  if (path.endsWith('/auth/me')) return json({ id: 'admin', name: '隔离管理员', role: 'super_admin', status: 'active' })
  calls.push({ method: request.method(), path, query: url.search })
  if (request.method() !== 'GET') { unexpected.push(`${request.method()} ${path}`); return json({}, 405) }
  if (!path.startsWith(root)) { unexpected.push(path); return json({}, 501) }
  if (failure) return json({ detail: '隔离故障' }, failure)
  if (path === root) {
    const q = url.searchParams
    let items = rows.filter(item => (!q.get('ownerId') || item.ownerId === q.get('ownerId')) && (!q.get('workspace') || item.workspace === q.get('workspace')) && (!q.get('status') || item.status === q.get('status')) && item.name.includes(q.get('search') || ''))
    const counters = { total: items.length, ...Object.fromEntries(states.map(status => [status, items.filter(item => item.status === status).length])) }
    const pageNumber = Number(q.get('page') || 1), pageSize = Number(q.get('pageSize') || 10), total = items.length
    items = items.slice((pageNumber - 1) * pageSize, pageNumber * pageSize)
    return json({ items, total, page: pageNumber, pageSize, counters, members })
  }
  const [, id, tail] = path.slice(root.length).match(/^\/([^/]+)(.*)$/) || []
  if (deleted) return json({}, 404)
  if (!tail) { if (held === id) await new Promise(resolve => { release = resolve }); return json(snapshot(id)) }
  if (tail === '/transcript') {
    const after = Number(url.searchParams.get('after') || 0)
    return json({ items: after < revision + 1 ? [{ id: revision + 1, itemId: 'process', turnId: `turn-${id}`, kind: 'tool', text: revision ? '新公开执行进度' : '公开执行过程', state: 'running', createdAt: stamp }] : [], cursor: revision + 1, hasMore: false })
  }
  if (url.searchParams.has('thumbnail') && url.searchParams.get('thumbnail') !== 'true') return json({}, 422)
  if (tail.endsWith('/content')) return tail.includes('/pictures/')
    ? route.fulfill({ contentType: 'image/png', body: Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j39sAAAAASUVORK5CYII=', 'base64') })
    : route.fulfill({ contentType: 'text/plain', body: '真实文件内容' })
  unexpected.push(path); return json({}, 501)
})
const refresh = () => page.getByRole('button', { name: '刷新', exact: true }).click()
const choose = id => page.locator('.wm-name').filter({ hasText: new RegExp(`^验收会话 ${id}$`) }).click()
const waitName = id => page.locator('.wm-chat-heading strong').filter({ hasText: new RegExp(`^验收会话 ${id}$`) }).waitFor()
async function bounds(label, locator) {
  await locator.scrollIntoViewIfNeeded()
  const result = await locator.evaluate(element => {
    const r = element.getBoundingClientRect(), clipped = []
    for (let p = element.parentElement; p; p = p.parentElement) {
      const s = getComputedStyle(p), b = p.getBoundingClientRect()
      if (/(auto|scroll|hidden|clip)/.test(s.overflowX) && (r.left < b.left - 2 || r.right > b.right + 2)) clipped.push(`${p.className}:x`)
      if (/(auto|scroll|hidden|clip)/.test(s.overflowY) && (r.top < b.top - 2 || r.bottom > b.bottom + 2)) clipped.push(`${p.className}:y`)
    }
    return { clipped, viewport: r.left >= -1 && r.right <= innerWidth + 1 && r.top >= -1 && r.bottom <= innerHeight + 1, overflow: document.documentElement.scrollWidth > innerWidth + 1 }
  })
  geometry.push({ label, width: page.viewportSize().width, ...result })
  assert.deepEqual(result.clipped, [], label); assert.ok(result.viewport && !result.overflow, `${label}: ${JSON.stringify(result)}`)
}
try {
  await page.goto(`${base}/#/management/workspace-sessions`)
  await page.locator('.wm-name').first().waitFor()
  await page.locator('.wm-sync .el-switch').click()
  assert.equal(await page.locator('.wm-name').count(), 10)
  await page.locator('.el-pagination .btn-next').click(); await page.locator('.wm-name').filter({ hasText: /^验收会话 10$/ }).waitFor()
  await page.getByRole('textbox', { name: '搜索会话名称' }).fill('验收会话 20')
  await page.locator('.wm-name').filter({ hasText: /^验收会话 20$/ }).waitFor(); assert.equal(await page.locator('.wm-name').count(), 1)
  await choose(20); await waitName(20); await page.getByRole('button', { name: '← 返回会话列表' }).click()
  assert.equal(await page.getByRole('textbox', { name: '搜索会话名称' }).inputValue(), '验收会话 20')
  await page.getByRole('button', { name: '重置筛选' }).click(); await page.locator('.wm-name').filter({ hasText: /^验收会话 0$/ }).waitFor()
  checks.push('真实请求分页、名称筛选、返回保留筛选、重置')
  for (const width of [1920, 1000, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1080 })
    if (width === 390) { await page.locator('.el-menu-item.is-active').first().click(); await page.waitForTimeout(350) }
    await bounds('刷新', page.getByRole('button', { name: '刷新', exact: true }))
    await bounds('重置筛选', page.getByRole('button', { name: '重置筛选' }))
    await page.screenshot({ path: resolve(output, `list-${width}.png`), fullPage: true })
  }
  await page.setViewportSize({ width: 1920, height: 1080 }); await choose(0); await waitName(0)
  await page.getByText('公开执行过程', { exact: true }).waitFor()
  assert.equal(await page.getByRole('textbox').count(), 0)
  assert.equal(await page.getByRole('button', { name: /^(发送|停止|删除|重试|取回文件|归档|修改这张)$/ }).count(), 0)
  const vector = page.locator('.wm-managed-asset').filter({ hasText: '矢量附件.svg' })
  assert.equal(await vector.getByRole('button', { name: '预览', exact: true }).count(), 0)
  const vectorDownload = page.waitForEvent('download'); await vector.getByRole('button', { name: '下载', exact: true }).click(); await vectorDownload
  assert.equal(calls.some(call => call.path.includes('vector-a') && call.query.includes('thumbnail')), false)
  const card = page.locator('.wm-managed-asset').filter({ hasText: '正式输出.txt' })
  const downloadEvent = page.waitForEvent('download'); await card.getByRole('button', { name: '下载', exact: true }).click(); await downloadEvent
  await page.locator('.wm-managed-asset').filter({ hasText: '已保存图片.png' }).getByRole('button', { name: '预览', exact: true }).click()
  await page.locator('.el-image-viewer__wrapper').waitFor(); await page.keyboard.press('Escape')
  await page.getByRole('button', { name: '附件与结果', exact: true }).click(); await page.getByRole('dialog').waitFor()
  await page.getByRole('dialog').getByText('图需说明.txt', { exact: true }).waitFor(); await page.keyboard.press('Escape')
  checks.push('完整已提交消息/实际技能/公开过程、真实图片预览与文件下载、纯只读附件面板')
  revision = 1; await refresh(); await page.getByText('新公开执行进度', { exact: true }).waitFor(); await page.getByText('同步后新回复', { exact: true }).waitFor()
  failure = 503; await refresh(); await page.getByText('同步已中断，当前显示最后一次成功内容', { exact: false }).waitFor(); assert.ok(await page.getByText('同步后新回复', { exact: true }).isVisible())
  failure = 0; await refresh(); await page.getByText('同步已中断，当前显示最后一次成功内容', { exact: false }).waitFor({ state: 'hidden' })
  checks.push('手动增量同步、断线保留最近成功内容、恢复同步')
  for (const width of [1920, 1000, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1080 })
    if (width > 700) await bounds('成员会话只读说明', page.locator('.wm-sidebar-note'))
    await bounds('只读说明', page.locator('.wm-readonly'))
    await bounds('附件与结果', page.getByRole('button', { name: '附件与结果', exact: true }))
    await page.screenshot({ path: resolve(output, `detail-${width}.png`), fullPage: true })
  }
  await page.setViewportSize({ width: 1920, height: 1080 })
  held = 'session-1'; await page.locator('.wm-conversation').filter({ has: page.getByText('验收会话 1', { exact: true }) }).click()
  await page.waitForTimeout(100); await page.evaluate(() => { location.hash = '#/management/workspace-sessions?session=session-2' }); await waitName(2)
  release?.(); held = undefined; await page.waitForTimeout(150); assert.equal(await page.locator('.wm-chat-heading strong').innerText(), '验收会话 2')
  await page.locator('.wm-conversation').filter({ has: page.getByText('验收会话 4', { exact: true }) }).click(); await waitName(4); await page.getByText('这个会话还没有提交消息', { exact: true }).waitFor()
  checks.push('同成员会话切换、迟到响应不串会话、空会话')
  deleted = true; await refresh(); await page.getByText('会话已删除或不可用，请返回列表。', { exact: true }).waitFor(); assert.equal(await page.locator('.wm-chat').count(), 0)
  deleted = false; await refresh(); await waitName(4)
  failure = 403; await refresh(); await page.getByText('仅超级管理员可查看', { exact: true }).waitFor()
  assert.equal(await page.locator('.wm-chat,.wm-name,.wm-managed-asset').count(), 0)
  checks.push('源会话删除及管理员撤权清除全部敏感内容')
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, [])
  await writeFile(resolve(output, 'report.json'), JSON.stringify({ result: 'PASS', checks, geometry, errors, unexpected, calls }, null, 2))
  console.log(JSON.stringify({ result: 'PASS', checks, requests: calls.length }, null, 2))
} catch (error) {
  await page.screenshot({ path: resolve(output, 'failure.png'), fullPage: true }).catch(() => {})
  await writeFile(resolve(output, 'failure.json'), JSON.stringify({ error: String(error), errors, unexpected, geometry, calls }, null, 2)); throw error
} finally { release?.(); await context.close(); await browser.close() }
