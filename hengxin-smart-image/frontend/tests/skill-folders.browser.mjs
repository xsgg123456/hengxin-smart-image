// Full disposable API/UDS integration. Never run against a production origin.
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { mkdtemp, mkdir, writeFile, readFile, readdir, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import path from 'node:path'
import { dropNativeFolder, installBrowserFolderPicker, inspectSavedFolder } from './skill-folders-browser-helpers.mjs'
const { chromium } = await import(process.env.PLAYWRIGHT_MODULE || 'playwright')
const base = process.env.SKILL_FOLDER_UI_URL || 'http://127.0.0.1:3054'
assert.equal(new URL(base).hostname, '127.0.0.1')
assert.equal(new URL(base).port, '3054')
const output = path.resolve('../../output/playwright/skill-folders')
await mkdir(output, { recursive: true })
const temporary = await mkdtemp(path.join(tmpdir(), 'hx-folder-e2e-'))
const root = path.join(temporary, '完整技能原目录')
await mkdir(path.join(root, 'assets', '空目录'), { recursive: true })
await mkdir(path.join(root, 'scripts'))
await writeFile(path.join(root, 'SKILL.md'), '---\nname: folder-integration\ndescription: 完整目录上传下载集成验收\n---\n# 文件夹完整性验收\n\n[脚本](scripts/check.py)\n')
await writeFile(path.join(root, 'scripts', 'check.py'), '# never executed\n')
await writeFile(path.join(root, 'assets', '字体与图片.bin'), Buffer.from(Array.from({ length: 512 }, (_, i) => i % 256)))
for (let i = 0; i < 105; i++) await writeFile(path.join(root, `条目-${String(i).padStart(3, '0')}.txt`), `文件 ${i}\r\n`)
const expected = {}
async function manifest(dir, prefix = '') {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const relative = prefix + entry.name
    if (entry.isDirectory()) { expected[relative + '/'] = { directory: true }; await manifest(path.join(dir, entry.name), relative + '/') }
    else { const bytes = await readFile(path.join(dir, entry.name)); expected[relative] = { size: bytes.length, sha256: createHash('sha256').update(bytes).digest('hex') } }
  }
}
await manifest(root)
const browser = await chromium.launch({ headless: true, channel: 'chrome' })
const context = await browser.newContext({ viewport: { width: 1440, height: 1000 } })
const page = await context.newPage(), errors = [], checks = []
page.on('pageerror', e => errors.push(e.message))
page.setDefaultTimeout(30000)
await installBrowserFolderPicker(page)
const button = name => page.getByRole('button', { name, exact: true })
const headers = { Origin: base, 'X-HX-Request': '1' }
const api = '/api/overseas/v1/management'
const shot = name => page.screenshot({ path: path.join(output, name + '.png'), fullPage: true })
try {
  const login = await context.request.post(base + '/api/overseas/v1/auth/identity/session', { headers, data: { ticket: 'isolated-folder-ticket' } })
  assert.equal(login.status(), 200, await login.text())
  await page.goto(base + '/#/overseas/admin/skills')
  await button('上传 Skill 文件夹').click()
  await dropNativeFolder(page, root)
  await page.getByText('已完整读取，尚未上传', { exact: false }).waitFor()
  await shot('01-folder-scanned')
  await button('上传并安装').click()
  await page.getByRole('dialog').getByText(/108 个文件.*已安装/).waitFor({ timeout: 300000 })
  await button('关闭').click()
  const response = await context.request.get(base + api + '/skills')
  const catalog = await response.json(), item = catalog.items.find(x => x.name === 'folder-integration')
  assert.ok(item, JSON.stringify(catalog)); assert.equal(item.enabled, false); assert.deepEqual(item.platforms, [])
  const descriptor = await (await context.request.get(base + api + `/skills/${item.id}/package`)).json()
  assert.equal(descriptor.rootName, path.basename(root)); assert.deepEqual(descriptor.entries, expected)
  checks.push('Native folder drag >100 siblings, empty directories, raw binary: installed manifest exact')
  console.log(checks.at(-1))
  await button('保存为文件夹').click()
  await page.getByText('文件夹保存完成，全部目录和文件已读回核验', { exact: true }).waitFor({ timeout: 300000 })
  const saved = await inspectSavedFolder(page, path.basename(root))
  assert.deepEqual(saved.entries, expected); assert.equal(saved.pickerCalls[0].active, true)
  checks.push('Actual browser directory handles: all saved files, empty directories and hashes match')
  await shot('02-saved-and-verified')
  await button('保存为文件夹').click()
  await page.getByText(/目标已存在同名文件夹或文件/).waitFor()
  assert.deepEqual((await inspectSavedFolder(page, path.basename(root))).entries, expected)
  checks.push('Existing folder refused without overwriting')
  await button('删除 Skill').click()
  await page.getByRole('dialog').getByText(/历史会话/).waitFor()
  await shot('03-delete-confirm')
  await button('取消').click()
  assert.equal((await (await context.request.get(base + api + '/skills')).json()).items.length, 1)
  await button('上传 Skill 文件夹').click()
  await dropNativeFolder(page, root)
  await page.getByText('已完整读取，尚未上传', { exact: false }).waitFor()
  await button('上传并安装').click()
  await page.getByText('同名同内容已安装，无需重复安装', { exact: true }).waitFor({ timeout: 300000 })
  await page.getByRole('dialog').getByText(/108 个文件.*已安装/).waitFor()
  await button('关闭').click()
  assert.equal((await (await context.request.get(base + api + '/skills')).json()).items.length, 1)
  checks.push('Identical upload idempotent; delete cancel preserves catalog')
  await writeFile(path.join(root, 'scripts', 'check.py'), '# changed but never executed\n')
  await button('上传 Skill 文件夹').click(); await dropNativeFolder(page, root)
  await page.getByText('已完整读取，尚未上传', { exact: false }).waitFor(); await button('上传并安装').click()
  await button('确认更新同名 Skill').waitFor({ timeout: 300000 })
  await shot('04-update-diff')
  const before = await (await context.request.get(base + api + `/skills/${item.id}/package`)).json()
  assert.equal(before.checksum, descriptor.checksum)
  await button('确认更新同名 Skill').click()
  await page.getByRole('dialog').getByText(/108 个文件.*已安装/).waitFor(); await button('关闭').click()
  const after = await (await context.request.get(base + api + `/skills/${item.id}/package`)).json()
  assert.notEqual(after.checksum, descriptor.checksum)
  const oldFile = await context.request.get(base + api + `/skills/${item.id}/files?` + new URLSearchParams({ release: descriptor.release, path: 'scripts/check.py' }))
  assert.equal(oldFile.status(), 410)
  checks.push('Update waits for explicit confirmation, unreferenced old central bytes reclaimed')
  await page.setViewportSize({ width: 390, height: 844 }); await shot('05-narrow')
  assert.ok(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1))
  await page.setViewportSize({ width: 1440, height: 1000 })
  let failedDelete = false
  await page.route('**/management/skills/' + item.id, async route => {
    if (route.request().method() === 'DELETE' && !failedDelete) {
      failedDelete = true
      await route.fulfill({ status: 503, contentType: 'application/json', body: JSON.stringify({ detail: '隔离测试：物理清理失败，请重试' }) })
    } else await route.continue()
  })
  await button('删除 Skill').click(); await button('确认删除').click()
  await page.getByText('隔离测试：物理清理失败，请重试', { exact: false }).waitFor()
  assert.equal((await (await context.request.get(base + api + '/skills')).json()).items.length, 1)
  await shot('06-delete-failed')
  await button('删除 Skill').click(); await button('确认删除').click()
  await page.getByText('暂无已安装 Skill', { exact: false }).waitFor()
  await page.getByText(/Skill 已删除，释放/).waitFor()
  assert.deepEqual((await (await context.request.get(base + api + '/skills')).json()).items, [])
  const frozen = await context.request.get(base + api + `/skills/${item.id}/files?` + new URLSearchParams({ release: descriptor.release, path: 'scripts/check.py' }))
  assert.equal(frozen.status(), 410)
  checks.push('Failed deletion remains retryable; completed deletion shows released space and empty catalog')
  assert.deepEqual(errors, [])
  await shot('06-empty')
  await writeFile(path.join(output, 'result.json'), JSON.stringify({ checks, errors, entries: Object.keys(expected).length, savedEntries: Object.keys(saved.entries).length }, null, 2))
  console.log(JSON.stringify({ passed: checks.length, checks, errors }, null, 2))
} catch (e) { await shot('failure'); console.error((await page.locator('body').innerText()).slice(-6000)); throw e }
finally { await context.close(); await browser.close(); await rm(temporary, { recursive: true, force: true }) }




