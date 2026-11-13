// Real frontend, disposable browser storage, intercepted APIs; never calls a model or production.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { resolve, isAbsolute } from 'node:path'
import { pathToFileURL } from 'node:url'
const moduleName = process.env.PLAYWRIGHT_MODULE || 'playwright'
const { chromium } = await import(isAbsolute(moduleName) ? pathToFileURL(moduleName).href : moduleName)
const base = process.env.IDENTITY_UI_URL || 'http://127.0.0.1:3018'
assert.ok(['127.0.0.1', 'localhost'].includes(new URL(base).hostname))
const output = resolve(process.env.BROWSER_OUTPUT || '../../output/playwright/domestic-explicit-skill')
await mkdir(output, { recursive: true })
const browser = await chromium.launch({ headless: true, ...(process.env.BROWSER_CHANNEL ? { channel: process.env.BROWSER_CHANNEL } : {}) })
const context = await browser.newContext({ viewport: { width: 1920, height: 1080 }, serviceWorkers: 'block' })
const page = await context.newPage(), errors = [], unexpected = [], sends = [], checks = [], geometry = []
page.setDefaultTimeout(30000)
page.on('pageerror', error => errors.push(error.message))
const entries = [
  ['camera', '/new-product/camera-accessories', '相机配件生成'],
  ['case', '/new-product/phone-case', '手机壳生成'],
  ['product', '/product-replace/product-only', '只换产品'],
  ['scene', '/product-replace/scene-model-product-size', '换场景 / 模特 / 产品 / 修改尺寸'],
  ['phone', '/product-replace/phone-wallpaper-film', '换手机 / 壁纸 / 膜'],
]
const skill = { id: 'skill-current', name: 'camera-design', displayName: '相机配件电商图片设计规范与产品细节保真技能', description: '仅本轮明确选中才使用' }
const stamp = '2026-11-13T03:00:00Z'
const makeRow = (id, name) => ({ id, name, version: 1, createdAt: stamp, updatedAt: stamp, activeTurnId: null, status: 'empty', turnCount: 0 })
const workspaces = Object.fromEntries(entries.map(([key]) => [key, {
  rows: [makeRow(`${key}-a`, '方案甲'), makeRow(`${key}-b`, '方案乙')], turns: {}, skills: [skill],
}]))
let failure = false, holdSend, releaseSend
const state = (key, id) => {
  const w = workspaces[key], selected = id || w.rows[0].id
  return { taskId: key, taskVersion: 1, archiveId: null, completed: false, reopened: false,
    conversationId: selected, conversations: w.rows, maxConversations: 10, activeConversationCount: 0,
    turns: w.turns[selected] || [], materials: [], skills: w.skills, fixedSkillReady: !!w.skills.length, activeTurnId: null }
}
const button = name => page.getByRole('button', { name, exact: true })
const input = page.getByRole('textbox', { name: '设计要求', exact: true })
const choice = () => page.locator('.domestic-skill-choice input')
async function choose(name) {
  await page.locator('.session-switch').filter({ has: page.getByText(name, { exact: true }) }).click()
  await page.locator('.session-current strong').getByText(name, { exact: true }).waitFor()
  await ready()
}
async function ready() { await input.waitFor(); await page.waitForFunction(() => !document.querySelector('[aria-label="设计要求"]').disabled) }
async function sent(text) {
  await input.fill(text); await button('发送').click()
  await page.waitForFunction(() => document.querySelector('[aria-label="设计要求"]').value === '')
}
async function bounds(label, locator) {
  await locator.scrollIntoViewIfNeeded()
  const result = await locator.evaluate(el => {
    const r = el.getBoundingClientRect(), clipped = []
    for (let p = el.parentElement; p; p = p.parentElement) {
      const s = getComputedStyle(p), b = p.getBoundingClientRect()
      if (/(auto|scroll|hidden|clip)/.test(s.overflowX) && (r.left < b.left - 2 || r.right > b.right + 2)) clipped.push(`${p.className}:x`)
      if (/(auto|scroll|hidden|clip)/.test(s.overflowY) && (r.top < b.top - 2 || r.bottom > b.bottom + 2)) clipped.push(`${p.className}:y`)
    }
    return { rect: { left: r.left, right: r.right, top: r.top, bottom: r.bottom, width: r.width, height: r.height }, clipped,
      viewport: r.left >= -1 && r.right <= innerWidth + 1 && r.top >= -1 && r.bottom <= innerHeight + 1,
      noHorizontalOverflow: document.documentElement.scrollWidth <= innerWidth + 1 }
  })
  geometry.push({ width: page.viewportSize().width, label, ...result })
  assert.deepEqual(result.clipped, [], `${label} clipped: ${JSON.stringify(result)}`)
  assert.ok(result.viewport && result.noHorizontalOverflow, `${label} outside viewport: ${JSON.stringify(result)}`)
}
await context.route('**/*', async route => {
  const request = route.request(), url = new URL(request.url()), path = url.pathname
  if (url.origin !== new URL(base).origin) {
    if (!['api.iconify.design', 'api.unisvg.com', 'api.simplesvg.com'].includes(url.hostname)) unexpected.push(url.href)
    return route.abort()
  }
  if (!path.startsWith('/api/')) return route.continue()
  const json = (body, status = 200) => route.fulfill({ status, contentType: 'application/json', body: JSON.stringify(body) })
  if (path.endsWith('/auth/me')) return json({ id: 'isolated-domestic-user', name: '隔离验收用户', role: 'super_admin', status: 'active' })
  const match = path.match(/^\/api\/v1\/domestic-studio\/workspaces\/(camera|case|product|scene|phone)(.*)$/)
  if (!match) { unexpected.push(path); return json({}, 501) }
  const [, key, suffix] = match, w = workspaces[key]
  if (suffix === '/transcript') return json({ items: [], cursor: 0, hasMore: false })
  if (suffix === '') return json(state(key, url.searchParams.get('conversationId')))
  if (suffix === '/turns' && request.method() === 'POST') {
    const body = request.postDataJSON(), idempotencyKey = request.headers()['idempotency-key']
    sends.push({ workspace: key, body, key: idempotencyKey })
    assert.ok(idempotencyKey); assert.ok(body.conversationId)
    if (holdSend) await new Promise(resolve => { releaseSend = resolve })
    if (failure) return json({ detail: '隔离测试：请求结果待确认' }, 503)
    const id = `turn-${sends.length}`, row = w.rows.find(row => row.id === body.conversationId)
    row.status = 'succeeded'; row.turnCount++
    ;(w.turns[row.id] ||= []).push({ id, text: body.text, skillName: body.skillId ? skill.displayName : null,
      status: 'succeeded', reply: '隔离接口返回的已完成回复', error: null, jobId: `job-${id}`, jobVersion: 1,
      attachments: [], pictures: [], referencePictures: [], createdAt: stamp, conversationId: row.id,
      actor: { id: 'isolated-domestic-user', name: '隔离验收用户' } })
    return json(state(key, row.id))
  }
  unexpected.push(`${request.method()} ${path}`); return json({}, 501)
})
try {
  for (const [key, path, title] of entries) {
    await page.goto(`${base}/#${path}`); await ready()
    await page.getByRole('heading', { name: title, exact: true }).waitFor(); await ready()
    assert.equal(await input.inputValue(), ''); assert.equal(await choice().isChecked(), false)
    assert.equal(await page.locator('.studio-empty').count(), 0)
    const label = page.locator('.domestic-skill-choice'), upload = button('上传附件')
    const a = await label.boundingBox(), b = await upload.boundingBox(); assert.ok(a.x < b.x)
    await page.locator('.domestic-skill-choice').click(); await sent(`${key} 本轮选技能`)
    assert.equal(sends.at(-1).body.skillId, skill.id); assert.equal(await choice().isChecked(), false)
    await page.locator('.studio-message.user .el-tag').getByText(skill.displayName, { exact: true }).waitFor()
    await sent(`${key} 下一轮继续修改`); assert.equal(sends.at(-1).body.skillId, null)
    assert.equal(sends.at(-1).body.conversationId, `${key}-a`)
    checks.push(`${key}: 默认空白；选中发送；成功清空；下一轮null；历史真实技能标签`)
  }
  await page.goto(`${base}/#${entries[0][1]}`); await page.getByRole('heading', { name: entries[0][2], exact: true }).waitFor(); await ready()
  await input.fill('甲草稿'); await page.locator('.domestic-skill-choice').click(); await choose('方案乙'); await ready()
  assert.equal(await choice().isChecked(), false); await input.fill('乙草稿')
  await choose('方案甲'); await ready(); assert.equal(await input.inputValue(), '甲草稿'); assert.equal(await choice().isChecked(), true)
  await choose('方案乙'); await ready(); assert.equal(await input.inputValue(), '乙草稿'); assert.equal(await choice().isChecked(), false)
  await choose('方案甲'); await ready(); checks.push('会话甲乙独立保存文字和技能草稿')
  failure = true; await input.fill('失败保持选择'); await button('发送').click(); await button('核实并重试').waitFor()
  assert.equal(await input.inputValue(), '失败保持选择'); assert.equal(await choice().isChecked(), true)
  assert.equal(await choice().isDisabled(), true); const first = sends.at(-1)
  failure = false; await button('核实并重试').click(); await page.waitForFunction(() => document.querySelector('[aria-label="设计要求"]').value === '')
  assert.deepEqual(sends.at(-1), first); assert.equal(await choice().isChecked(), false)
  checks.push('503后文字/选择保留且锁定，重试复用原幂等键和完整body，成功才清空')
  await input.fill('旧绑定草稿'); await page.locator('.domestic-skill-choice').click()
  workspaces.camera.skills = [{ ...skill, id: 'skill-replacement', displayName: '新绑定技能' }]
  await page.reload(); await ready(); await button('取消失效 Skill').waitFor()
  assert.equal(await button('发送').isDisabled(), true); await button('取消失效 Skill').click()
  await sent('取消旧绑定后普通续聊'); assert.equal(sends.at(-1).body.skillId, null)
  checks.push('绑定变化后旧草稿选择阻止发送，取消后正常null发送')
  workspaces.camera.skills = []; await page.reload(); await ready(); await page.getByText('暂无可选 Skill', { exact: true }).waitFor()
  await sent('未绑定普通对话'); assert.equal(sends.at(-1).body.skillId, null)
  checks.push('未绑定、fixedSkillReady=false仍允许普通发送')
  workspaces.camera.skills = [skill]; await page.reload(); await ready(); await page.locator('.domestic-skill-choice').click(); await input.fill('布局验收草稿')
  for (const width of [1920, 1000, 390]) {
    await page.setViewportSize({ width, height: width === 390 ? 844 : 1080 }); await page.waitForTimeout(250)
    for (const [label, locator] of [['Skill', page.locator('.domestic-skill-choice')], ['输入框', input], ['上传附件', button('上传附件')], ['发送', button('发送')]]) await bounds(label, locator)
    await page.screenshot({ path: resolve(output, `workspace-${width}.png`), fullPage: true, animations: 'disabled' })
  }
  holdSend = true; await button('发送').click(); await page.waitForFunction(() => document.querySelector('.studio-send-tools .is-loading'))
  await bounds('发送中按钮', button('发送')); await bounds('发送中Skill', page.locator('.domestic-skill-choice'))
  assert.equal(await choice().isDisabled(), true); await page.screenshot({ path: resolve(output, 'workspace-390-loading.png'), fullPage: true })
  holdSend = false; releaseSend(); await page.waitForFunction(() => document.querySelector('[aria-label="设计要求"]').value === '')
  checks.push('1920/1000/390长名称与发送中控件裁切祖先、视口边界和横向溢出检查通过')
  assert.deepEqual(errors, []); assert.deepEqual(unexpected, [])
  await writeFile(resolve(output, 'report.json'), JSON.stringify({ checks, sends, geometry, errors, unexpected }, null, 2))
  console.log(JSON.stringify({ result: 'PASS', checks, sends: sends.length, errors, unexpected }, null, 2))
} catch (error) {
  await page.screenshot({ path: resolve(output, 'failure.png'), fullPage: true }).catch(() => {})
  await writeFile(resolve(output, 'failure.json'), JSON.stringify({ error: String(error), errors, unexpected, geometry }, null, 2))
  throw error
} finally { releaseSend?.(); await context.close(); await browser.close() }
