// Disposable browser context; only loopback frontend and intercepted APIs. No production writes.
import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3037'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const out = '../../output/playwright/studio-batch'
await mkdir(out, { recursive: true })
const browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : {}) })
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 } }), page = await context.newPage()
page.setDefaultTimeout(12000)
const errors = [], unexpected = [], checks = [], sends = [], uploads = new Map()
const check = (value, name) => { assert.ok(value, name); checks.push(name); console.log('PASS', name) }
page.on('pageerror', e => errors.push(e.message))
const sample = await readFile('preview-ai-studio/assets/sample-1.jpg')
const pictures = Array.from({ length: 6 }, (_, i) => ({ id: `p${i + 1}`, name: `0${i + 1}.jpg`, width: 1250, height: 1600, turnId: 'r', url: `${'/api/overseas/v1/tasks/t/studio'}/pictures/p${i + 1}/content`, sku: null, archived: false }))
const caps = ['task.read', 'task.design']
const task = { id: 't', name: '批量画布正式组件验收', productName: '灯具', brand: 'OUTON', platform: 'Amazon', market: '美国', remarks: '', skus: [{ code: 'A' }], workflow: 'studio', status: 'studio', version: 1, createdAt: '2026-11-05', updatedAt: '2026-11-05', createdBy: { id: 'u', name: '运营' }, designer: { id: 'd', name: '设计', status: 'active', eligible: true }, capabilities: caps, events: [] }
const row = id => ({ id, name: id === 'a' ? '主图方案' : '另一会话', version: 1, createdAt: '2026-11-05T01:00:00Z', updatedAt: '2026-11-05T01:00:00Z', activeTurnId: null, status: 'succeeded', turnCount: id === 'a' ? 1 : 0 })
const turn = (id, extra = {}) => ({ id, text: '检查这一组图片', skillName: null, status: 'succeeded', reply: '图片已保存', error: null, jobId: 'j', jobVersion: 1, attachments: [], pictures: [], referencePictures: [], createdAt: '2026-11-05T01:00:00Z', conversationId: 'a', ...extra })
const turns = { a: [turn('r', { pictures })], b: [] }, materials = []
const state = (id = 'a') => ({ taskId: 't', taskVersion: 1, archiveId: null, completed: false, reopened: false, conversationId: id, conversations: [row('a'), row('b')], activeConversationCount: 0, maxConversations: 10, turns: turns[id], materials, skills: [], activeTurnId: null })
let failUpload = false, failSend = false, readFailure = false
const button = name => page.getByRole('button', { name, exact: true })
const ready = async () => { await page.getByRole('textbox', { name: '设计要求', exact: true }).waitFor(); await page.waitForFunction(() => !document.querySelector('[aria-label="设计要求"]').disabled || [...document.querySelectorAll('button')].some(b => b.textContent.includes('核实并重试上次操作'))) }
const note = value => page.getByRole('textbox', { name: '标注1修改意见', exact: true }).fill(value)
const choosePurpose = async value => { await page.locator('.reference-card .el-select').click(); await page.getByRole('option', { name: value, exact: true }).click() }
async function select(i) { await button('选择图片').click(); await page.locator(`.board-stage [data-picture="p${i}"] > rect`).click({ position: { x: 20, y: 20 } }) }
async function draw(i, tool = '框选问题') {
  await page.waitForFunction(n => document.querySelectorAll('.board-stage image')[n - 1]?.getAttribute('href')?.startsWith('blob:'), i); await button(tool).click()
  const b = await page.locator('.board-stage image').nth(i - 1).boundingBox()
  await page.mouse.move(b.x + b.width * .2, b.y + b.height * .2); await page.mouse.down(); await page.mouse.move(b.x + b.width * .7, b.y + b.height * .6, { steps: 10 }); await page.mouse.up()
}
async function uploadRef(kind = '自定义用途') {
  await page.getByLabel('上传参考图文件').setInputFiles({ name: 'reference.jpg', mimeType: 'image/jpeg', buffer: sample })
  await page.locator('.reference-top .el-image').waitFor(); await choosePurpose(kind)
  await page.getByRole('textbox', { name: '参考图1说明', exact: true }).fill('参考木色与材质，不照搬背景')
}
async function screenshot(name) { await page.screenshot({ path: `${out}/${name}.png`, animations: 'disabled' }) }
async function loadedBoard(width) {
  await page.waitForFunction(() => { const images = [...document.querySelectorAll('.board-stage image')]; return images.length === 6 && images.every(image => image.getAttribute('href')?.startsWith('blob:') && image.getBoundingClientRect().width > 0 && image.getBoundingClientRect().height > 0) })
  check(true, `${width}宽度六张真实图片加载且尺寸有效`)
}
try {
  await context.route('**/*', async route => {
    const request = route.request(), url = new URL(request.url()), path = url.pathname
    if (['api.iconify.design', 'api.unisvg.com', 'api.simplesvg.com'].includes(url.hostname)) return route.fulfill({ contentType: 'application/json', body: '{}' })
    if (url.origin !== base && !['data:', 'blob:'].includes(url.protocol)) { unexpected.push(url.href); return route.abort() }
    if (!path.startsWith('/api/')) return route.continue()
    let body = {}, status = 200
    if (path.endsWith('/config')) body = { configured: true, corpId: 'test', clientId: 'test' }
    else if (path === '/api/identity/v1/me') body = { name: '设计', sessionId: 'batch-test' }
    else if (path.endsWith('/tickets')) body = { ticket: 'test' }
    else if (path === '/api/v1/auth/identity/access') body = { state: 'unregistered' }
    else if (path.includes('/auth/')) { body = { id: 'd', name: '设计', identitySessionId: 'batch-test', status: 'active', roles: ['designer'], capabilities: caps }; if (path.endsWith('/access')) body = { state: 'allowed', member: body } }
    else if (path.includes('/studio/pictures/')) {
      if (readFailure && path.includes('/p6/')) return route.fulfill({ status: 503, body: '暂不可用' })
      return route.fulfill({ contentType: 'image/jpeg', body: sample })
    } else if (path.includes('/studio/files/') && path.endsWith('/content')) {
      const id = path.split('/').at(-2), file = uploads.get(`upload:${id}`)
      return route.fulfill({ contentType: file.asset.contentType, body: file.bytes })
    } else if (path.endsWith('/studio/files')) {
      if (failUpload) { failUpload = false; return route.fulfill({ status: 503, contentType: 'application/json', body: '{"detail":"测试上传故障"}' }) }
      const raw = request.postDataBuffer(), boundary = request.headers()['content-type'].split('boundary=')[1]
      const start = raw.indexOf('\r\n\r\n') + 4, end = raw.lastIndexOf(`\r\n--${boundary}`), headers = raw.subarray(0, start).toString()
      const name = headers.match(/filename="([^"]+)"/)[1], type = headers.match(/Content-Type: ([^\r]+)/i)[1], bytes = raw.subarray(start, end)
      const id = `${uploads.size + 1}`, asset = { id: `upload:${id}`, name, contentType: type, sizeBytes: bytes.length, source: 'upload', url: `/api/overseas/v1/tasks/t/studio/files/${id}/content` }
      uploads.set(asset.id, { asset, bytes }); materials.push(asset); body = asset
    } else if (path.endsWith('/studio/turns')) {
      const sent = request.postDataJSON(); sends.push({ body: sent, key: request.headers()['idempotency-key'] })
      if (failSend) { failSend = false; status = 503; body = { detail: '测试网络故障' } }
      else { turns[sent.conversationId].push(turn('sent', { text: sent.text, imageEdits: structuredClone(sent.imageEdits), attachments: sent.attachmentIds.map(id => structuredClone(uploads.get(id).asset)), referencePictures: sent.referencePictureIds.map(id => pictures.find(p => p.id === id)) })); body = state(sent.conversationId) }
    } else if (path.endsWith('/studio/transcript')) body = { items: [], cursor: 0, hasMore: false }
    else if (path.endsWith('/studio')) body = state(url.searchParams.get('conversationId') || 'a')
    else if (path.endsWith('/tasks/t')) body = task
    else if (path.endsWith('/materials')) body = []
    else if (path.endsWith('/jobs')) body = { items: [] }
    else if (path.endsWith('/execution-events')) body = { items: [], cursor: 0 }
    else if (path.endsWith('/plans') || path.endsWith('/pictures')) body = { items: [], taskVersion: 1 }
    else { unexpected.push(path); return route.abort() }
    return route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  })
  await page.goto(`${base}/#/overseas/tasks/t`); await ready(); await button('批量标注').click()
  check(await button('确认并带回工作台（0张）').isDisabled(), '空批量禁用确认')
  await draw(2); await button('确认并带回工作台（1张）').click(); await page.locator('.editor-error').waitFor()
  check((await page.locator('.editor-error').innerText()).includes('请填写每一处标注'), '标注缺少意见阻止提交'); await note('商品朝向与沙发平行')
  await uploadRef(); await button('确认并带回工作台（1张）').click()
  check((await page.locator('.editor-error').innerText()).includes('自定义'), '自定义用途为空阻止确认')
  const purpose = '品牌配色参考\n保持商品原有结构'
  await page.getByRole('textbox', { name: '参考图1自定义用途', exact: true }).fill(purpose)
  await choosePurpose('本产品实拍'); await choosePurpose('自定义用途')
  check(await page.getByRole('textbox', { name: '参考图1自定义用途', exact: true }).inputValue() === purpose, '切换用途保留自由文字')
  await draw(4, '画笔圈注'); await note('调整灯罩色调'); await uploadRef('成品效果参考')
  await select(1); await uploadRef('本产品实拍')
  check(await page.getByText('当前图片只有参考图，尚未标注，本次不会带回；草稿仍保留。').isVisible(), '未标注仅参考图明确排除')
  await select(2); await button('放大精细标注').click(); await page.locator('.annotation-canvas').waitFor(); check(true, '同区进入单图精细标注')
  await button('← 返回整组画布').click(); await button('关闭并保留草稿').click(); await button('批量标注').click()
  check(await button('确认并带回工作台（2张）').isEnabled(), '关闭重开草稿保留')
  await select(2); await screenshot('batch-desktop'); await button('确认并带回工作台（2张）').click()
  const review = page.getByRole('dialog', { name: '确认本次修改内容', exact: true })
  await review.waitFor()
  check(await review.locator('.revision-detail').count() === 2, '核对仅2和4张且用途正确')
  check((await review.innerText()).includes(purpose), '核对展示完整自由用途')
  failUpload = true; await button('确认并带回输入区').click(); await review.getByText('文件上传失败，请重试', { exact: true }).waitFor()
  check(await page.locator('.composer-files .revision-draft').count() === 0, '上传失败不带回半批'); await button('确认并带回输入区').click(); await review.waitFor({ state: 'hidden' })
  check(await page.locator('.composer-files .revision-draft').count() === 2 && sends.length === 0, '两张真实上传回填、不自动发送')
  check(uploads.size === 4, '仅上传两张标注和两张参考文件')
  await page.reload(); await ready(); check(await page.locator('.composer-files .revision-draft').count() === 2, '刷新恢复已确认修改材料')
  await page.locator('.composer-files .revision-draft').first().getByRole('button', { name: '继续标注', exact: true }).click()
  await page.locator('.reference-top .el-image').waitFor()
  check(await page.getByRole('textbox', { name: '参考图1自定义用途', exact: true }).inputValue() === purpose, '刷新后单张编辑恢复参考用途与文件')
  await screenshot('single-desktop'); await button('关闭并保留草稿').click()
  await page.locator('.session-switch').filter({ has: page.getByText('另一会话', { exact: true }) }).click(); await ready()
  check(await page.locator('.composer-files .revision-draft').count() === 0, '跨会话不串材料')
  await page.locator('.session-switch').filter({ has: page.getByText('主图方案', { exact: true }) }).click(); await ready()
  failSend = true; await page.getByRole('textbox', { name: '设计要求', exact: true }).fill('只修改指定两张'); await button('发送').click()
  await button('核实并重试上次操作').waitFor(); await page.reload(); await ready(); await button('核实并重试上次操作').click()
  await button('查看本轮修改材料（2张）').waitFor(); check(JSON.stringify(sends[0]) === JSON.stringify(sends[1]), '未知响应刷新后原请求幂等重试')
  const payload = sends.at(-1).body
  check(payload.referencePictureIds.join(',') === 'p2,p4' && payload.imageEdits.length === 2, '实际发送只含2和4张')
  check(payload.imageEdits[0].references[0].customPurpose === purpose && payload.imageEdits[1].references[0].kind === 'effect', '实际发送逐图用途无串用')
  check(uploads.get(payload.imageEdits[0].references[0].attachmentId).bytes.equals(sample), '上传参考文件原始字节保持')
  await button('查看本轮修改材料（2张）').click(); await screenshot('history')
  check((await page.getByRole('dialog', { name: '本轮修改材料', exact: true }).innerText()).includes(purpose), '历史按冻结绑定展示材料'); await button('关闭').click()
  await button('修改这张').nth(1).click(); check(await page.locator('.reference-card').count() === 0, '发送成功后清除旧草稿')
  await button('关闭并保留草稿').click(); await page.setViewportSize({ width: 1440, height: 900 }); await button('批量标注').click(); await loadedBoard(1440); await screenshot('batch-1440'); await button('关闭并保留草稿').click()
  await page.setViewportSize({ width: 390, height: 844 }); await button('修改这张').first().click(); await uploadRef(); await page.getByRole('textbox', { name: '参考图1自定义用途', exact: true }).fill('自由用途'); await page.getByRole('textbox', { name: '参考图1自定义用途', exact: true }).scrollIntoViewIfNeeded(); await screenshot('single-390')
  check(await button('确认标注').isVisible(), '窄屏参考用途与确认按钮可达'); await button('关闭并保留草稿').click()
  await button('批量标注').click(); await loadedBoard(390); await screenshot('batch-390'); await button('关闭并保留草稿').click()
  check(errors.length === 0, '无浏览器脚本异常'); check(unexpected.length === 0, '无真实业务或外网请求')
  await writeFile(`${out}/validation.json`, JSON.stringify({ checks, errors, unexpected, sends: sends.length, uploads: uploads.size }, null, 2))
} catch (error) { await screenshot('failure'); console.error('BROWSER_ERRORS', errors, unexpected); throw error }
finally { await browser.close() }
