import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import path from 'node:path'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.API_UI_URL || 'http://127.0.0.1:3024/'
const output = path.resolve('../../output/round-materials-20260924')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await context.newPage(), errors = [], materialRequests = [], checks = []
page.setDefaultTimeout(15000)
page.on('pageerror', error => errors.push(error.message))
const uuid = n => `00000000-0000-4000-8000-${String(n).padStart(12, '0')}`
const image = Buffer.from(await page.evaluate(() => {
  const canvas = document.createElement('canvas'); canvas.width = canvas.height = 800
  const ctx = canvas.getContext('2d'); ctx.fillStyle = '#d8e5ef'; ctx.fillRect(0, 0, 800, 800)
  ctx.fillStyle = '#206a73'; ctx.fillRect(250, 130, 300, 540)
  return canvas.toDataURL().split(',')[1]
}), 'base64')
const picture = n => ({ name: `第4张-V${n}.png`, fileId: uuid(n), url: `/api/v1/files/${uuid(n)}/content` })
const time = '2026-09-24T08:29:07Z'
const rounds = [1, 2].map(n => ({ id: `round-${n}`, taskId: 'fixture-cli', operatorId: 'browser-user', target: 0,
  note: n === 1 ? '历史修改意见' : '手机壁纸重新更改 <script>不执行</script>', state: '待查看',
  baseVersion: n, baseVersionId: `version-${n}`, createdAt: time, startedAt: time, finishedAt: time, error: null }))
const task = { id: 'fixture-cli', name: '轮次材料隔离验收', mode: 'wallpaper', template: '', skillVersionId: 'skill-1',
  ownerId: 'browser-user', sessionId: 'session-1', state: '待查看', progress: 100, images: [picture(3)], sources: [picture(8)],
  feedback: [], time, archived: false, currentRoundId: 'round-2', executionSource: 'cli' }
const detail = { task, rounds, slots: [{ slot: 0, currentVersionId: 'version-3', error: null,
  versions: [1, 2, 3].map(n => ({ ...picture(n), id: `version-${n}`, version: n, roundId: n === 3 ? 'round-2' : 'round-1', createdAt: time })) }],
  executionControl: { canRevise: true, canRetry: false, blockedReason: null } }
