import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.API_UI_URL || 'http://127.0.0.1:3019/'
const output = path.resolve('output/playwright/api-text')
await mkdir(output, { recursive: true })
const expectedPrompt = (await readFile('hengxin-smart-image/frontend/src/views/hengxin/api-image-edits/default-wallpaper-prompt.txt', 'utf8')).replace(/\r\n/g, '\n')
const pic = id => ({ fileId: id, name: id + '.png', url: '/fixture/' + id + '.svg', width: 790, height: 1500 })
const original = pic('original'), current = pic('current')
const item = { id: 'item-1', position: 1, source: original, state: 'succeeded', retries: 0, nextAttemptAt: null,
  result: current, error: null, currentVersion: 1, versions: [{ number: 1, picture: current, created: '2026-09-30T08:00:00Z',
    operator: '隔离测试', text: '', annotation: null, baseVersion: null, kind: 'generation' }], revision: null }
const task = { id: 'text-fixture', name: '文案功能隔离验收', prompt: '任务原提示词', created: '2026-09-30T08:00:00Z',
  status: 'succeeded', operator: '隔离测试', batch: { current: 1, total: 1, running: 0 }, material: pic('material'),
  events: [], error: null, metrics: { requestCount: 1, retryCount: 0, elapsedSeconds: 5 }, items: [item] }
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await context.newPage(), errors = [], checks = [], requests = []
let rejectNext = false, uploads = 0
const image = Buffer.from(await page.evaluate(() => {
  const c = document.createElement('canvas'); c.width = 790; c.height = 1500
  const ctx = c.getContext('2d'); ctx.fillStyle = '#e2ecff'; ctx.fillRect(0, 0, 790, 1500)
  ctx.fillStyle = '#222'; ctx.font = '55px sans-serif'; ctx.fillText('原有文案', 160, 180)
  return c.toDataURL('image/png').split(',')[1]
}), 'base64')
page.setDefaultTimeout(20000)
page.on('pageerror', e => errors.push(e.message))
await context.route('**/*', async route => {
  const req = route.request(), u = new URL(req.url())
  if (u.origin !== new URL(base).origin) return route.abort()
  if (u.pathname.startsWith('/fixture/')) return route.fulfill({ contentType: 'image/svg+xml', body: '<svg xmlns="http://www.w3.org/2000/svg" width="790" height="1500"><rect width="100%" height="100%" fill="#e2ecff"/><text x="160" y="180" font-size="55">原有文案</text><rect x="100" y="330" width="580" height="990" rx="45" fill="#9eb8e7"/></svg>' })
  if (!u.pathname.startsWith('/api/')) return route.continue()
  const fulfill = body => route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
  if (u.pathname === '/api/v1/auth/me') return fulfill({ id: 'browser-user', name: '隔离测试', role: 'super_admin', status: 'active' })
  if (u.pathname.endsWith('/status')) return fulfill({ enabled: true, paused: false, reason: null })
  if (u.pathname.endsWith('/content')) return route.fulfill({ contentType: 'image/png', body: image })
  if (u.pathname.endsWith('/files') && req.method() === 'POST') { uploads++; return fulfill(pic('annotation')) }
  if (u.pathname.endsWith('/files/annotation') && req.method() === 'DELETE') return fulfill({ deleted: true })
  if (u.pathname.endsWith('/revise')) {
    const body = req.postDataJSON(); requests.push({ body, key: req.headers()['idempotency-key'] })
    if (rejectNext) { rejectNext = false; return route.fulfill({ status: 500, contentType: 'application/json', body: '{"detail":"isolated uncertain test"}' }) }
    item.state = 'queued'; task.status = 'running'
    item.revision = { state: 'queued', text: body.text || '', kind: body.kind, operator: '隔离测试', baseVersion: body.baseVersion, retries: 0, error: null, annotation: body.annotationFileId ? pic('annotation') : null }
    return fulfill({ taskId: task.id })
  }
  if (u.pathname.endsWith('/items/item-1/retry')) { item.state = 'queued'; item.error = null; item.revision.state = 'queued'; task.status = 'running'; return fulfill({ taskId: task.id }) }
  if (u.pathname.endsWith('/tasks/' + task.id)) return fulfill(task)
  if (u.pathname.endsWith('/tasks')) return fulfill({ items: [{ id: task.id, name: task.name, created: task.created, status: task.status,
    operator: task.operator, cover: item.result, counts: { total: 1, success: item.state === 'succeeded' ? 1 : 0, failed: item.state === 'failed' ? 1 : 0, uncertain: 0 }, batch: task.batch }], total: 1, page: 1, pageSize: 20 })
  errors.push(req.method() + ' unexpected API: ' + u.pathname)
  return route.fulfill({ status: 501, body: '{}' })
})
async function screenshot(name) { await page.screenshot({ path: path.join(output, name + '.png'), animations: 'disabled' }) }
async function refresh() { await page.getByRole('button', { name: '刷新详情', exact: true }).click() }
function complete(kind) {
  item.state = task.status = 'succeeded'; item.error = null
  item.currentVersion++; item.result = pic('v' + item.currentVersion)
  item.versions.push({ number: item.currentVersion, picture: item.result, created: task.created, operator: '隔离测试',
    text: item.revision.text, annotation: item.revision.annotation, baseVersion: item.revision.baseVersion, kind })
  item.revision.state = 'succeeded'; item.revision.error = null
}
try {
  await page.goto(base + '#/api-image-edits/create')
  const prompt = page.getByRole('textbox', { name: '提示词', exact: true })
  await prompt.waitFor(); assert.equal(await prompt.inputValue(), expectedPrompt)
  await screenshot('create-default')
  await prompt.fill('用户自己的草稿'); await page.getByRole('button', { name: /换图记录/ }).first().click()
  await page.goto(base + '#/api-image-edits/create'); assert.equal(await prompt.inputValue(), '用户自己的草稿')
  await prompt.fill(''); await page.goto(base + '#/api-image-edits/records'); await page.goto(base + '#/api-image-edits/create')
  assert.equal(await prompt.inputValue(), '')
  checks.push('完整默认原文预填；路由切换保留用户草稿和显式清空')
  await page.goto(base + '#/api-image-edits/records?task=' + task.id)
  const repair = page.getByRole('button', { name: '修复文案', exact: true }), edit = page.getByRole('button', { name: '修改这张', exact: true })
  await repair.waitFor(); await screenshot('detail-before')
  rejectNext = true; await repair.click()
  await page.getByRole('button', { name: '确认原修复请求', exact: true }).waitFor()
  assert.equal(await edit.isDisabled(), true); const first = requests.at(-1)
  await screenshot('repair-uncertain')
  await page.getByRole('button', { name: '确认原修复请求', exact: true }).click()
  await page.getByText(/修复文案：等待处理/).waitFor()
  assert.deepEqual(requests.at(-1), first)
  assert.equal(first.body.kind, 'text_repair'); assert.equal(first.body.text, ''); assert.equal(first.body.annotationFileId, undefined)
  assert.equal(await repair.isDisabled(), true); assert.equal(await edit.isDisabled(), true)
  await screenshot('repair-queued')
  checks.push('一键修复空意见提交；未知结果同key同载荷确认；处理中阻止修改与重复修复')
  item.state = 'failed'; task.status = 'failed'; item.error = '隔离测试错误'; item.revision.state = 'failed'; item.revision.error = item.error
  await refresh(); await page.getByRole('button', { name: '继续重试这张', exact: true }).waitFor()
  assert.equal(await page.getByText('当前 V1 · 点击放大', { exact: true }).count(), 1)
  await screenshot('repair-failed'); await page.getByRole('button', { name: '继续重试这张', exact: true }).click()
  await page.getByText(/修复文案：等待处理/).waitFor(); complete('text_repair'); await refresh()
  await page.getByText('当前 V2 · 点击放大', { exact: true }).waitFor()
  await screenshot('repair-complete'); checks.push('失败保留旧V1、继续重试，成功新V2')
  await edit.click()
  const dialog = page.getByRole('dialog', { name: '修改第 1 张图片 · 基于 V2', exact: true })
  await dialog.getByText('标注可选，填写修改意见即可提交', { exact: true }).waitFor()
  await dialog.getByRole('textbox', { name: '整体补充要求', exact: true }).fill('将原有文案替换成新的文案')
  await dialog.getByRole('button', { name: '预览提交内容', exact: true }).click()
  const confirm = page.getByRole('dialog', { name: '确认本次修改内容', exact: true })
  await confirm.waitFor(); await screenshot('text-only-preview')
  await confirm.getByRole('button', { name: '确认提交修改', exact: true }).click()
  await page.getByText(/文字修改：等待处理/).waitFor()
  const textOnly = requests.at(-1).body
  assert.equal(textOnly.kind, 'text_edit'); assert.equal(textOnly.annotationFileId, undefined)
  assert.ok(textOnly.prompt.includes('将原有文案替换成新的文案')); assert.ok(textOnly.prompt.includes('【文字长度】')); assert.equal(uploads, 0)
  complete('text_edit'); await refresh(); await page.getByText('当前 V3 · 点击放大', { exact: true }).waitFor()
  checks.push('无标注纯文字提交；完整固定规则拼接，无额外图片上传')
  await edit.click()
  const annotated = page.getByRole('dialog', { name: '修改第 1 张图片 · 基于 V3', exact: true })
  await annotated.locator('.el-loading-mask').waitFor({ state: 'hidden' })
  await annotated.evaluate(async el => {
    const finite = el.getAnimations({ subtree: true }).filter(a => a.effect?.getTiming().iterations !== Infinity)
    await Promise.all(finite.map(a => a.finished.catch(() => {})))
  })
  const canvas = annotated.locator('svg[aria-label="当前成品与问题标注"]'); await canvas.waitFor()
  const bounds = await canvas.locator('image').boundingBox()
  await page.mouse.move(bounds.x + bounds.width * .25, bounds.y + bounds.height * .25); await page.mouse.down()
  await page.mouse.move(bounds.x + bounds.width * .65, bounds.y + bounds.height * .5, { steps: 8 }); await page.mouse.up()
  await annotated.getByRole('textbox', { name: '标注 1 修改意见', exact: true }).fill('圈中标题改为全面保护')
  await screenshot('annotation-edit')
  await annotated.getByRole('button', { name: '预览提交内容', exact: true }).click()
  await confirm.getByRole('button', { name: '确认提交修改', exact: true }).click()
  await page.getByText(/文字修改：等待处理/).waitFor()
  assert.equal(requests.at(-1).body.annotationFileId, 'annotation'); assert.equal(uploads, 1)
  complete('text_edit'); await refresh(); checks.push('圈注意见关联、导出上传标注并提交')
  await page.getByRole('button', { name: '历史版本 · 4', exact: true }).click()
  await page.getByRole('dialog', { name: '历史版本 · 原图 1', exact: true }).waitFor()
  await screenshot('history-kinds'); await page.getByRole('dialog', { name: '历史版本 · 原图 1', exact: true }).getByRole('button', { name: '关闭', exact: true }).click()
  await page.setViewportSize({ width: 1920, height: 1080 }); await screenshot('detail-wide')
  await page.setViewportSize({ width: 390, height: 844 }); await screenshot('detail-narrow')
  const actions = page.locator('.card-actions').first()
  for (const button of await actions.getByRole('button').all()) {
    await button.scrollIntoViewIfNeeded()
    assert.equal(await button.evaluate(el => { const r = el.getBoundingClientRect(), p = el.closest('.el-card').getBoundingClientRect(); return r.left >= p.left && r.right <= p.right && r.width > 0 }), true)
  }
  await edit.click(); const narrow = page.getByRole('dialog', { name: '修改第 1 张图片 · 基于 V4', exact: true })
  await narrow.waitFor(); await narrow.locator('.el-loading-mask').waitFor({ state: 'hidden' })
  await narrow.getByRole('textbox', { name: '整体补充要求', exact: true }).scrollIntoViewIfNeeded()
  await screenshot('edit-narrow'); assert.equal(await narrow.evaluate(el => el.scrollWidth > el.clientWidth + 1), false)
  checks.push('历史版本类型可读；390px卡片按钮与画布弹窗无横向裁切')
  assert.deepEqual(errors, [])
  await writeFile(path.join(output, 'result.json'), JSON.stringify({ checks, errors, requestKinds: requests.map(r => r.body.kind), uploads }, null, 2))
  console.log(JSON.stringify({ checks, errors }, null, 2))
} catch (error) { await screenshot('failure'); throw error }
finally { await context.close(); await browser.close() }
