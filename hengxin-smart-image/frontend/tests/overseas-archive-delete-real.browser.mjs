// Only run against infra/identity-test --delete-skills --serve disposable topology.
import assert from 'node:assert/strict'
import { mkdir, writeFile } from 'node:fs/promises'
import { execFileSync } from 'node:child_process'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.IDENTITY_UI_URL || 'http://localhost:3022'
const runner = process.env.IDENTITY_TEST_RUNNER
assert.ok(['localhost', '127.0.0.1'].includes(new URL(base).hostname))
assert.match(runner || '', /^hx-p\d+-[a-f0-9]+-runner$/)
const output = '../../output/playwright/archive-delete'
const headers = { 'X-HX-Request': '1', Origin: base }, checks = [], errors = []
const docker = (...args) => execFileSync('docker', args, { encoding: 'utf8', timeout: 90000 })
const python = code => docker('exec', runner, '/app/.venv/bin/python', '-c',
  "import sys,os;sys.path.insert(0,'/workspace/infra/identity-test');import checks as h;sys.argv.append('--phase20');os.environ.update(h.environment('overseas'));" + code)
const cleanup = () => python('from sqlalchemy.orm import sessionmaker;from app.overseas.archives.cleanup import cleanup_once;print(cleanup_once(sessionmaker(h.ENGINES["overseas"],expire_on_commit=False)))')
const minio = runner.replace(/runner$/, 'overseas-minio')
const browser = await chromium.launch({ headless: true, ...(process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE ? { executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE } : {}) })
await mkdir(output, { recursive: true })
async function call(context, method, path, data) {
  const response = await context.request[method](`${base}/api/overseas/v1${path}`, { headers, data })
  assert.ok(response.ok(), `${method} ${path}: ${response.status()} ${await response.text()}`)
  return response.json()
}
async function login(code) {
  const context = await browser.newContext({ viewport: { width: 1366, height: 900 } })
  const auth = await context.request.post(`${base}/api/identity/v1/dingtalk/container`, { headers, data: { code } })
  assert.equal(auth.status(), 200)
  const ticket = await context.request.post(`${base}/api/identity/v1/tickets`, { headers, data: { business: 'overseas', purpose: 'session' } })
  assert.equal(ticket.status(), 200)
  await call(context, 'post', '/auth/identity/session', await ticket.json())
  const page = await context.newPage()
  page.setDefaultTimeout(20000)
  page.on('pageerror', error => errors.push(error.message))
  return { context, page }
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
let activePage, minioStopped = false
try {
  const { context, page } = await login('p18-admin'); activePage = page
  const archive = (await call(context, 'get', '/archives')).items.find(item => item.sourceDeleted)
  assert.ok(archive, 'Requires disposable archived images whose source task was deleted')
  const detail = await call(context, 'get', `/archives/${archive.id}`)
  assert.ok(detail.deleteToken)
  const beforeTasks = await call(context, 'get', '/tasks')
  const beforeObjects = JSON.parse(python('from app.storage.minio_store import get_store;from app.core.config import get_settings;import json;print(json.dumps(list(get_store().keys(get_settings().minio_bucket,""))))'))
  const owned = beforeObjects.filter(key => key.includes(`/${archive.id}/`))
  assert.equal(owned.length, detail.pictureCount)
  for (const code of ['p18-operator', 'p18-designer', 'p18-operator_manager', 'p18-design_manager']) {
    const other = await login(code)
    await other.page.goto(`${base}/#/overseas/archive`)
    await other.page.getByRole('heading', { name: '成品库', exact: true }).waitFor()
    await other.page.locator('.hx-library-card').first().waitFor()
    assert.equal(await other.page.getByRole('button', { name: '删除整套成品', exact: true }).count(), 0)
    const denied = await other.context.request.delete(`${base}/api/overseas/v1/archives/${archive.id}`, { headers, data: { deleteToken: detail.deleteToken } })
    assert.equal(denied.status(), 403)
    await other.context.close()
  }
  checks.push('四种非超级管理员无入口且真实DELETE均403')
  await page.goto(`${base}/#/overseas/archive`)
  const card = page.locator('.hx-library-card').filter({ hasText: archive.productName }).first()
  const button = (name, scope = page) => scope.getByRole('button', { name, exact: true })
  let mutations = 0
  page.on('request', request => { if (request.method() === 'DELETE') mutations++ })
  await button('删除整套成品', card).click()
  const dialog = page.getByRole('dialog', { name: '永久删除整套成品', exact: true })
  await button('确认删除', dialog).waitFor()
  await page.screenshot({ path: output + '/confirm-desktop.png', fullPage: true, animations: 'disabled' })
  await page.setViewportSize({ width: 390, height: 844 })
  await unclipped(button('确认删除', dialog)); await unclipped(button('取消', dialog))
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
  await page.screenshot({ path: output + '/confirm-mobile.png', fullPage: true, animations: 'disabled' })
  await button('取消', dialog).click()
  assert.equal(mutations, 0)
  assert.equal((await call(context, 'get', `/archives/${archive.id}`)).deleteToken, detail.deleteToken)
  checks.push('桌面与390px确认可操作；取消未发送删除请求、归档保持')
  assert.match(archive.id, /^[0-9a-f-]{36}$/)
  python(`from sqlalchemy.orm import sessionmaker;from sqlalchemy import select;from uuid import UUID;from app.overseas.archives.models import ArchiveAsset;from app.storage.minio_store import get_store;session=sessionmaker(h.ENGINES['overseas'])();asset=session.scalar(select(ArchiveAsset).where(ArchiveAsset.archive_id==UUID('${archive.id}')));get_store().remove(asset);session.close()`)
  checks.push('隔离归档预先丢失一张图片，随后仍能打开确认并清理整套')
  await page.setViewportSize({ width: 1366, height: 900 })
  await button('删除整套成品', card).click(); await button('确认删除', dialog).click()
  await button('正在删除', card).waitFor()
  assert.equal(mutations, 1)
  assert.equal(await button('下载整套成品', card).isEnabled(), false)
  const blocked = await context.request.get(base + detail.pictures[0].url)
  assert.equal(blocked.status(), 409)
  await page.reload(); await button('正在删除', card).waitFor()
  checks.push('确认仅一次DELETE，刷新恢复正在删除，图片读取与下载被阻止')
  docker('stop', minio); minioStopped = true
  cleanup()
  await button('重试删除整套成品', card).waitFor({ timeout: 30000 })
  assert.equal((await call(context, 'get', `/archives/${archive.id}/deletion`)).status, 'delete_failed')
  await page.screenshot({ path: output + '/failure-retry.png', fullPage: true, animations: 'disabled' })
  docker('start', minio); minioStopped = false
  // Readiness uses the private store probe, never a fixed blind sleep.
  await assert.doesNotReject(async () => {
    for (let attempt = 0; attempt < 30; attempt++) {
      try { python('from app.storage.minio_store import get_store;from app.core.config import get_settings;get_store().ensure_private(get_settings().minio_bucket)'); return }
      catch { await new Promise(resolve => setTimeout(resolve, 250)) }
    }
    throw new Error('Disposable MinIO failed to recover')
  })
  await button('重试删除整套成品', card).click(); await button('确认删除', dialog).click()
  await button('正在删除', card).waitFor(); cleanup()
  await card.waitFor({ state: 'hidden', timeout: 20000 })
  const receipt = await call(context, 'get', `/archives/${archive.id}/deletion`)
  assert.equal(receipt.status, 'deleted'); assert.equal(receipt.error, null)
  assert.equal((await context.request.get(`${base}/api/overseas/v1/archives/${archive.id}`)).status(), 404)
  const afterObjects = JSON.parse(python('from app.storage.minio_store import get_store;from app.core.config import get_settings;import json;print(json.dumps(list(get_store().keys(get_settings().minio_bucket,""))))'))
  assert.deepEqual(afterObjects.sort(), beforeObjects.filter(key => !owned.includes(key)).sort())
  assert.deepEqual((await call(context, 'get', '/tasks')).items, beforeTasks.items)
  assert.deepEqual(await call(context, 'delete', `/archives/${archive.id}`, { deleteToken: detail.deleteToken }), receipt)
  checks.push('真实MinIO停机清理失败可重试，恢复后全部归档对象消失，其他对象及任务不变，重复删除幂等')
  await page.screenshot({ path: output + '/deleted.png', fullPage: true, animations: 'disabled' })
  assert.deepEqual(errors, [])
  await writeFile(output + '/result.json', JSON.stringify({ checks, errors, modelCalls: 0 }, null, 2))
  console.log(JSON.stringify({ passed: checks.length, checks, errors }, null, 2))
  await context.close()
} catch (error) {
  if (activePage && !activePage.isClosed()) await activePage.screenshot({ path: output + '/failure.png', fullPage: true })
  throw error
} finally {
  if (minioStopped) docker('start', minio)
  await browser.close()
}
