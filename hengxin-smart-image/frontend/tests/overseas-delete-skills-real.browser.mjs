// Disposable identity-test --delete-skills --serve only. No model calls.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
import { createHash } from 'node:crypto'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://localhost:3022', runner = process.env.IDENTITY_TEST_RUNNER
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname))
assert.match(runner || '', /^hx-p\d+-[a-f0-9]+-runner$/)
const output = '../../output/playwright/delete-skills', headers = { 'X-HX-Request': '1', Origin: base }, checks = [], errors = []
const browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : {}) })
await mkdir(output, { recursive: true })
const digest = data => createHash('sha256').update(data).digest('hex')
const cleanup = () => execFileSync('docker', ['exec', runner, '/app/.venv/bin/python', '-c', "import sys,os;sys.path.insert(0,'/workspace/infra/identity-test');import checks as h;sys.argv.append('--phase20');os.environ.update(h.environment('overseas'));from sqlalchemy.orm import sessionmaker;from app.overseas.tasks.cleanup import cleanup_once;print(cleanup_once(sessionmaker(h.ENGINES['overseas'],expire_on_commit=False)))"], { encoding: 'utf8' })
async function call(context, method, path, data) {
  const response = await context.request[method](`${base}/api/overseas/v1${path}`, { headers: { ...headers, 'Idempotency-Key': crypto.randomUUID() }, data })
  assert.ok(response.ok(), `${method} ${path}: ${response.status()} ${await response.text()}`)
  return response.json()
}
async function login(code = 'p18-admin') {
  const context = await browser.newContext({ viewport: { width: 1366, height: 900 }, acceptDownloads: true })
  const auth = await context.request.post(`${base}/api/identity/v1/dingtalk/container`, { headers, data: { code } }); assert.equal(auth.status(), 200)
  const ticket = await context.request.post(`${base}/api/identity/v1/tickets`, { headers, data: { business: 'overseas' } }); assert.equal(ticket.status(), 200)
  await call(context, 'post', '/auth/identity/session', await ticket.json())
  const page = await context.newPage(); page.setDefaultTimeout(20000); page.on('pageerror', error => errors.push(error.message))
  return { context, page }
}
async function downloadedBytes(download) {
  assert.equal(await download.failure(), null)
  const stream = await download.createReadStream(), chunks = []
  for await (const chunk of stream) chunks.push(chunk)
  return Buffer.concat(chunks)
}
async function unclipped(locator) {
  await locator.scrollIntoViewIfNeeded()
  assert.deepEqual(await locator.evaluate(element => {
    const bounds = element.getBoundingClientRect(), failures = []
    for (let parent = element.parentElement; parent; parent = parent.parentElement) {
      const rect = parent.getBoundingClientRect(), style = getComputedStyle(parent)
      if (/(auto|scroll|hidden|clip)/.test(style.overflowX) && (bounds.left < rect.left - 1 || bounds.right > rect.right + 1)) failures.push('x')
      if (/(auto|scroll|hidden|clip)/.test(style.overflowY) && (bounds.top < rect.top - 1 || bounds.bottom > rect.bottom + 1)) failures.push('y')
    }
    return failures
  }), [])
}
let activePage
try {
  const { context, page } = await login(); activePage = page
  const button = (name, scope = page) => scope.getByRole('button', { name, exact: true })
  const archives = await call(context, 'get', '/archives'), archive = archives.items.find(item => item.sourceDeleted)
  assert.ok(archive, '隔离实例需有已删除来源的真实归档')
  const detail = await call(context, 'get', `/archives/${archive.id}`), original = await context.request.get(base + detail.pictures[0].url)
  assert.equal(original.status(), 200)
  await page.goto(`${base}/#/overseas/archive`)
  const card = page.locator('.hx-library-card').filter({ hasText: archive.productName }).first()
  await card.getByText('原任务已删除', { exact: true }).waitFor(); await button('查看成品', card).click()
  const dialog = page.getByRole('dialog', { name: '归档成品', exact: true })
  await dialog.getByText('原任务已删除', { exact: true }).waitFor(); assert.equal(await button('查看原任务', dialog).count(), 0)
  await page.waitForFunction(() => [...document.querySelectorAll('.archive-picture img')].length > 0 && [...document.querySelectorAll('.archive-picture img')].every(image => image.complete && image.naturalWidth > 0))
  await dialog.locator('.archive-picture').first().click(); await page.locator('.el-image-viewer__wrapper').waitFor(); await page.keyboard.press('Escape')
  const singlePromise = page.waitForEvent('download'); await button('下载图片', dialog).first().click(); const single = await singlePromise
  assert.equal(digest(await downloadedBytes(single)), digest(await original.body())); assert.equal(single.suggestedFilename(), detail.pictures[0].name)
  await page.screenshot({ path: output + '/archive-deleted-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 }); await unclipped(button('下载图片', dialog).first()); assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
  await page.screenshot({ path: output + '/archive-deleted-mobile.png', fullPage: true }); await button('关闭', dialog).click()
  const zipPromise = page.waitForEvent('download'); await button('下载整套成品', card).click(); const zip = await zipPromise, zipBytes = await downloadedBytes(zip)
  assert.ok(zip.suggestedFilename().endsWith('.zip')); assert.equal(zipBytes.subarray(0, 2).toString(), 'PK')
  checks.push('真实已删除任务归档独立列表/详情/大图/单图下载字节一致/ZIP下载，390px可操作')
  await page.setViewportSize({ width: 1366, height: 900 }); await page.goto(`${base}/#/overseas/admin/skills`)
  const skills = (await call(context, 'get', '/management/skills')).items; assert.ok(skills.length)
  for (const skill of skills) await page.getByText(skill.displayName, { exact: true }).waitFor()
  assert.deepEqual(await page.getByRole('columnheader').allTextContents(), ['名称', '描述'])
  for (const label of ['添加 Skill', '上传', '发布新版本', '停用', '历史版本']) assert.equal(await button(label).count(), 0)
  await page.screenshot({ path: output + '/skills-desktop.png', fullPage: true })
  await page.setViewportSize({ width: 390, height: 844 }); await unclipped(button('刷新 Skill')); await unclipped(page.getByText(skills[0].description, { exact: true })); assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
  await page.screenshot({ path: output + '/skills-mobile.png', fullPage: true })
  const studioTask = (await call(context, 'get', '/tasks')).items.find(task => task.workflow === 'studio' && task.status === 'studio')
  assert.ok(studioTask); const studio = await call(context, 'get', `/tasks/${studioTask.id}/studio`); assert.deepEqual(studio.skills, skills)
  await page.setViewportSize({ width: 1366, height: 900 }); await page.goto(`${base}/#/overseas/tasks/${studioTask.id}`)
  await page.getByRole('combobox', { name: '选择 Skill', exact: true }).click(); await page.getByRole('option', { name: skills[0].displayName, exact: true }).click()
  assert.ok(await page.getByText(skills[0].displayName, { exact: true }).first().isVisible())
  checks.push('真实Skill两列只读、中文目录与工作台完全一致且可选择，390px描述与刷新完整可见')
  const designers = await call(context, 'get', '/task-designers'), name = `浏览器删除隔离任务-${Date.now()}`
  const task = await call(context, 'post', '/tasks', { name, productName: '隔离产品', brand: 'UI-TEST', platform: 'Amazon', market: '美国', remarks: '只做删除验收，不生成图片', skus: [{code:'DELETE-ONLY'}], designerId: designers.items[0].id })
  await page.goto(`${base}/#/overseas/tasks`); await page.getByRole('textbox', { name: '搜索任务', exact: true }).fill(name)
  const row = page.getByRole('row').filter({ hasText: name }); await button('删除', row).click()
  const deletion = page.getByRole('dialog', { name: '永久删除任务', exact: true }); await deletion.getByText(/已归档成品保留/).waitFor()
  await page.getByRole('textbox', { name: '确认删除任务名称', exact: true }).fill('错误名称'); assert.equal(await button('确认永久删除', deletion).isEnabled(), false)
  await button('取消', deletion).click(); assert.equal((await call(context, 'get', `/tasks/${task.id}`)).status, 'created')
  await button('删除', row).click(); await page.getByRole('textbox', { name: '确认删除任务名称', exact: true }).fill(name)
  await button('确认永久删除', deletion).click(); await button('正在删除', row).waitFor(); assert.equal(await button('正在删除', row).isEnabled(), false)
  assert.equal((await call(context, 'get', `/tasks/${task.id}/deletion`)).status, 'deleting'); assert.equal(await row.count(), 1)
  await deletion.waitFor({state:'hidden'}); await page.screenshot({ path: output + '/task-deleting.png', fullPage: true, animations:'disabled' })
  assert.match(cleanup(), /1/); await row.waitFor({ state: 'hidden', timeout: 15000 }); assert.equal((await call(context, 'get', `/tasks/${task.id}/deletion`)).status, 'deleted')
  checks.push('真实管理员名称确认/取消不写/异步删除保留行/后端清理后轮询移除，不调用模型')
  await context.close()
  for (const role of ['p18-operator', 'p18-designer', 'p18-operator_manager', 'p18-design_manager']) {
    const value = await login(role); activePage = value.page; await value.page.goto(`${base}/#/overseas/tasks`)
    await value.page.getByRole('heading', { name: '工作流任务', exact: true }).waitFor(); await value.page.getByText(/共 \d+ 个任务/).waitFor()
    assert.equal(await value.page.getByRole('button', { name: '删除', exact: true }).count(), 0); assert.equal(await value.page.getByRole('button', { name: '重试删除', exact: true }).count(), 0); await value.context.close()
  }
  checks.push('四种非管理员角色均无任务删除入口')
  assert.deepEqual(errors, []); await writeFile(output + '/real-result.json', JSON.stringify({ checks, errors, modelCalls: 0 }, null, 2)); console.log(JSON.stringify({ passed: checks.length, checks, errors }, null, 2))
} catch (error) { if (activePage && !activePage.isClosed()) { console.error(await activePage.locator('body').innerText()); await activePage.screenshot({ path: output + '/failure.png', fullPage: true }) }; throw error }
finally { await browser.close() }
