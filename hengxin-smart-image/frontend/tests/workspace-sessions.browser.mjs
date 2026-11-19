// Formal Art application, isolated browser context and intercepted HTTP only.
import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { resolve, isAbsolute } from 'node:path'
import { pathToFileURL } from 'node:url'
import { verifyManagedViewer } from './workspace-viewer-browser-helpers.mjs'
const previewPng = await readFile(new URL('../preview-reference-edit/current.png', import.meta.url))
const moduleName = process.env.PLAYWRIGHT_MODULE || 'playwright'
const { chromium } = await import(isAbsolute(moduleName) ? pathToFileURL(moduleName).href : moduleName)
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3037'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const output = resolve(process.env.BROWSER_OUTPUT || '../../output/playwright/workspace-sessions')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: process.env.BROWSER_HEADLESS !== 'false', channel: process.env.BROWSER_CHANNEL || 'chrome' })
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, serviceWorkers: 'block' })
const page = await context.newPage(), errors = [], unexpected = [], calls = [], checks = [], geometry = []
page.on('pageerror', error => errors.push(error.message)); page.setDefaultTimeout(20000)
const stamp = '2026-11-17T02:00:00Z', root = '/api/v1/management/domestic-studio/sessions'
const routes = {
  camera: '/new-product/camera-accessories', case: '/new-product/phone-case',
  product: '/product-replace/product-only', scene: '/product-replace/scene-model-product-size', phone: '/product-replace/phone-wallpaper-film',
  film: '/new-product/screen-protector', cable: '/new-product/data-cable', earbud: '/new-product/earbud-case',
  accessory: '/new-product/creative-accessories', edit: '/product-replace/general-edit', general: '/new-product/general',
}
const keys = Object.keys(routes)
const states = ['running', 'queued', 'succeeded', 'failed', 'empty', 'cancelled', 'unknown']
const rows = Array.from({ length: 21 }, (_, index) => ({ id: `session-${index}`, name: `验收会话 ${index}`, ownerId: index < 15 ? 'member-a' : 'member-b', ownerName: index < 15 ? '真实成员甲' : '真实成员乙', workspace: [0, 1, 4].includes(index) ? 'camera' : keys[index % keys.length], taskId: `task-${[1, 4].includes(index) ? 0 : index}`, taskName: `验收任务 ${[1, 4].includes(index) ? 0 : index}`, status: states[index % 7], turnCount: index === 4 ? 0 : 1, createdAt: stamp, updatedAt: stamp, version: 1, activeTurnId: null }))
const taskRoot = '/api/v1/management/domestic-studio/tasks'
const tasks = Array.from({ length: 21 }, (_, index) => ({ id: `task-${index}`, name: `验收任务 ${index}`, ownerId: rows[index].ownerId, ownerName: rows[index].ownerName, workspace: rows[index].workspace, version: 1, completed: index % 3 === 0, conversationCount: rows.filter(row => row.taskId === `task-${index}`).length, activeConversationCount: 0, createdAt: stamp, updatedAt: stamp, deletionStatus: null, deletionError: null }))
const file = (id, kind, name, type) => ({ id: `${kind === 'files' ? 'upload:' : ''}${id}`, name, contentType: type, sizeBytes: 12, url: `${root}/session-0/${kind}/${id}/content`, ...(kind === 'files' ? { source: 'upload' } : {}) })
const picture = { ...file('picture-a', 'pictures', '已保存图片.png', 'image/png'), width: 1, height: 1, turnId: 'turn-session-0', sku: null, archived: false }
let viewer = { id: 'member-b', name: '真实成员乙', role: 'operator', status: 'active' }
let longContent = false
let failure = 0, revision = 0, held, release, deleted = false, authStatus = 200, authDelay = 0, authChecks = 0
const slowPaths = new Set()
const members = [{ id: 'member-a', name: '真实成员甲' }, { id: 'member-b', name: '真实成员乙' }]
function snapshot(id) {
  const row = rows.find(item => item.id === id)
  const turn = { id: `turn-${id}`, text: `完整已提交需求 ${id}${longContent ? '\n阅读位置验证'.repeat(80) : ''}`, skillName: '本轮实际技能', status: row.status, reply: revision ? '同步后新回复' : '已收到完整需求', error: row.status === 'failed' ? '执行失败原因' : null, jobId: 'job-a', jobVersion: 1, createdAt: stamp, actor: { id: row.ownerId, name: row.ownerName }, replyAt: stamp, replyTimeSource: 'message', conversationId: id, attachments: id === 'session-0' ? [file('input-a', 'files', '图需说明.txt', 'text/plain'), file('vector-a', 'files', '矢量附件.svg', 'image/svg+xml'), file('input-image', 'files', '参考图片.png', 'image/png'), file('input-image-b', 'files', '参考图片二.png', 'image/png')] : [], pictures: id === 'session-0' ? [picture, { ...picture, id: 'picture-b', name: '第二张图片.png', url: `${root}/session-0/pictures/picture-b/content` }] : [], referencePictures: [], outputs: id === 'session-0' ? [file('output-a', 'outputs', '正式输出.txt', 'text/plain'), file('output-image', 'outputs', '图片输出.png', 'image/png')] : [] }
  return { session: row, siblingSessions: rows.filter(item => item.taskId === row.taskId), workspace: { taskId: row.taskId, taskVersion: 1, conversationId: id, archiveId: null, completed: false, reopened: false, fixedSkillReady: false, skills: [], materials: [], activeTurnId: null, turns: row.turnCount ? [turn] : [] } }
}
await context.route('**/*', async route => {
  const request = route.request(), url = new URL(request.url()), path = url.pathname
  if (url.origin !== new URL(base).origin) return route.abort()
  if (!path.startsWith('/api/')) return route.continue()
  const json = (value, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(value) })
  if (path === '/api/identity/v1/config') return json({ configured: false, corpId: '', clientId: '' })
  if (path.endsWith('/auth/me')) {
    authChecks++
    if (authDelay) await new Promise(resolve => setTimeout(resolve, authDelay))
    return json(viewer, authStatus)
  }
  calls.push({ method: request.method(), path, query: url.search })
  if (slowPaths.has(path)) await new Promise(resolve => setTimeout(resolve, 800))
  if (request.method() !== 'GET') { unexpected.push(`${request.method()} ${path}`); return json({}, 405) }
  if (failure) return json({ detail: '隔离故障' }, failure)
  if (path === taskRoot || path === '/api/v1/domestic-studio/tasks') {
    const q = url.searchParams, all = tasks.filter(item => (!q.get('ownerId') || item.ownerId === q.get('ownerId')) && (!q.get('workspace') || item.workspace === q.get('workspace')) && item.name.includes(q.get('search') || ''))
    const filtered = all.filter(item => !q.get('status') || (q.get('status') === 'completed' ? item.completed : !item.completed)), pageNumber = Number(q.get('page') || 1), pageSize = Number(q.get('pageSize') || 20)
    return json({ items: filtered.slice((pageNumber - 1) * pageSize, pageNumber * pageSize), total: filtered.length, page: pageNumber, pageSize, counters: { total: all.length, active: all.filter(item => !item.completed).length, completed: all.filter(item => item.completed).length }, members })
  }
  if (path.startsWith(taskRoot + '/')) { const task = tasks.find(item => path === `${taskRoot}/${item.id}`); return task ? json({ task, sessions: rows.filter(row => row.taskId === task.id) }) : json({}, 404) }
  const shared = path.match(/^\/api\/v1\/domestic-studio\/tasks\/([^/]+)\/view\/([^/]+)(?:\/sessions(\/.*))?$/)
  if (shared && !shared[3]) {
    const task = tasks.find(row => row.id === shared[1] && row.workspace === shared[2])
    return task ? json({ task, sessions: rows.filter(row => row.taskId === task.id) }) : json({}, 404)
  }
  const sessionRoot = shared ? path.slice(0, -shared[3].length) : root
  if (!path.startsWith(sessionRoot)) { unexpected.push(path); return json({}, 501) }
  if (path === root) {
    const q = url.searchParams
    let items = rows.filter(item => (!q.get('ownerId') || item.ownerId === q.get('ownerId')) && (!q.get('workspace') || item.workspace === q.get('workspace')) && (!q.get('status') || item.status === q.get('status')) && item.name.includes(q.get('search') || ''))
    const counters = { total: items.length, ...Object.fromEntries(states.map(status => [status, items.filter(item => item.status === status).length])) }
    const pageNumber = Number(q.get('page') || 1), pageSize = Number(q.get('pageSize') || 10), total = items.length
    items = items.slice((pageNumber - 1) * pageSize, pageNumber * pageSize)
    return json({ items, total, page: pageNumber, pageSize, counters, members })
  }
  const [, id, tail] = path.slice(sessionRoot.length).match(/^\/([^/]+)(.*)$/) || []
  if (deleted) return json({}, 404)
  if (!tail) { if (held === id) await new Promise(resolve => { release = resolve }); return json(shared ? JSON.parse(JSON.stringify(snapshot(id)).replaceAll(root, sessionRoot)) : snapshot(id)) }
  if (tail === '/transcript') {
    const after = Number(url.searchParams.get('after') || 0)
    return json({ items: after < revision + 1 ? [{ id: revision + 1, itemId: 'process', turnId: `turn-${id}`, kind: 'tool', text: revision ? '新公开执行进度' : '公开执行过程', state: 'running', createdAt: stamp }] : [], cursor: revision + 1, hasMore: false })
  }
  if (url.searchParams.has('thumbnail') && url.searchParams.get('thumbnail') !== 'true') return json({}, 422)
  if (tail.endsWith('/content')) return (tail.includes('/pictures/') || tail.includes('image'))
    ? route.fulfill({ contentType: 'image/png', body: previewPng })
    : route.fulfill({ contentType: 'text/plain', body: '真实文件内容' })
  unexpected.push(path); return json({}, 501)
})
const refresh = async () => { const session = page.getByRole('button', { name: '刷新会话', exact: true }); await (await session.count() ? session : page.getByRole('button', { name: '刷新', exact: true })).click() }
const choose = id => page.locator('.tc-task-name').filter({ hasText: new RegExp(`^验收任务 ${id}$`) }).click()
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
async function verifyPolling(label, path, button, content, change, updated) {
  // hash路由切换有入场动画，等待完成后再记录轮询布局基线。
  await page.waitForTimeout(500)
  slowPaths.add(path)
  const before = await button.boundingBox()
  await content.evaluate(element => { window.__polledContent = element })
  for (let tick = 0; tick < 2; tick++) {
    const arrived = page.waitForRequest(request => new URL(request.url()).pathname === path)
    const completed = page.waitForResponse(response => new URL(response.url()).pathname === path)
    change(tick)
    await arrived
    for (let sample = 0; sample < 3; sample++) {
      await page.waitForTimeout(120)
      assert.equal(await button.evaluate(element => element.classList.contains('is-loading')), false, `${label}: 自动同步不转圈`)
      assert.equal(await page.locator('.tc-page .el-loading-mask:visible,.tc-page .el-skeleton:visible').count(), 0, `${label}: 自动同步不遮罩`)
      assert.deepEqual(await button.boundingBox(), before, `${label}: 自动同步按钮几何稳定`)
      assert.ok(await content.evaluate(element => element === window.__polledContent && element.isConnected), `${label}: 内容节点保持`)
    }
    await completed; await updated(tick)
  }
  await page.screenshot({ path: resolve(output, `${label}-polling.png`), fullPage: true })
  const completed = page.waitForResponse(response => new URL(response.url()).pathname === path)
  await button.click(); await page.waitForTimeout(120)
  assert.equal(await button.evaluate(element => element.classList.contains('is-loading')), true, `${label}: 主动刷新有反馈`)
  assert.deepEqual(await button.boundingBox(), before, `${label}: 手动刷新按钮几何稳定`)
  await completed
  await page.waitForFunction(() => !document.querySelector('.tc-page .wm-sync .is-loading'))
  slowPaths.delete(path)
  geometry.push({ label: `${label}-polling`, width: page.viewportSize().width, before, after: await button.boundingBox(), automaticTicks: 2, samplesPerTick: 3 })
  checks.push(`${label}: 两次真实3秒自动tick静默更新，内容节点及按钮几何保持；手动刷新反馈且宽度稳定`)
}
async function switchBrowserTab(label, content) {
  // 正式应用接收浏览器生命周期事件；不直接调用identity或改业务状态。
  const before = await content.innerText(), sync = page.locator('.wm-sync .el-switch').first()
  const checked = await sync.count() ? await sync.getAttribute('aria-checked') : null
  await page.evaluate(() => {
    Object.defineProperty(document, 'visibilityState', { configurable: true, value: 'hidden' })
    document.dispatchEvent(new Event('visibilitychange'))
  })
  assert.equal(await page.evaluate(() => document.documentElement.dataset.identityLocked), 'true')
  authDelay = 800
  const probes = authChecks
  await page.evaluate(() => {
    delete document.visibilityState
    document.dispatchEvent(new Event('visibilitychange'))
  })
  assert.equal(await page.evaluate(() => getComputedStyle(document.querySelector('.hx-protected-content')).visibility), 'hidden')
  await page.waitForFunction(() => !document.documentElement.dataset.identityLocked)
  assert.ok(authChecks > probes, '返回必须重新核验身份')
  assert.equal(await page.getByText('无权查看任务', { exact: true }).count(), 0)
  assert.equal(await content.innerText(), before)
  if (checked !== null) assert.equal(await sync.getAttribute('aria-checked'), checked)
  authDelay = 0
  checks.push(`${label}: 隐藏/恢复事件、重验前遮蔽、成功恢复内容与同步设置`)
}
try {
  tasks.push({ ...tasks[0], id: 'own-task', name: '本人任务', ownerId: viewer.id, ownerName: viewer.name })
  await page.goto(`${base}/#${routes.camera}`)
  const own = page.getByRole('row').filter({ hasText: '本人任务' })
  const peer = page.getByRole('row').filter({ has: page.getByRole('button', { name: '验收任务 0', exact: true }) })
  await own.getByRole('button', { name: '进入任务' }).waitFor()
  assert.equal(await own.getByLabel('更多任务操作').count(), 1)
  assert.equal(await peer.getByLabel('更多任务操作').count(), 0)
  await peer.getByRole('button', { name: '只读查看' }).click()
  await waitName(0)
  assert.equal(await page.getByRole('button', { name: /^(标记任务完成|重新打开任务|发送|归档到成品库)$/ }).count(), 0)
  assert.equal(await page.locator('.wm-readonly').innerText(), '◇ 只读查看 · 无法代发消息或修改用户内容')
  await page.getByRole('button', { name: '附件与结果', exact: true }).click()
  await page.getByRole('tab', { name: '生成结果' }).click()
  await page.getByRole('dialog').getByText('已保存图片.png', { exact: true }).first().waitFor()
  await page.keyboard.press('Escape')
  await page.screenshot({ path: resolve(output, 'member-shared-task.png'), fullPage: true })
  assert.ok(calls.some(item => item.path.includes('/view/camera/sessions/session-0/pictures/')))
  assert.ok(calls.every(item => item.method === 'GET' && !item.path.startsWith('/api/v1/management/') && !item.path.endsWith('/studio')))
  checks.push('同业务本人可操作，其他成员进入只读工作台、查看对话及结果，全部请求为业务 GET')
  tasks.pop()
  viewer = { id: 'admin', name: '隔离管理员', role: 'super_admin', status: 'active' }
  await page.goto('about:blank')
  {
    for (const [key, route] of Object.entries(routes)) {
      await page.goto(`${base}/#${route}`)
      const content = page.locator('.tc-task-name').first()
      await page.getByRole('button', { name: tasks.find(task => task.workspace === key).name, exact: true }).waitFor()
      await switchBrowserTab(route, content)
    }
  }
  await page.goto(`${base}/#/management/workspace-sessions`)
  await page.locator('.tc-task-name').first().waitFor()
  await page.waitForFunction(() => !document.querySelector('.el-loading-mask'))
  await verifyPolling('list', taskRoot, page.getByRole('button', { name: '刷新', exact: true }), page.locator('.tc-task-name').first(), tick => { tasks[0].name = `自动同步任务 ${tick}` }, tick => page.getByRole('button', { name: `自动同步任务 ${tick}`, exact: true }).waitFor())
  tasks[0].name = '验收任务 0'
  await page.locator('.wm-sync .el-switch').first().click()
  await switchBrowserTab('管理任务列表（暂停同步）', page.locator('.tc-task-name').first())
  assert.equal(await page.locator('.tc-task-name').count(), 20)
  await page.locator('.el-pagination .btn-next').click(); await page.locator('.tc-task-name').filter({ hasText: /^验收任务 20$/ }).waitFor()
  await page.getByRole('textbox', { name: '搜索任务名称' }).fill('验收任务 20')
  await page.locator('.tc-task-name').filter({ hasText: /^验收任务 20$/ }).waitFor(); assert.equal(await page.locator('.tc-task-name').count(), 1)
  await choose(20); await waitName(20); await page.getByRole('button', { name: '返回任务列表' }).click()
  assert.equal(await page.getByRole('textbox', { name: '搜索任务名称' }).inputValue(), '验收任务 20')
  await page.getByRole('button', { name: '重置筛选' }).click(); await page.locator('.tc-task-name').filter({ hasText: /^验收任务 0$/ }).waitFor()
  checks.push('真实请求分页、名称筛选、返回保留筛选、重置')
  for (const width of [1920, 1000, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1080 })
    if (width === 390) { await page.locator('.el-menu-item.is-active').first().click(); await page.waitForTimeout(350) }
    await bounds('刷新', page.getByRole('button', { name: '刷新', exact: true }))
    await bounds('重置筛选', page.getByRole('button', { name: '重置筛选' }))
    await page.screenshot({ path: resolve(output, `list-${width}.png`), fullPage: true })
  }
  await page.setViewportSize({ width: 1920, height: 1080 }); await choose(0); await waitName(0)
  await page.locator('.wm-sync .el-switch').first().click()
  await switchBrowserTab('管理员会话详情（自动同步）', page.locator('.wm-chat-heading strong'))
  await verifyPolling('detail', `${root}/session-0`, page.getByRole('button', { name: '刷新会话', exact: true }), page.locator('.wm-chat'), tick => { rows[0].name = `自动同步会话 ${tick}` }, tick => page.locator('.wm-chat-heading strong').filter({ hasText: `自动同步会话 ${tick}` }).waitFor())
  await page.locator('.wm-sync .el-switch').first().click()
  rows[0].name = '验收会话 0'; revision = 0; await refresh()
  await page.getByText('公开执行过程', { exact: true }).waitFor()
  assert.equal(await page.getByRole('textbox').count(), 0)
  assert.equal(await page.getByRole('button', { name: /^(发送|停止|删除|重试|取回文件|归档|修改这张)$/ }).count(), 0)
  await verifyManagedViewer({ page, output, checks, calls, root, waitName, refresh, setFailure: value => { failure = value }, setLongContent: value => { longContent = value } })
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
  failure = 503; await refresh(); await page.getByText('会话同步已中断', { exact: false }).waitFor(); assert.ok(await page.getByText('同步后新回复', { exact: true }).isVisible())
  failure = 0; await refresh(); await page.getByText('会话同步已中断', { exact: false }).waitFor({ state: 'hidden' })
  checks.push('手动增量同步、断线保留最近成功内容、恢复同步')
  for (const width of [1920, 1000, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1080 })
    if (width === 390) { await page.locator('.el-menu-item.is-active').first().click(); await page.waitForTimeout(350) }
    if (width > 700) await bounds('成员会话只读说明', page.locator('.wm-sidebar-note'))
    await bounds('只读说明', page.locator('.wm-readonly'))
    await bounds('附件与结果', page.getByRole('button', { name: '附件与结果', exact: true }))
    await page.screenshot({ path: resolve(output, `detail-${width}.png`), fullPage: true })
  }
  await page.setViewportSize({ width: 1920, height: 1080 })
  held = 'session-1'; await page.locator('.wm-conversation').filter({ has: page.getByText('验收会话 1', { exact: true }) }).click()
  await page.waitForTimeout(100); await page.evaluate(() => { location.hash = '#/management/workspace-sessions?session=session-2' }); await waitName(2)
  release?.(); held = undefined; await page.waitForTimeout(150); assert.equal(await page.locator('.wm-chat-heading strong').innerText(), '验收会话 2')
  await page.evaluate(() => { location.hash = '#/management/task-center?task=task-0&session=session-4' }); await waitName(4); await page.locator('.wm-conversation').filter({ has: page.getByText('验收会话 4', { exact: true }) }).click(); await waitName(4); await page.getByText('这个会话还没有提交消息', { exact: true }).waitFor()
  checks.push('同成员会话切换、迟到响应不串会话、空会话')
  deleted = true; await refresh(); await page.getByText('会话已删除或不可用，请返回列表。', { exact: true }).waitFor(); assert.equal(await page.locator('.wm-chat').count(), 0)
  deleted = false; await refresh(); await waitName(4)
  failure = 403; await refresh(); await page.getByText('无权查看任务', { exact: true }).waitFor()
  assert.equal(await page.locator('.wm-chat,.tc-task-name,.wm-managed-asset').count(), 0)
  checks.push('源会话删除及管理员撤权清除全部敏感内容')
  {
    failure = 0
    await page.reload(); await waitName(4)
    await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pagehide', { persisted: true })))
    authStatus = 401
    await page.evaluate(() => window.dispatchEvent(new PageTransitionEvent('pageshow', { persisted: true })))
    await page.waitForFunction(() => !document.querySelector('.wm-chat'))
    assert.equal(await page.locator('.tc-task-name,.wm-chat,.wm-managed-asset').count(), 0)
    checks.push('隐藏期间身份失效，返回重验401清除受保护内容')
  }
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, [])
  await writeFile(resolve(output, 'report.json'), JSON.stringify({ result: 'PASS', checks, geometry, errors, unexpected, calls }, null, 2))
  console.log(JSON.stringify({ result: 'PASS', checks, requests: calls.length }, null, 2))
} catch (error) {
  await page.screenshot({ path: resolve(output, 'failure.png'), fullPage: true }).catch(() => {})
  await writeFile(resolve(output, 'failure.json'), JSON.stringify({ error: String(error), errors, unexpected, geometry, calls }, null, 2)); throw error
} finally { release?.(); await context.close(); await browser.close() }