const fullPrompt = '完整系统任务提示词\n'.repeat(220) + '任务原文结尾'
let fail = true, publish = false, delayed, releaseDelayed
function materials(roundId) {
  return { taskId: task.id, roundId, note: rounds[roundId === 'round-1' ? 0 : 1].note, status: 'succeeded',
    systemPrompts: roundId === 'round-1' ? [] : [{ label: '首次执行', text: fullPrompt }],
    toolCalls: roundId === 'round-1' ? [] : [1, 2].map(n => ({ label: `生图调用 ${n}`, prompt: `实际生图工具原文 ${n}\n<script>只作为文本显示</script>`, images: ['/work/current/00.png', '/work/original/00.jpg'] })),
    inputs: [{ role: 'current', label: '基础成品', version: roundId === 'round-1' ? 1 : 2, picture: picture(roundId === 'round-1' ? 1 : 2) },
      { role: 'original', label: '原始底图', picture: picture(8) }, { role: 'material', label: '屏幕素材', picture: picture(9) },
      { role: 'annotation', label: '标注图', picture: null, reason: '本轮未提交标注图' }],
    outputs: publish ? [{ role: 'output', label: '本轮结果', version: 3, picture: picture(3) }] : [],
    notices: roundId === 'round-1' ? ['历史执行原文未保存，不能恢复完整提示词。'] : [] }
}
await context.route('**/*', async route => {
  const u = new URL(route.request().url()), p = u.pathname
  if (u.origin !== new URL(base).origin) return route.abort()
  if (!p.startsWith('/api/')) return route.continue()
  if (p.endsWith('/content')) return route.fulfill({ contentType: 'image/png', body: image })
  let body
  if (p === '/api/v1/auth/me') body = { id: 'browser-user', name: '隔离测试', role: 'super_admin', status: 'active' }
  else if (p.endsWith('/materials')) {
    const roundId = p.split('/').at(-2); materialRequests.push(roundId)
    if (delayed === roundId) { await new Promise(resolve => { releaseDelayed = resolve }); delayed = null }
    if (fail) { fail = false; return route.fulfill({ status: 503, contentType: 'application/json', body: '{}' }) }
    body = materials(roundId)
  } else if (p === '/api/v1/tasks/fixture-cli') body = detail
  else if (p === '/api/v1/tasks') body = { items: [task], total: 1, page: 1, pageSize: 20, stats: { total: 1, processing: 0, ready: 1, archived: 0 } }
  else if (p.endsWith('/execution')) body = { taskId: task.id, roundId: 'round-2', status: 'succeeded', source: 'cli', diagnosticId: null,
    stage: 'completed', label: '已完成', startedAt: time, finishedAt: time, updatedAt: time, lastActivityAt: time,
    totalImages: 1, detectedImages: 1, legacy: false, events: [], failure: null }
  else { errors.push('Unexpected API: ' + p); return route.fulfill({ status: 501, body: '{}' }) }
  return route.fulfill({ contentType: 'application/json', body: JSON.stringify(body) })
})
const region = () => page.getByRole('region', { name: '本轮执行材料' })
try {
  await page.goto(base + '#/tasks/index'); await page.getByText(task.name, { exact: true }).click()
  await page.getByText('执行与修改记录（2）', { exact: true }).click()
  assert.equal(materialRequests.length, 0)
  await page.getByText('第 2 轮 · 第 1 张 · 待查看', { exact: true }).click()
  await page.getByRole('button', { name: '重试读取材料', exact: true }).click()
  await region().getByText('本轮未提交标注图', { exact: true }).waitFor()
  assert.equal(materialRequests.length, 2)
  assert.equal(await region().locator('img').first().getAttribute('src'), picture(2).url)
  await region().getByText('完整任务提示词 · 系统交给 CLI', { exact: true }).click()
  assert.equal(await region().getByLabel('完整任务提示词 1', { exact: true }).textContent(), fullPrompt)
  await region().getByText('实际生图提示词 · 2 次已记录调用', { exact: true }).click()
  await region().getByLabel('实际生图提示词 2', { exact: true }).waitFor()
  assert.equal(await region().locator('script').count(), 0)
  assert.match(await region().getByLabel('实际生图提示词 2', { exact: true }).textContent(), /<script>只作为文本显示<\/script>/)
  await region().getByRole('button', { name: '放大查看 第4张-V2.png', exact: true }).click()
  await page.locator('.el-image-viewer__wrapper').waitFor(); await page.keyboard.press('Escape')
  checks.push('按需加载、503可重试、历史基础V2不取当前V3、完整长文本、多次调用与纯文本防注入、原图预览')
  publish = true; await region().getByRole('button', { name: '刷新材料', exact: true }).click()
  await region().getByText('本轮结果 · V3', { exact: true }).waitFor()
  await page.getByText('第 1 轮 · 第 1 张 · 待查看', { exact: true }).click()
  await region().getByText('历史执行原文未保存，不能恢复完整提示词。', { exact: true }).waitFor()
  assert.equal(await region().locator('img').first().getAttribute('src'), picture(1).url)
  await page.screenshot({ path: path.join(output, 'historical.png'), fullPage: true })
  delayed = 'round-1'; await region().getByRole('button', { name: '刷新材料', exact: true }).click()
  await page.waitForFunction(() => document.body.textContent.includes('正在读取本轮执行材料'))
  await page.getByText('第 2 轮 · 第 1 张 · 待查看', { exact: true }).click()
  await region().getByText('本轮结果 · V3', { exact: true }).waitFor()
  releaseDelayed(); await page.waitForTimeout(150)
  assert.equal(await region().getByText('历史执行原文未保存，不能恢复完整提示词。', { exact: true }).count(), 0)
  await region().getByText('完整任务提示词 · 系统交给 CLI', { exact: true }).click()
  await region().getByText('实际生图提示词 · 2 次已记录调用', { exact: true }).click()
  await region().scrollIntoViewIfNeeded(); await page.screenshot({ path: path.join(output, 'materials.png') })
  await page.setViewportSize({ width: 760, height: 900 }); await page.waitForTimeout(200)
  assert.ok(await region().evaluate(el => el.scrollWidth <= el.clientWidth + 1))
  await page.screenshot({ path: path.join(output, 'narrow.png') })
  const count = materialRequests.length
  await page.getByText('执行与修改记录（2）', { exact: true }).click()
  await page.waitForTimeout(350)
  assert.equal(materialRequests.length, count)
  checks.push('刷新发布结果、旧记录明确缺失、切换轮次忽略迟到响应、窄面板无溢出、折叠停止材料读取')
  assert.deepEqual(errors, [])
  await writeFile(path.join(output, 'checks.json'), JSON.stringify({ checks, materialRequests, errors }, null, 2))
  console.log(JSON.stringify({ passed: true, checks }, null, 2))
} catch (error) {
  await page.screenshot({ path: path.join(output, 'failure.png') }); throw error
} finally { await context.close(); await browser.close() }
