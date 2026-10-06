import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.API_UI_URL || 'http://127.0.0.1:3024/'
const output = path.resolve('../../output/playwright/api-image-conversation')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await context.newPage(), errors = [], requests = [], checks = [], downloads = []
page.setDefaultTimeout(15000); page.on('pageerror', error => errors.push(error.message))
const png = Buffer.from(await page.evaluate(() => { const c = document.createElement('canvas'); c.width = 790; c.height = 1500; const x = c.getContext('2d'); x.fillStyle = '#dde4ea'; x.fillRect(0, 0, 790, 1500); return c.toDataURL().split(',')[1] }), 'base64')
const pic = n => ({ fileId: `image-${n}`, name: `${n}.png`, url: `/fixture/${n}.png`, width: 790, height: 1500 })
const item = { id: 'item', position: 1, source: pic(1), state: 'succeeded', retries: 0, nextAttemptAt: null, result: pic(2), error: null, currentVersion: 1, versions: [{ number: 1, picture: pic(2), created: '2026-10-06T00:00:00Z', operator: '测试', text: '', annotation: null, baseVersion: null }], revision: null }
const task = { id: 'fixture-api', name: '多轮隔离验收', prompt: '', created: '2026-10-06T00:00:00Z', status: 'succeeded', operator: '测试', batch: { current: 1, total: 1, running: 0 }, material: pic(3), items: [item], events: [], error: null, metrics: { requestCount: 1, retryCount: 0, elapsedSeconds: 1 } }
const conversation = { id: null, itemId: 'item', currentVersion: 1, lastEventId: 0, turns: [] }
const events = [], keys = new Map(); let loseResponse = true, completeNext = 'waiting_user', adopted = 0
function event(turn, type, text) { events.push({ id: ++conversation.lastEventId, turnId: turn.id, type, ...(text ? { text } : { status: turn.status }) }) }
await context.route('**/*', async route => {
  const req = route.request(), u = new URL(req.url()), p = u.pathname
  if (u.origin !== new URL(base).origin) return route.abort()
  if (p.startsWith('/fixture/')) return route.fulfill({ contentType: 'image/png', body: png })
  if (!p.startsWith('/api/')) return route.continue()
  let body
  if (p.endsWith('/auth/me')) body = { id: 'browser-user', name: '测试', role: 'super_admin', status: 'active' }
  else if (p.endsWith('/content')) { downloads.push(p); return route.fulfill({ contentType: 'image/png', body: png }) }
  else if (p.endsWith('/files') && req.method() === 'POST') {
    const raw = req.postDataBuffer(), at = raw.indexOf(Buffer.from([137,80,78,71,13,10,26,10]))
    assert.ok(at >= 0); assert.deepEqual([raw.readUInt32BE(at + 16), raw.readUInt32BE(at + 20)], [790,1500]); body = pic(90)
  } else if (p.endsWith('/events')) {
    const running = conversation.turns.find(t => t.status === 'running')
    if (running && completeNext) {
      running.messages.push('请确认这处修改要求'); event(running, 'message', '请确认这处修改要求')
      running.status = completeNext
      if (completeNext === 'candidate') { running.candidate = pic(10 + conversation.turns.length); running.candidateFileId = running.candidate.fileId }
      event(running, 'state'); completeNext = ''
    }
    const after = Number(u.searchParams.get('after') || 0)
    return route.fulfill({ contentType: 'text/event-stream', body: ': heartbeat\n\n' + events.filter(e => e.id > after).map(e => `id: ${e.id}\nevent: message\ndata: ${JSON.stringify(e)}\n\n`).join('') })
  } else if (p.endsWith('/conversation')) body = conversation
  else if (p.endsWith('/turns')) {
    const input = req.postDataJSON(), key = req.headers()['idempotency-key']; requests.push({ key, input })
    if (!keys.has(key)) {
      const basePicture = input.baseTurnId ? conversation.turns.find(t => t.id === input.baseTurnId).candidate : item.versions.find(v => v.number === (input.baseVersion ?? item.currentVersion)).picture
      const t = { id: `turn-${conversation.turns.length + 1}`, status: 'running', ...input, baseVersion: input.baseVersion ?? null, baseTurnId: input.baseTurnId ?? null, baseFileId: basePicture.fileId, basePicture, annotationFileId: input.annotationFileId ?? null, annotation: input.annotationFileId ? pic(90) : null, candidateFileId: null, candidate: null, messages: [], error: null, createdAt: '2026-10-06T00:00:00Z', adoptedVersion: null }
      conversation.id = 'conversation'; conversation.turns.push(t); keys.set(key, t); event(t, 'state')
    }
    if (loseResponse) { loseResponse = false; return route.abort('failed') }
    body = conversation
  } else if (p.endsWith('/stop')) {
    const turn = conversation.turns.at(-1); turn.status = 'cancelled'; event(turn, 'state'); body = conversation
  } else if (p.endsWith('/adopt')) {
    assert.equal(req.postDataJSON().expectedVersion, item.currentVersion)
    const turn = conversation.turns.find(t => p.includes(`/${t.id}/`)); turn.status = 'adopted'; turn.adoptedVersion = ++item.currentVersion; item.result = turn.candidate; item.versions.push({ number: item.currentVersion, kind: 'image_edit', picture: item.result, created: turn.createdAt, operator: '测试', text: turn.text, annotation: turn.annotation, baseVersion: 1 }); conversation.currentVersion = item.currentVersion; adopted++; event(turn, 'state'); body = conversation
  } else if (p.endsWith('/revise')) { requests.push({ input: req.postDataJSON() }); body = { taskId: task.id } }
  else if (p.endsWith('/status')) body = { enabled: true, paused: false, reason: null }
  else if (p.endsWith('/tasks/fixture-api')) body = task
  else if (p.endsWith('/tasks')) body = { items: [{ ...task, cover: item.source, counts: { total: 1, success: 1, failed: 0, uncertain: 0 } }], total: 1, page: 1, pageSize: 20 }
  else { errors.push(`${req.method()} ${p}`); return route.fulfill({ status: 501 }) }
  return route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
})
const dialog = page.getByRole('dialog', { name: /修改第 1 张图片/ })
const field = () => dialog.getByRole('textbox', { name: '整体补充要求' })
const confirm = page.getByRole('dialog', { name: '确认本次修改内容', exact: true })
async function submit(text) {
  await field().fill(text); await dialog.getByRole('button', { name: '预览提交内容', exact: true }).click()
  await confirm.waitFor(); await confirm.getByRole('button', { name: '确认提交修改', exact: true }).click(); await confirm.waitFor({ state: 'hidden' })
}
try {
  await page.goto(base + '#/api-image-edits/records?task=fixture-api')
  await page.getByRole('button', { name: '修改图片', exact: true }).click()
  await dialog.locator('svg[role="img"]').waitFor()
  await dialog.locator('.picture-area .el-loading-mask').waitFor({ state: 'hidden' }); await page.waitForTimeout(400)
  assert.equal(await dialog.locator('.input-card img').count(), 3)
  const svg = dialog.locator('svg[role="img"]'), b = await svg.boundingBox()
  await page.mouse.move(b.x + b.width * .48, b.y + b.height * .4); await page.mouse.down(); await page.mouse.move(b.x + b.width * .52, b.y + b.height * .6, { steps: 8 }); await page.mouse.up()
  await dialog.getByRole('textbox', { name: '标注 1 修改意见', exact: true }).fill('缩小这个物体')
  await submit('其余保持不变')
  await dialog.getByRole('button', { name: '确认原修改请求', exact: true }).click()
  await dialog.getByText('等待补充意见', { exact: true }).waitFor()
  assert.equal(requests.length, 2); assert.deepEqual(requests[0], requests[1]); assert.match(requests[0].input.text, /标注 1/)
  assert.equal(await field().inputValue(), '')
  checks.push('原尺寸标注、三图/可选标注、未知请求原键重放、纯文字等待回复')
  completeNext = 'candidate'; await submit('确认，保持文字不变')
  await dialog.getByRole('button', { name: '采用此图', exact: true }).waitFor()
  assert.equal(adopted, 0); assert.equal(item.currentVersion, 1); assert.equal(await field().inputValue(), '')
  await field().fill('候选草稿保留')
  await dialog.getByRole('button', { name: '关闭', exact: true }).click(); await dialog.waitFor({ state: 'hidden' })
  await page.getByRole('button', { name: '修改图片', exact: true }).click(); await dialog.locator('svg[role="img"]').waitFor()
  assert.equal(await field().inputValue(), '候选草稿保留')
  await dialog.getByRole('button', { name: '采用此图', exact: true }).click()
  await page.waitForFunction(() => document.body.innerText.includes('已采用'))
  assert.equal(adopted, 1); assert.equal(await dialog.isVisible(), true)
  checks.push('候选默认下轮底图、关闭重开草稿恢复、显式采用且弹窗保持')
  await submit('继续调整'); await dialog.getByRole('button', { name: '停止本轮', exact: true }).waitFor()
  assert.equal(requests.at(-1).input.baseTurnId, 'turn-2')
  await dialog.getByRole('button', { name: '停止本轮', exact: true }).click()
  await dialog.getByText('已停止', { exact: true }).waitFor(); assert.equal(await field().inputValue(), '继续调整'); assert.equal(item.currentVersion, 2)
  checks.push('续接候选底图、停止保留旧图及意见')
  await dialog.locator('.conversation-history > summary').click()
  await dialog.getByRole('button', { name: '基于 V1 继续', exact: true }).click()
  await dialog.locator('.conversation-history > summary').click()
  completeNext = 'waiting_user'; await submit('基于旧版确认位置')
  await dialog.getByText('等待补充意见', { exact: true }).waitFor()
  assert.equal(requests.at(-1).input.baseVersion, 1)
  await dialog.getByRole('button', { name: '关闭', exact: true }).click(); await dialog.waitFor({ state: 'hidden' })
  await page.getByRole('button', { name: '修改图片', exact: true }).click(); await dialog.locator('svg[role="img"]').waitFor()
  assert.match(await dialog.getAttribute('aria-label'), /基于 V1/)
  await dialog.locator('.picture-area .el-loading-mask').waitFor({ state: 'hidden' })
  assert.equal(conversation.turns.at(-1).baseFileId, 'image-2')
  assert.match(downloads.at(-1), /\/files\/image-2\/content$/)
  assert.match(await dialog.locator('.input-card img').first().getAttribute('src'), /\/fixture\/2\.png$/)
  await dialog.locator('.latest-reply').getByText('请确认这处修改要求', { exact: true }).waitFor()
  checks.push('选择历史V1后纯文字等待、重新打开保留实际旧底图并直接显示问题')
  await page.screenshot({ path: path.join(output, 'conversation.png'), animations: 'disabled' })
  await dialog.getByText('文字修改', { exact: true }).click(); await dialog.locator('svg[role="img"]').waitFor()
  await submit('只替换标题文字'); await dialog.waitFor({ state: 'hidden' })
  assert.equal(requests.at(-1).input.kind, 'text_edit'); assert.equal(requests.at(-1).input.baseVersion, 2)
  checks.push('文字模式沿用API返工，采用候选后文字底图更新为当前版本')
  assert.deepEqual(errors, []); await writeFile(path.join(output, 'result.json'), JSON.stringify({ checks, requests, errors }, null, 2)); console.log(JSON.stringify({ checks, errors }))
} catch (error) { await page.screenshot({ path: path.join(output, 'failure.png'), animations: 'disabled' }); throw error }
finally { await context.close(); await browser.close() }
