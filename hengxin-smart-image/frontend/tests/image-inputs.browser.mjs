import assert from 'node:assert/strict'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const output = path.resolve('../../output/image-inputs-20260923')
await mkdir(output, { recursive: true })
const bytes = await readFile('public/demo-images/sample-1.jpg'), image64 = bytes.toString('base64')
const real = process.env.API_UI_URL || 'http://127.0.0.1:3014/'
const demo = process.env.DEMO_URL || 'http://127.0.0.1:3015/'
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 }, permissions: ['clipboard-read', 'clipboard-write'] })
const page = await context.newPage(), errors = [], checks = []
page.on('pageerror', e => errors.push(e.message)); page.setDefaultTimeout(15000)
const pic = id => ({ fileId: id, name: id + '.jpg', url: '/fixture/' + id + '.jpg' })
const task = { id: 'fixture-task', name: '原始输入核验', prompt: '保持结构', created: '2026-09-23T10:00:00Z', status: 'succeeded', operator: '隔离测试', batch: { current: 1, total: 1, running: 0 }, material: pic('material'), events: [], error: null, metrics: { requestCount: 1, retryCount: 0, elapsedSeconds: 3 }, items: [{ id: 'item-1', position: 1, source: pic('source'), state: 'succeeded', retries: 0, nextAttemptAt: null, result: pic('v2'), error: null, currentVersion: 2, versions: [1, 2].map(number => ({ number, picture: pic('v' + number), created: '2026-09-23T10:00:00Z', operator: '隔离测试', text: '', annotation: null, baseVersion: null })), revision: null }] }
let uploadCount = 0, failImages = false, paused = false
await context.route('**/fixture/**', route => failImages ? route.fulfill({ status: 404 }) : route.fulfill({ contentType: 'image/jpeg', body: bytes }))
// All real-mode API traffic stays in this browser context; no backend or production database is used.
await context.route('**/api/v1/**', async route => {
  const url = new URL(route.request().url()), method = route.request().method(), p = url.pathname
  let body
  if (p === '/api/v1/auth/me') body = { id: 'browser-user', name: '隔离测试', role: 'super_admin', status: 'active' }
  else if (p.endsWith('/status')) body = { enabled: true, paused, reason: paused ? '测试暂停' : null }
  else if (p.endsWith('/files') && method === 'POST') body = pic('upload-' + (++uploadCount))
  else if (p.includes('/files/') && method === 'DELETE') return route.fulfill({ status: 204 })
  else if (p.endsWith('/restore')) { task.items[0].currentVersion = 1; task.items[0].result = pic('v1'); body = { taskId: task.id } }
  else if (p.endsWith('/tasks/' + task.id)) body = task
  else if (p.endsWith('/tasks')) body = { items: [task], total: 1, page: 1, pageSize: 20 }
  else throw new Error('Unmocked API: ' + method + ' ' + p)
  await route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
})
async function drop(zone, count = 1, name = 'drop.jpg', type = 'image/jpeg') {
  await zone.evaluate((el, data) => { const transfer = new DataTransfer(); for (let i = 0; i < data.count; i++) transfer.items.add(new File([Uint8Array.from(atob(data.image64), c => c.charCodeAt(0))], data.name, { type: data.type })); for (const event of ['dragenter', 'drop']) el.dispatchEvent(new DragEvent(event, { dataTransfer: transfer, bubbles: true, cancelable: true })) }, { image64, count, name, type })
}
async function copyImage() {
  // Browser clipboard commonly exposes PNG even when the source is JPEG.
  await page.evaluate(async image64 => { const img = new Image(); img.src = 'data:image/jpeg;base64,' + image64; await img.decode(); const canvas = document.createElement('canvas'); canvas.width = 16; canvas.height = 16; canvas.getContext('2d').drawImage(img, 0, 0, 16, 16); const blob = await new Promise(resolve => canvas.toBlob(resolve)); await navigator.clipboard.write([new ClipboardItem({ 'image/png': blob })]) }, image64)
}
async function paste(zone) { await copyImage(); await zone.focus(); await page.keyboard.press('Control+V') }
async function capture(name) { await page.screenshot({ path: path.join(output, name + '.png'), animations: 'disabled' }) }
try {
  await page.goto(real + '#/api-image-edits/records?task=' + task.id)
  await page.getByText('本次共用素材', { exact: true }).waitFor()
  assert.equal(await page.locator('.material-reference img').getAttribute('src'), '/fixture/material.jpg')
  await page.getByRole('button', { name: '查看原图 / 对照成品' }).click()
  const comparison = page.locator('.comparison-grid')
  await comparison.waitFor(); assert.deepEqual(await comparison.locator('img').evaluateAll(imgs => imgs.map(i => i.getAttribute('src'))), ['/fixture/source.jpg', '/fixture/v2.jpg'])
  await capture('real-comparison'); await page.getByRole('button', { name: '关闭对照' }).click()
  // Simulate another client switching current version, then use the real refresh path.
  task.items[0].currentVersion = 1; task.items[0].result = pic('v1')
  await page.getByRole('button', { name: '刷新详情', exact: true }).click()
  await page.getByText('当前 V1 · 点击放大', { exact: true }).waitFor()
  await page.getByRole('button', { name: '查看原图 / 对照成品' }).click()
  await comparison.locator('img[src="/fixture/v1.jpg"]').waitFor()
  await page.getByRole('button', { name: '关闭对照' }).click()
  checks.push('真实API组件冻结原图/素材、当前版本刷新对照')
  await page.getByRole('button', { name: '修改这张', exact: true }).click()
  const revision = page.getByRole('dialog', { name: '修改这张结果', exact: true }), zone = revision.locator('.upload-interaction')
  await drop(zone, 1, 'bad.webp', 'image/webp'); await revision.getByText('请选择 JPG 或 PNG 图片', { exact: true }).waitFor()
  await drop(zone, 2); await revision.getByText(/最多.*1.*张/).last().waitFor(); assert.equal(uploadCount, 0)
  await paste(zone); await revision.getByRole('button', { name: '移除标注图' }).waitFor(); assert.equal(uploadCount, 1)
  await drop(zone); assert.equal(uploadCount, 1)
  await revision.getByRole('button', { name: '移除标注图' }).click()
  await revision.getByRole('button', { name: '移除标注图' }).waitFor({ state: 'hidden' })
  await drop(zone); await revision.getByRole('button', { name: '移除标注图' }).waitFor(); assert.equal(uploadCount, 2)
  await revision.getByRole('button', { name: '关闭', exact: true }).click()
  checks.push('真实标注拖拽/原生粘贴调用独立API；WebP拒绝、单图满额保留、移除重传')
  task.material = null; task.items[0].source = null
  await page.getByRole('button', { name: '刷新详情', exact: true }).click()
  await page.getByText('历史记录中没有可查看的共用素材', { exact: true }).waitFor()
  await page.getByRole('button', { name: '查看原图 / 对照成品' }).click()
  await page.getByText('历史记录中没有可查看的原始图片', { exact: true }).waitFor(); await comparison.locator('img').waitFor()
  await capture('missing-input'); await page.getByRole('button', { name: '关闭对照' }).click()
  task.material = pic('missing'); failImages = true
  await page.getByRole('button', { name: '刷新详情', exact: true }).click()
  await page.locator('.material-reference').getByText('图片加载失败', { exact: false }).waitFor()
  failImages = false; await page.locator('.material-reference').getByRole('button', { name: '重新加载' }).click()
  await page.waitForFunction(() => document.querySelector('.material-reference img')?.naturalWidth > 0)
  checks.push('历史输入为空仍可看成品；图片404及重新加载恢复')
  await page.goto(real + '#/api-image-edits/create')
  await page.getByText('上传全部完成后才可提交。切换页面会保留本次草稿与上传状态。', { exact: true }).waitFor()
  const seq = page.locator('.upload-interaction').first(); await seq.waitFor(); await page.waitForTimeout(500)
  await drop(seq, 2); await page.getByText('上传完成', { exact: true }).first().waitFor()
  await paste(seq); await page.waitForFunction(() => document.querySelectorAll('.sequence-card').length === 3)
  await page.waitForFunction(() => [...document.querySelectorAll('.sequence-card')].every(el => el.textContent.includes('上传完成')))
  const before = uploadCount; await page.locator('.sequence-card').first().dragTo(page.locator('.sequence-card').last())
  assert.equal(uploadCount, before); assert.equal(await page.locator('.sequence-card').count(), 3)
  await capture('real-uploads'); checks.push('真实API多图拖拽、粘贴追加及排序不重复上传')
  await page.goto(demo + '#/templates/index'); await page.getByRole('button', { name: '新建模板', exact: true }).click()
  const template = page.locator('.hx-template-dialog'), upload = template.locator('.upload-interaction')
  await upload.waitFor(); await page.waitForTimeout(700); await drop(upload); await template.locator('.picture-card').waitFor(); await paste(upload)
  await page.waitForFunction(() => document.querySelectorAll('.hx-template-dialog .picture-card').length === 2)
  await copyImage(); await upload.getByRole('button', { name: '粘贴图片', exact: true }).click()
  await page.waitForFunction(() => document.querySelectorAll('.hx-template-dialog .picture-card').length === 3)
  for (const [width, height] of [[1440, 900], [1280, 720]]) {
    await page.setViewportSize({ width, height }); await page.waitForTimeout(250)
    const box = await template.boundingBox(), footer = await template.locator('.el-dialog__footer').boundingBox()
    assert.ok(Math.abs(box.x + box.width / 2 - width / 2) < 3 && Math.abs(box.y + box.height / 2 - height / 2) < 3)
    assert.ok(footer.y + footer.height <= height - 15); await capture('template-' + width)
  }
  await template.getByRole('button', { name: '取消', exact: true }).click()
  await page.getByRole('button', { name: '配置模板', exact: true }).first().click(); await template.waitFor()
  await template.locator('.picture-card').first().waitFor(); assert.ok(await template.locator('.picture-card').count() > 0); await template.getByRole('button', { name: '取消', exact: true }).click()
  checks.push('模板新建三种上传、配置加载、两尺寸居中固定底部')
  await page.setViewportSize({ width: 1440, height: 900 })
  for (const mode of ['wallpaper', 'product', 'text']) {
    await page.goto(demo + '#/image-processing/' + mode)
    const z = page.locator('.upload-interaction').first(); await z.waitFor(); await page.waitForTimeout(700)
    await drop(z); await page.waitForFunction(() => document.querySelectorAll('.compact-picture').length === 1)
    await paste(z); await page.waitForFunction(() => document.querySelectorAll('.compact-picture').length === 2)
  }
  await page.getByRole('textbox', { name: '任务名称', exact: true }).fill('上传隔离验收')
  await page.locator('textarea').fill('保留背景')
  await page.getByRole('button', { name: '提交生成任务', exact: true }).click()
  await page.getByRole('button', { name: '修改这张', exact: true }).first().click()
  const cli = page.locator('.revision-editor'), cliUpload = cli.locator('.upload-interaction')
  await drop(cliUpload); await cli.getByText('模拟已接收', { exact: true }).waitFor()
  await cli.getByRole('button', { name: '移除图片 1', exact: true }).click()
  await paste(cliUpload); await cli.getByText('模拟已接收', { exact: true }).waitFor()
  await page.evaluate(() => navigator.clipboard.writeText('文字粘贴核验'))
  await page.getByLabel('修改意见', { exact: true }).focus(); await page.keyboard.press('Control+V')
  assert.equal(await page.getByLabel('修改意见', { exact: true }).inputValue(), '文字粘贴核验')
  assert.equal(await cli.locator('.picture-card').count(), 1)
  checks.push('三类CLI创建拖拽/粘贴；CLI截图拖拽/移除/粘贴；文本粘贴不上传')
  assert.deepEqual(errors, [])
  await writeFile(path.join(output, 'checks.json'), JSON.stringify({ passed: true, checks, errors }, null, 2)); console.log(JSON.stringify({ passed: true, checks }, null, 2))
} catch (error) { await capture('failure'); console.error((await page.locator('body').innerText()).slice(-2500)); throw error }
finally { await context.close(); await browser.close() }
