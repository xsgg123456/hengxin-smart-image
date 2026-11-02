// Real Vue/Element components, isolated browser storage and mocked local APIs only.
import assert from 'node:assert/strict'
import { mkdir } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3051'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const output = '../../output/playwright/workflow-collaborators'
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
const errors = [], unexpected = [], results = []
let activePage
const png = Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aV1cAAAAASUVORK5CYII=', 'base64')
try {
  for (const relationship of ['created', 'assigned', 'other']) {
    const writable = relationship !== 'other', writes = [], reads = []
    let granted = true
    const context = await browser.newContext({ viewport: { width: 1366, height: 900 } })
    const page = await context.newPage(); activePage = page; page.setDefaultTimeout(15000)
    page.on('pageerror', error => errors.push(error.message))
    const button = name => page.getByRole('button', { name, exact: true })
    const input = page.getByRole('textbox', { name: '设计要求', exact: true })
    const root = '/api/overseas/v1/tasks/t/studio'
    const task = { id: 't', name: `${relationship} 权限验收`, productName: '灯具', brand: 'OUTON', platform: 'Amazon', market: '', remarks: '', skus: [{ code: 'A' }], workflow: 'studio', status: 'pending_review', version: 1, createdAt: '2026-11-02', updatedAt: '2026-11-02', createdBy: { id: relationship === 'created' ? 'd' : 'other', name: '提交人' }, designer: { id: relationship === 'assigned' ? 'd' : 'other', name: '负责设计', status: 'active', eligible: true }, events: [], requirementsReviews: [] }
    const caps = () => ['task.read', ...(writable && granted ? ['task.design', ...(task.status === 'pending_review' ? ['task.requirements.review'] : task.status === 'returned' ? ['task.requirements.resubmit'] : task.status === 'created' ? ['task.materials.submit'] : [])] : [])]
    const detail = () => ({ ...task, capabilities: caps() })
    const row = (id, name) => ({ id, name, version: 1, createdAt: '2026-11-02T01:00:00Z', updatedAt: '2026-11-02T01:00:00Z', activeTurnId: null, status: 'succeeded', turnCount: 1 })
    let rows = [row('a', '主图方案'), row('b', '详情方案')], archiveId = 'archive', running = false
    const asset = { id: 'upload:f', name: '消息附件.txt', contentType: 'text/plain', sizeBytes: 4, url: `${root}/files/f/content`, source: 'upload' }
    const picture = { id: 'p', name: '生成图片.png', url: `${root}/pictures/p/content`, width: 1, height: 1, turnId: 'turn', sku: null, archived: false }
    const file = { id: 'o', name: '输出文件.txt', contentType: 'text/plain', sizeBytes: 4, url: `${root}/outputs/o/content` }
    let materials = [asset]
    const state = (id = rows[0]?.id || null) => ({ taskId: 't', taskVersion: task.version, archiveId, completed: task.status === 'completed', reopened: false, conversationId: id,
      conversations: rows.map(r => ({ ...r, activeTurnId: running && r.id === 'a' ? 'turn' : null, status: running && r.id === 'a' ? 'running' : r.status })), maxConversations: 10, activeConversationCount: running ? 1 : 0,
      turns: id === 'a' ? [{ id: 'turn', text: '历史设计要求', reply: '历史设计回复', status: running ? 'running' : 'succeeded', skillName: null, error: null, jobId: 'job', jobVersion: 1, conversationId: 'a', createdAt: '2026-11-02T01:00:00Z', attachments: [asset], referencePictures: [], pictures: [picture], outputs: [file] }] : [], materials, skills: [], activeTurnId: running && id === 'a' ? 'turn' : null })
    await context.route('**/*', async route => {
      const req = route.request(), url = new URL(req.url()), path = url.pathname, method = req.method()
      if (['api.iconify.design', 'api.unisvg.com', 'api.simplesvg.com'].includes(url.hostname)) return route.fulfill({ json: {} })
      if (url.origin !== base) { unexpected.push(url.href); return route.abort() }
      if (!path.startsWith('/api/')) return route.continue()
      if (path.startsWith('/api/overseas/v1/') && !path.includes('/auth/')) {
        if (['GET', 'HEAD'].includes(method)) reads.push(path)
        else writes.push({ method, path, body: req.postData() })
      }
      let body = {}, status = 200
      if (path.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
      else if (path === '/api/identity/v1/me') body = { name: '权限验收设计', sessionId: 'identity-test' }
      else if (path.endsWith('/tickets')) body = { ticket: 'test' }
      else if (path === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
      else if (path.includes('/auth/')) {
        // Global member capabilities deliberately include design, even for the read-only task.
        body = { id: 'd', name: '权限验收设计', identitySessionId: 'identity-test', status: 'active', roles: ['designer'], capabilities: ['task.read', 'task.create', 'task.design', ...(granted ? ['task.workflow.collaborate'] : [])] }
        if (path.endsWith('/access')) body = { state: 'allowed', member: body }
      } else if (path.startsWith(root) && /\/(content|thumbnail|preview)$/.test(path)) {
        return route.fulfill({ contentType: path.includes('/pictures/') ? 'image/png' : 'text/plain', body: path.includes('/pictures/') ? png : 'test' })
      } else if (path.endsWith('/studio/transcript')) body = { items: [], cursor: 0, hasMore: false }
      else if (path === root) body = state(url.searchParams.get('conversationId') || undefined)
      else if (path.endsWith('/recoverable-files')) body = { items: [{ id: 'f', name: '未保存文件.txt', path: 'outputs/file.txt', source: 'work', sizeBytes: 4, version: 'v1' }], busy: false }
      else if (path.endsWith('/recover-files')) body = { saved: [{ id: 'f', kind: 'file' }], errors: [] }
      else if (path === `${root}/conversations` && method === 'POST') { rows.push(row('c', '新会话')); body = state('c') }
      else if (path === `${root}/conversations/c`) {
        if (method === 'PATCH') rows.find(r => r.id === 'c').name = req.postDataJSON().name
        if (method === 'DELETE') rows = rows.filter(r => r.id !== 'c')
        body = state(method === 'DELETE' ? 'a' : 'c')
      } else if (path.endsWith('/turns') && method === 'POST') body = state(req.postDataJSON().conversationId)
      else if (path.endsWith('/cancel')) { running = false; body = state('a') }
      else if (path === `${root}/files` && method === 'POST') body = asset
      else if (path.startsWith(`${root}/materials/`) && method === 'DELETE') { materials = []; body = state('a') }
      else if (path.endsWith('/archive') && method === 'POST') { archiveId = 'archive'; body = state('a') }
      else if (path.endsWith('/complete') || path.endsWith('/reopen')) { task.status = path.endsWith('/complete') ? 'completed' : 'studio'; task.version++; body = state('a') }
      else if (path.endsWith('/requirements-review')) { task.status = 'studio'; task.version++; body = detail() }
      else if (path.endsWith('/tasks/t/materials')) body = [{ id: 'm', kind: 'requirement', name: '图需.txt', contentType: 'text/plain', sizeBytes: 4, taskId: 't', status: 'ready', createdAt: '2026-11-02' }]
      else if (path.endsWith('/tasks/t')) body = detail()
      else if (path.endsWith('/task-designers')) body = { items: [{ id: task.designer.id, name: '负责设计', department: '' }], total: 1, page: 1, pageSize: 20 }
      else { unexpected.push(`${method} ${path}`); status = 404 }
      return route.fulfill({ status, json: body })
    })
    async function load() { await page.goto(`${base}/#/overseas/tasks/t`); await page.reload(); await button('刷新任务详情').waitFor() }
    async function studioReady() { await page.locator('.session-current strong').getByText('主图方案', { exact: true }).waitFor(); await input.waitFor() }
    await load(); await page.getByRole('heading', { name: '审核结论', exact: true }).waitFor()
    assert.equal(await button('审核通过，进入工作台').count(), writable ? 1 : 0)
    assert.equal(await button('退回提交人修改').count(), writable ? 1 : 0)
    if (writable) { await button('审核通过，进入工作台').click(); await page.getByRole('dialog').getByRole('button', { name: '确认', exact: true }).click(); await studioReady() }
    task.status = 'returned'; await page.reload(); await page.getByRole('heading', { name: '审核结论', exact: true }).waitFor()
    assert.equal(await button('修改图需并重新提交').count(), writable ? 1 : 0)
    if (writable) { await button('修改图需并重新提交').click(); await button('重新提交设计审核').waitFor(); assert.equal(await button('重新提交设计审核').isEnabled(), true) }
    task.status = 'studio'; await page.reload(); await studioReady()
    assert.equal(await button('改派设计').count(), 0)
    assert.equal(await page.getByText('用户与角色', { exact: true }).count(), 0)
    assert.equal(await input.isEnabled(), writable)
    assert.equal(await button('＋ 新建会话').isEnabled(), writable)
    assert.equal(await button('重命名').isEnabled(), writable)
    assert.equal(await button('完成任务').isEnabled(), writable)
    await page.getByText('历史设计要求', { exact: true }).waitFor()
    await page.getByText('历史设计回复', { exact: true }).waitFor()
    await page.getByRole('button', { name: '预览 生成图片.png', exact: true }).click()
    await page.locator('.el-image-viewer__wrapper').waitFor(); await page.keyboard.press('Escape')
    for (const selector of ['.studio-message.user .studio-image-file', '[aria-label="本轮输出文件"] .studio-image-file']) {
      await Promise.all([page.waitForEvent('download'), page.locator(selector).getByRole('button', { name: '下载原文件', exact: true }).click()])
    }
    await button('管理主图方案').click()
    assert.equal(await page.getByRole('menuitem', { name: '删除会话', exact: true }).getAttribute('aria-disabled'), writable ? 'false' : 'true')
    await page.keyboard.press('Escape'); await input.click({ force: true })
    await button('取回文件').click(); await page.locator('.recovery-file').getByText('未保存文件.txt', { exact: true }).waitFor()
    assert.equal(await page.getByRole('checkbox', { name: '选择 未保存文件.txt', exact: true }).isEnabled(), writable)
    if (writable) { await page.locator('.recovery-file .el-checkbox').click(); await button('取回所选文件').click(); await page.getByText('已保存 1 个文件，0 个未保存。', { exact: true }).waitFor() }
    else assert.equal(await button('取回所选文件').isEnabled(), false)
    await button('关闭').click()
    if (writable) {
      await input.fill(`${relationship} 发送要求`); await button('发送').click()
      await page.waitForFunction(() => document.querySelector('[aria-label="设计要求"]').value === '')
      await button('＋ 新建会话').click(); await page.locator('.session-current strong').getByText('新会话', { exact: true }).waitFor()
      await button('重命名').click(); await page.locator('.el-message-box input').fill('修改名称'); await button('保存').click()
      await page.locator('.session-current strong').getByText('修改名称', { exact: true }).waitFor()
      await button('管理修改名称').click(); await page.getByRole('menuitem', { name: '删除会话', exact: true }).click(); await button('确认删除').click(); await studioReady()
      await page.locator('.studio-composer input[type=file]').setInputFiles({ name: '材料.txt', mimeType: 'text/plain', buffer: Buffer.from('test') })
      await page.getByRole('button', { name: '移除 消息附件.txt', exact: true }).waitFor()
      await button('从列表移除 消息附件.txt').click(); await page.getByRole('dialog').getByRole('button', { name: '移除', exact: true }).click()
      await page.getByText('暂无任务素材', { exact: true }).waitFor()
      await page.locator('.studio-picture-footer .el-checkbox').click(); await button('归档所选图片（1）').click()
      await page.getByRole('dialog', { name: '归档所选图片', exact: true }).locator('.el-select').click(); await page.getByRole('option', { name: 'A', exact: true }).click(); await button('确认归档').click()
      await page.getByRole('dialog', { name: '归档所选图片', exact: true }).waitFor({ state: 'hidden' })
    } else {
      for (const name of ['发送', '修改这张', '归档所选图片（0）', '从列表移除 消息附件.txt']) assert.equal(await button(name).isEnabled(), false, name)
      // Exercise hidden native input and file drop/paste handlers, not just disabled buttons.
      await page.locator('.studio-composer input[type=file]').setInputFiles({ name: '越权.txt', mimeType: 'text/plain', buffer: Buffer.from('test') })
      await page.locator('.studio-composer').evaluate(el => {
        const data = new DataTransfer(); data.items.add(new File(['test'], '越权.txt', { type: 'text/plain' }))
        el.dispatchEvent(new DragEvent('drop', { bubbles: true, dataTransfer: data }))
        el.dispatchEvent(new ClipboardEvent('paste', { bubbles: true, clipboardData: data }))
      })
      await page.locator('.session-switch').filter({ hasText: '详情方案' }).click(); await page.locator('.session-current strong').getByText('详情方案', { exact: true }).waitFor()
      await page.locator('.session-switch').filter({ hasText: '主图方案' }).click(); await studioReady()
    }
    running = true; await button('刷新').click(); await button('停止').waitFor(); assert.equal(await button('停止').isEnabled(), writable)
    if (writable) { await button('停止').click(); await button('发送').waitFor() }
    else running = false
    if (writable) { await button('完成任务').click(); await button('确认完成').click(); await button('解冻工作台').waitFor() }
    else { task.status = 'completed'; task.version++; await page.reload(); await studioReady() }
    assert.equal(await button('解冻工作台').isEnabled(), writable)
    if (writable) { await button('解冻工作台').click(); await button('确认解冻').click(); await button('完成任务').waitFor() }
    else {
      task.status = 'studio'; task.version++
      await page.evaluate(() => {
        sessionStorage.setItem('hx-studio-sessions:["d","t"]:pending', JSON.stringify({ key: 'previous-session-request', kind: 'create' }))
        sessionStorage.setItem('hx-studio-pending:d:t:a', JSON.stringify({ key: 'previous-send-request', kind: 'send', body: { conversationId: 'a', text: '待核实消息', skillId: null, attachmentIds: [], referencePictureIds: [] }, draftConversationId: 'a' }))
      })
      await page.reload(); await studioReady()
      assert.equal(await button('核实会话操作').isEnabled(), false)
      assert.equal(await button('核实并重试上次操作').isEnabled(), false)
      // Dispatch click on disabled controls too: controller guards must independently hold.
      await button('核实会话操作').dispatchEvent('click'); await button('核实并重试上次操作').dispatchEvent('click')
      await button('刷新').click(); await page.waitForResponse(r => r.url().includes('/studio/transcript'))
      assert.deepEqual(writes, [], '只读访问、读取附件、切换会话、隐藏上传与待核实请求均不能写入')
    }
    if (writable) for (const suffix of ['/requirements-review', '/recover-files', '/turns', '/conversations', '/conversations/c', '/files', '/materials/upload%3Af', '/archive', '/cancel', '/complete', '/reopen']) assert.ok(writes.some(w => w.path.endsWith(suffix)), `missing writable operation ${suffix}`)
    if (relationship === 'created') {
      // Same actor, role, task version and identity session: only the grant marker disappears.
      const requestsBefore = reads.filter(path => path.endsWith('/tasks/t')).length, writesBefore = writes.length
      granted = false
      await page.evaluate(() => window.dispatchEvent(new Event('focus')))
      await page.waitForFunction(() => document.querySelector('[aria-label="设计要求"]')?.disabled === true && !document.body.inert)
      assert.ok(reads.filter(path => path.endsWith('/tasks/t')).length > requestsBefore, '授权范围撤销须重新读取任务能力')
      assert.equal(await button('＋ 新建会话').isEnabled(), false)
      assert.equal(await button('重命名').isEnabled(), false)
      assert.equal(writes.length, writesBefore, '身份重验不能补交任何旧写操作')
    }
    assert.ok(reads.some(p => p.endsWith('/outputs/o/content')))
    assert.ok(reads.some(p => p.endsWith('/files/f/content')))
    assert.ok(reads.some(p => p.endsWith('/pictures/p/content')))
    await page.screenshot({ path: `${output}/${relationship}.png`, fullPage: true })
    results.push({ relationship, writable, writes: writes.length, reads: reads.length })
    await context.close()
  }
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, [])
  console.log('PASS workflow collaborator capability UI', JSON.stringify(results))
} catch (error) {
  if (activePage && !activePage.isClosed()) { await activePage.screenshot({ path: `${output}/failure.png`, fullPage: true }); console.error({ errors, unexpected, text: await activePage.locator('body').innerText() }) }
  throw error
} finally { await browser.close() }
